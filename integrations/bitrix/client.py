import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import BitrixError

logger = logging.getLogger(__name__)

_UF_MOTIVO_ESCALAMIENTO = "UF_CRM_MOTIVO_ESCALAMIENTO_HUMANO"
_UF_RESUMEN_CONVERSACION = "UF_CRM_RESUMEN_CONVERSACION"


class BitrixClient:
    """Cliente para el webhook entrante de Bitrix24 (no requiere sesión interactiva)."""

    def __init__(self) -> None:
        self._base_url = settings.bitrix_webhook_url.rstrip("/")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def _call(self, method: str, params: dict) -> dict:
        url = f"{self._base_url}/{method}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise BitrixError(
                f"Bitrix API error {exc.response.status_code}",
                retriable=exc.response.status_code >= 500,
                original=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise BitrixError("Bitrix network error", retriable=True, original=exc) from exc

    async def buscar_deal_por_telefono(self, telefono: str) -> str:
        """Busca el deal del imconnector (Open Lines) para el teléfono dado.

        Filtra por SOURCE_ID del conector activo para excluir deals creados por el bot.
        Si no hay coincidencia con SOURCE_ID, busca cualquier deal activo como fallback.
        """
        tail = telefono[-4:]
        source_id = f"{settings.bitrix_connector_line_id}|{settings.bitrix_connector_id.upper()}"

        # Búsqueda principal: solo deals creados por el canal Open Lines
        result = await self._call("crm.deal.list", {
            "filter": {
                "CATEGORY_ID": settings.bitrix_pipeline_id,
                "%TITLE": f"*{tail}",
                "SOURCE_ID": source_id,
            },
            "order": {"DATE_CREATE": "DESC"},
            "select": ["ID", "STAGE_ID", "TITLE"],
            "start": 0,
        })
        items = result.get("result", [])
        if items:
            deal_id = str(items[0]["ID"])
            logger.info("bitrix_deal_encontrado", extra={"phone_tail": tail, "deal_id": deal_id, "source": "openlines"})
            return deal_id

        # Fallback: cualquier deal activo con ese teléfono (excluye solo WON — Caído se reactiva)
        result2 = await self._call("crm.deal.list", {
            "filter": {
                "CATEGORY_ID": settings.bitrix_pipeline_id,
                "%TITLE": f"*{tail}",
                "!=STAGE_ID": ["C90:WON"],
            },
            "order": {"DATE_CREATE": "DESC"},
            "select": ["ID", "STAGE_ID", "TITLE"],
            "start": 0,
        })
        items2 = result2.get("result", [])
        if items2:
            deal_id = str(items2[0]["ID"])
            stage  = items2[0].get("STAGE_ID", "")
            logger.info("bitrix_deal_encontrado", extra={"phone_tail": tail, "deal_id": deal_id, "source": "fallback", "stage": stage})
            return deal_id

        return ""

    async def _find_or_create_contact(self, telefono: str, nombre: str = "") -> str:
        """Busca un contacto por teléfono (crm.duplicate.findbycomm) o crea uno nuevo.

        Retorna el contact_id como string, o '' si ocurre algún error.
        """
        try:
            dup = await self._call("crm.duplicate.findbycomm", {
                "type": "PHONE",
                "values": [telefono],
                "entity_type": "CONTACT",
            })
            dup_result = dup.get("result", {})
            # Bitrix retorna [] (lista) si no hay duplicados, {"CONTACT": [...]} si los hay
            contact_ids = dup_result.get("CONTACT", []) if isinstance(dup_result, dict) else []
            if contact_ids:
                contact_id = str(contact_ids[0])
                logger.info("bitrix_contact_found", extra={"phone_tail": telefono[-4:], "contact_id": contact_id})
                return contact_id

            fields = {
                "NAME": nombre or f"WA *{telefono[-4:]}",
                "PHONE": [{"VALUE": telefono, "VALUE_TYPE": "WORK"}],
                "SOURCE_ID": "WEB",
            }
            result = await self._call("crm.contact.add", {"fields": fields})
            contact_id = str(result.get("result", ""))
            logger.info("bitrix_contact_created", extra={"phone_tail": telefono[-4:], "contact_id": contact_id})
            return contact_id
        except Exception as exc:
            logger.warning("bitrix_contact_error", extra={"phone_tail": telefono[-4:], "error": str(exc)})
            return ""

    async def link_contact_to_deal(self, deal_id: str, telefono: str, nombre: str = "") -> None:
        """Vincula o actualiza el contacto del deal con el teléfono del cliente.

        - Si el deal no tiene contacto: crea/busca uno y lo vincula.
        - Si ya tiene contacto pero sin PHONE: actualiza el contacto con el teléfono.
        Seguro de llamar en background — silencia todos los errores.
        """
        try:
            deal = await self.get_deal(deal_id)
            contact_id = deal.get("CONTACT_ID")

            if not contact_id:
                # Sin contacto: crear/encontrar y vincular al deal
                contact_id = await self._find_or_create_contact(telefono, nombre)
                if contact_id:
                    await self.actualizar_deal(deal_id, {"CONTACT_ID": contact_id})
                    logger.info("bitrix_contact_linked", extra={"deal_id": deal_id, "contact_id": contact_id})
                return

            # Con contacto existente (creado por Open Lines): verificar que tenga PHONE
            r = await self._call("crm.contact.get", {"id": contact_id})
            existing_phone = r.get("result", {}).get("PHONE")
            if not existing_phone:
                await self._call("crm.contact.update", {
                    "id": contact_id,
                    "fields": {"PHONE": [{"VALUE": telefono, "VALUE_TYPE": "WORK"}]},
                })
                logger.info("bitrix_contact_phone_updated", extra={"deal_id": deal_id, "contact_id": contact_id, "phone_tail": telefono[-4:]})
        except Exception as exc:
            logger.warning("bitrix_link_contact_error", extra={"deal_id": deal_id, "error": str(exc)})

    async def crear_deal(self, telefono: str, datos: dict, stage_id: str | None = None) -> dict:
        """Crea un deal en el pipeline de portabilidad (category_id = BITRIX_PIPELINE_ID)."""
        nombre = datos.get("NAME", "")
        titulo = f"Portabilidad {nombre} *{telefono[-4:]}" if nombre else f"Portabilidad *{telefono[-4:]}"

        contact_id = await self._find_or_create_contact(telefono, nombre)

        fields = {
            "TITLE": titulo,
            "CATEGORY_ID": settings.bitrix_pipeline_id,
            "STAGE_ID": stage_id or settings.bitrix_stage_listo,
            "COMMENTS": (
                f"Teléfono: {telefono}\n"
                + datos.get("COMMENTS", "")
            ),
        }
        if contact_id:
            fields["CONTACT_ID"] = contact_id

        result = await self._call("crm.deal.add", {"fields": fields})
        logger.info("bitrix_deal_created", extra={"phone_tail": telefono[-4:], "contact_id": contact_id})
        return result

    async def actualizar_deal(self, deal_id: str, datos: dict) -> dict:
        """Actualiza título, etapa y comentarios de un deal existente."""
        fields = {k: v for k, v in datos.items() if v is not None}
        result = await self._call("crm.deal.update", {"id": deal_id, "fields": fields})
        logger.info("bitrix_deal_updated", extra={"deal_id": deal_id})
        return result

    async def mover_etapa(self, deal_id: str, etapa: str) -> dict:
        """Mueve el deal a la etapa indicada del pipeline."""
        result = await self._call("crm.deal.update", {"id": deal_id, "fields": {"STAGE_ID": etapa}})
        logger.info("bitrix_etapa_actualizada", extra={"deal_id": deal_id, "etapa": etapa})
        return result

    async def set_tipificacion(self, deal_id: str, tipificacion: str) -> dict:
        """Registra el motivo de cierre/caída en el deal."""
        result = await self._call(
            "crm.deal.update",
            {"id": deal_id, "fields": {"UF_TIPIFICACION": tipificacion}},
        )
        logger.info("bitrix_tipificacion_set", extra={"deal_id": deal_id, "tipo": tipificacion})
        return result

    async def get_deal(self, deal_id: str) -> dict:
        """Retorna los campos del deal: STAGE_ID, ASSIGNED_BY_ID, SOURCE_ID, CLOSEDATE, CONTACT_ID, COMMENTS."""
        result = await self._call("crm.deal.get", {"id": deal_id})
        return result.get("result", {})

    async def get_stage_history(self, deal_id: str) -> list[dict]:
        """Retorna el historial de etapas del deal ordenado cronológicamente.

        Cada entrada tiene: STAGE_ID y CREATED_TIME (ISO 8601).
        Usa crm.stagehistory.list con entityTypeId=2 (Deal).
        """
        try:
            result = await self._call("crm.stagehistory.list", {
                "entityTypeId": 2,
                "filter": {"ENTITY_ID": deal_id},
                "select": ["ID", "ENTITY_ID", "STAGE_ID", "CREATED_TIME"],
                "order": {"CREATED_TIME": "ASC"},
            })
            return result.get("result", {}).get("items", [])
        except Exception as exc:
            logger.warning("bitrix_stage_history_error", extra={"deal_id": deal_id, "error": str(exc)})
            return []

    async def _ensure_one_userfield(self, field_name_suffix: str, label: str) -> None:
        """Crea un campo personalizado en deals si no existe. field_name_suffix sin prefijo UF_CRM_."""
        full_name = f"UF_CRM_{field_name_suffix}"
        result = await self._call("crm.deal.userfield.list", {
            "filter": {"FIELD_NAME": full_name},
        })
        if result.get("result"):
            return
        await self._call("crm.deal.userfield.add", {
            "fields": {
                "ENTITY_ID": "CRM_DEAL",
                "FIELD_NAME": field_name_suffix,
                "USER_TYPE_ID": "string",
                "EDIT_FORM_LABEL": {"ru": label},
                "LIST_COLUMN_LABEL": {"ru": label},
                "IS_SEARCHABLE": "Y",
            },
        })
        logger.info("bitrix_userfield_created", extra={"field": full_name})

    async def ensure_custom_fields(self) -> None:
        """Crea los campos personalizados del bot en deals y los agrega al layout si no existen."""
        try:
            await self._ensure_one_userfield("MOTIVO_ESCALAMIENTO_HUMANO", "Motivo de Escalamiento")
            await self._ensure_one_userfield("RESUMEN_CONVERSACION", "Resumen de Conversación")
            await self._ensure_layout_fields()
        except Exception as exc:
            logger.warning("bitrix_ensure_fields_error", extra={"error": str(exc)})

    async def _ensure_layout_fields(self) -> None:
        """Agrega los campos del bot a la vista del deal (sección Bot Telcel) si no están."""
        campos = [_UF_MOTIVO_ESCALAMIENTO, _UF_RESUMEN_CONVERSACION]
        result = await self._call("crm.deal.details.configuration.get", {
            "scope": "C",
            "data": {"categoryId": settings.bitrix_pipeline_id},
        })
        sections = result.get("result", [])
        existing = {el["name"] for s in sections for el in s.get("elements", [])}
        nuevos = [c for c in campos if c not in existing]
        if not nuevos:
            return
        sections.append({
            "name": "section_bot_telcel",
            "title": "Bot Telcel",
            "type": "section",
            "elements": [{"name": c, "optionFlags": "0"} for c in campos],
        })
        await self._call("crm.deal.details.configuration.set", {
            "scope": "C",
            "data": sections,
        })
        logger.info("bitrix_layout_updated", extra={"fields_added": nuevos})

    async def set_campos_escalamiento(self, deal_id: str, motivo: str, resumen: str) -> None:
        """Puebla motivo y resumen de conversación en el deal al escalar."""
        try:
            await self.actualizar_deal(deal_id, {
                _UF_MOTIVO_ESCALAMIENTO: motivo,
                _UF_RESUMEN_CONVERSACION: resumen,
            })
            logger.info("bitrix_campos_escalamiento_set", extra={"deal_id": deal_id, "motivo": motivo})
        except Exception as exc:
            logger.warning("bitrix_campos_escalamiento_error", extra={"deal_id": deal_id, "error": str(exc)})

    async def marcar_venta_exitosa(self, deal_id: str) -> dict:
        """Mueve el deal a la etapa VENTA (C90:WON)."""
        result = await self._call(
            "crm.deal.update",
            {"id": deal_id, "fields": {"STAGE_ID": "C90:WON"}},
        )
        logger.info("bitrix_venta_exitosa", extra={"deal_id": deal_id})
        return result

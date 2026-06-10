import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import BitrixError

logger = logging.getLogger(__name__)


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

    async def crear_deal(self, telefono: str, datos: dict, stage_id: str | None = None) -> dict:
        """Crea un deal en el pipeline de portabilidad (category_id = BITRIX_PIPELINE_ID)."""
        nombre = datos.get("NAME", "")
        titulo = f"Portabilidad {nombre} *{telefono[-4:]}" if nombre else f"Portabilidad *{telefono[-4:]}"
        fields = {
            "TITLE": titulo,
            "CATEGORY_ID": settings.bitrix_pipeline_id,
            "STAGE_ID": stage_id or settings.bitrix_stage_listo,
            "COMMENTS": (
                f"Teléfono: {telefono}\n"
                + datos.get("COMMENTS", "")
            ),
        }
        result = await self._call("crm.deal.add", {"fields": fields})
        logger.info("bitrix_deal_created", extra={"phone_tail": telefono[-4:]})
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

    async def marcar_venta_exitosa(self, deal_id: str) -> dict:
        """Mueve el deal a la etapa VENTA (C90:WON)."""
        result = await self._call(
            "crm.deal.update",
            {"id": deal_id, "fields": {"STAGE_ID": "C90:WON"}},
        )
        logger.info("bitrix_venta_exitosa", extra={"deal_id": deal_id})
        return result

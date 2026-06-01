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

    async def crear_o_actualizar_lead(self, telefono: str, datos: dict) -> dict:
        """Crea o actualiza el lead en Bitrix con los datos del cliente."""
        fields = {
            "PHONE": [{"VALUE": telefono, "VALUE_TYPE": "WORK"}],
            "TITLE": f"Portabilidad {telefono[-4:]}",
            **datos,
        }
        result = await self._call("crm.lead.add", {"fields": fields})
        logger.info("bitrix_lead_created", extra={"phone_tail": telefono[-4:]})
        return result

    async def mover_etapa(self, lead_id: str, etapa: str) -> dict:
        """Mueve el lead a la etapa indicada del pipeline operativo."""
        result = await self._call("crm.lead.update", {"id": lead_id, "fields": {"STATUS_ID": etapa}})
        logger.info("bitrix_etapa_actualizada", extra={"lead_id": lead_id, "etapa": etapa})
        return result

    async def set_tipificacion(self, lead_id: str, tipificacion: str) -> dict:
        """Registra el motivo de cierre/caída en el lead."""
        result = await self._call(
            "crm.lead.update",
            {"id": lead_id, "fields": {"UF_TIPIFICACION": tipificacion}},
        )
        logger.info("bitrix_tipificacion_set", extra={"lead_id": lead_id, "tipo": tipificacion})
        return result

    async def marcar_venta_exitosa(self, lead_id: str) -> dict:
        """Marca la casilla de venta exitosa y mueve a la etapa Venta."""
        result = await self._call(
            "crm.lead.update",
            {"id": lead_id, "fields": {"STATUS_ID": "CONVERTED", "UF_VENTA_EXITOSA": True}},
        )
        logger.info("bitrix_venta_exitosa", extra={"lead_id": lead_id})
        return result

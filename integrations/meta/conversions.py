"""Meta Conversions API (CAPI) — envía eventos de venta a Meta para optimización de anuncios.

Flujo:
  1. Bitrix mueve deal a C90:WON (venta exitosa)
  2. job_bitrix_sync detecta el cambio y llama send_purchase_event()
  3. CAPI envía el evento "Purchase" al Pixel con los datos del lead
     (teléfono hasheado, ctwa_clid si existe) para atribución
"""

import asyncio
import hashlib
import logging
import time

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

CAPI_URL = "https://graph.facebook.com/v20.0/{pixel_id}/events"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _build_event(
    phone: str,
    event_id: str,
    value: float = 0.0,
    currency: str = "MXN",
    ctwa_clid: str = "",
    ad_id: str = "",
) -> dict:
    user_data: dict = {
        "ph": [_sha256(phone)],
        "client_ip_address": "0.0.0.0",
        "client_user_agent": "Vera-Bot/1.0",
    }
    if ctwa_clid:
        user_data["ctwa_clid"] = ctwa_clid

    event: dict = {
        "event_name": "Purchase",
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": "other",
        "user_data": user_data,
    }

    if value > 0:
        event["custom_data"] = {
            "value": value,
            "currency": currency,
        }

    return event


async def send_purchase_event(
    phone: str,
    deal_id: str,
    recarga: float = 0.0,
    ctwa_clid: str = "",
    ad_id: str = "",
) -> bool:
    """Envía evento Purchase a Meta CAPI cuando se cierra una venta (C90:WON)."""
    if not settings.meta_pixel_id or not settings.meta_access_token:
        logger.warning("capi_not_configured")
        return False

    event = _build_event(
        phone=phone,
        event_id=f"won_{deal_id}",
        value=recarga,
        ctwa_clid=ctwa_clid,
        ad_id=ad_id,
    )

    payload = {
        "data": [event],
        "access_token": settings.meta_access_token,
    }

    url = CAPI_URL.format(pixel_id=settings.meta_pixel_id)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            events_received = result.get("events_received", 0)
            logger.info("capi_event_sent", extra={
                "phone_tail": phone[-4:],
                "deal_id": deal_id,
                "events_received": events_received,
                "ctwa_clid": ctwa_clid[:12] + "…" if ctwa_clid else "",
            })
            return events_received > 0
    except Exception as exc:
        logger.error("capi_send_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return False


async def send_lead_event(
    phone: str,
    deal_id: str,
    ctwa_clid: str = "",
) -> bool:
    """Envía evento Lead a Meta CAPI cuando un prospecto completa KPIs (C90:PROSPECTO)."""
    if not settings.meta_pixel_id or not settings.meta_access_token:
        return False

    event = _build_event(
        phone=phone,
        event_id=f"prospecto_{deal_id}",
        ctwa_clid=ctwa_clid,
    )
    event["event_name"] = "Lead"

    payload = {
        "data": [event],
        "access_token": settings.meta_access_token,
    }

    url = CAPI_URL.format(pixel_id=settings.meta_pixel_id)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("capi_lead_sent", extra={"phone_tail": phone[-4:], "deal_id": deal_id})
            return True
    except Exception as exc:
        logger.error("capi_lead_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return False

"""Meta Conversions API (CAPI) — envía eventos de venta a Meta para optimización de anuncios.

Flujo:
  1. Bitrix mueve deal a C90:WON (venta exitosa)
  2. job_bitrix_sync detecta el cambio y llama send_purchase_event()
  3. CAPI envía el evento "Purchase" al Pixel con los datos del lead
     (teléfono, nombre, municipio hasheados + ctwa_clid) para atribución
"""

import hashlib
import logging
import time

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

CAPI_URL = "https://graph.facebook.com/v20.0/{pixel_id}/events"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _split_name(nombre: str) -> tuple[str, str]:
    """Separa nombre completo en primer nombre y apellido(s)."""
    parts = nombre.strip().split(" ", 1)
    fn = parts[0] if parts else ""
    ln = parts[1] if len(parts) > 1 else ""
    return fn, ln


def _build_user_data(
    phone: str,
    ctwa_clid: str = "",
    nombre: str = "",
    municipio: str = "",
) -> dict:
    user_data: dict = {
        "ph": [_sha256(phone)],
        "client_ip_address": "0.0.0.0",
        "client_user_agent": "Vera-Bot/1.0",
    }

    if ctwa_clid:
        user_data["ctwa_clid"] = ctwa_clid

    if nombre:
        fn, ln = _split_name(nombre)
        if fn:
            user_data["fn"] = [_sha256(fn)]
        if ln:
            user_data["ln"] = [_sha256(ln)]

    if municipio:
        user_data["ct"] = [_sha256(municipio)]

    return user_data


def _build_event(
    phone: str,
    event_id: str,
    value: float = 0.0,
    currency: str = "MXN",
    ctwa_clid: str = "",
    nombre: str = "",
    municipio: str = "",
) -> dict:
    event: dict = {
        "event_name": "Purchase",
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": "other",
        "user_data": _build_user_data(
            phone=phone,
            ctwa_clid=ctwa_clid,
            nombre=nombre,
            municipio=municipio,
        ),
    }

    if value > 0:
        event["custom_data"] = {
            "value": value,
            "currency": currency,
        }

    return event


async def _post_event(payload: dict, phone_tail: str, log_key: str, extra: dict) -> bool:
    url = CAPI_URL.format(pixel_id=settings.meta_pixel_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            events_received = result.get("events_received", 0)
            logger.info(log_key, extra={**extra, "events_received": events_received})
            return events_received > 0
    except Exception as exc:
        logger.error(f"{log_key}_error", extra={"phone_tail": phone_tail, "error": str(exc)})
        return False


async def send_purchase_event(
    phone: str,
    deal_id: str,
    recarga: float = 0.0,
    ctwa_clid: str = "",
    nombre: str = "",
    municipio: str = "",
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
        nombre=nombre,
        municipio=municipio,
    )

    return await _post_event(
        payload={"data": [event], "access_token": settings.meta_access_token},
        phone_tail=phone[-4:],
        log_key="capi_purchase_sent",
        extra={
            "phone_tail": phone[-4:],
            "deal_id": deal_id,
            "ctwa_clid": ctwa_clid[:12] + "…" if ctwa_clid else "",
            "con_nombre": bool(nombre),
            "con_municipio": bool(municipio),
        },
    )


async def send_lead_event(
    phone: str,
    deal_id: str,
    ctwa_clid: str = "",
    nombre: str = "",
    municipio: str = "",
) -> bool:
    """Envía evento Lead a Meta CAPI cuando un prospecto completa KPIs (C90:PROSPECTO)."""
    if not settings.meta_pixel_id or not settings.meta_access_token:
        return False

    event = _build_event(
        phone=phone,
        event_id=f"prospecto_{deal_id}",
        ctwa_clid=ctwa_clid,
        nombre=nombre,
        municipio=municipio,
    )
    event["event_name"] = "Lead"

    return await _post_event(
        payload={"data": [event], "access_token": settings.meta_access_token},
        phone_tail=phone[-4:],
        log_key="capi_lead_sent",
        extra={
            "phone_tail": phone[-4:],
            "deal_id": deal_id,
            "ctwa_clid": ctwa_clid[:12] + "…" if ctwa_clid else "",
            "con_nombre": bool(nombre),
            "con_municipio": bool(municipio),
        },
    )

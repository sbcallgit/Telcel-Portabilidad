"""Control del bot desde Bitrix24 vía webhooks de salida.

POST /webhooks/bitrix/bot-pause   → pausa el bot para el número vinculado al deal
POST /webhooks/bitrix/bot-resume  → reactiva el bot para el número vinculado al deal

Configuración en Bitrix24:
  Automatización del deal → Agregar robot → Webhook de salida
  URL pausa:   https://portabilidad.callcomcc.io/webhooks/bitrix/bot-pause
  URL activa:  https://portabilidad.callcomcc.io/webhooks/bitrix/bot-resume

Bitrix envía el body como application/x-www-form-urlencoded con notación de corchetes.
Campos relevantes:
  auth[domain]     → dominio del portal (validación: b24-ahyle8.bitrix24.mx)
  document_id[2]   → "DEAL_123" — ID del deal que disparó el robot

Se busca el teléfono en `leads.bitrix_lead_id` y se escribe/elimina
la llave `bot_pausado:{phone}` en Redis.
"""

import logging
import re
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request

from integrations.bitrix.client import BitrixClient
from integrations.postgres.client import fetchval
from integrations.redis_client import get_redis

router = APIRouter()
logger = logging.getLogger(__name__)

_BITRIX_DOMAIN = "b24-ahyle8.bitrix24.mx"


def _redis_key(phone: str) -> str:
    return f"bot_pausado:{phone}"


def _extract_deal_id(form: dict) -> str | None:
    """Extrae el deal ID del payload form-data de Bitrix.

    Robots de automatización: document_id[2] = "DEAL_123"
    Webhooks de evento CRM:   data[FIELDS][ID] = "123"
    """
    # Formato robot de automatización
    doc = form.get("document_id[2]")
    if doc:
        match = re.search(r"\d+", str(doc))
        if match:
            return match.group()

    # Formato evento CRM (fallback)
    raw_id = form.get("data[FIELDS][ID]")
    if raw_id:
        return str(raw_id).strip()

    return None


def _validate_bitrix_origin(form: dict) -> None:
    """Verifica que el request proviene de nuestro portal Bitrix24."""
    domain = form.get("auth[domain]", "")
    if domain != _BITRIX_DOMAIN:
        raise HTTPException(status_code=403, detail="Forbidden")


async def _phone_from_deal(deal_id: str) -> str | None:
    # Ruta rápida: tabla local
    phone = await fetchval(
        "SELECT telefono FROM leads WHERE bitrix_lead_id = $1 LIMIT 1",
        deal_id,
    )
    if phone:
        return str(phone)

    # Fallback: consultar Bitrix → deal → contacto → teléfono
    try:
        bitrix = BitrixClient()
        deal = await bitrix.get_deal(deal_id)
        contact_id = deal.get("CONTACT_ID")
        if not contact_id:
            return None
        r = await bitrix._call("crm.contact.get", {"id": contact_id})
        phones = r.get("result", {}).get("PHONE", [])
        if phones:
            return str(phones[0].get("VALUE", ""))
    except Exception as exc:
        logger.warning("bitrix_phone_lookup_failed", extra={"deal_id": deal_id, "error": str(exc)})

    return None


async def _handle_toggle(request: Request, pause: bool) -> dict:
    raw = await request.body()
    # parse_qs devuelve listas; tomamos el primer valor de cada clave
    form = {k: v[0] for k, v in parse_qs(raw.decode()).items()}

    # Log de claves para diagnóstico
    logger.debug("bitrix_bot_toggle_form_keys", extra={"keys": list(form.keys())})

    _validate_bitrix_origin(form)

    deal_id = _extract_deal_id(form)
    if not deal_id:
        logger.warning(
            "bitrix_bot_toggle_no_deal_id",
            extra={"pause": pause, "form_keys": list(form.keys())},
        )
        raise HTTPException(status_code=422, detail="No se pudo extraer deal_id del payload")

    phone = await _phone_from_deal(deal_id)
    if not phone:
        logger.warning(
            "bitrix_bot_toggle_phone_not_found",
            extra={"deal_id": deal_id, "pause": pause},
        )
        raise HTTPException(status_code=404, detail=f"No se encontró teléfono para deal_id={deal_id}")

    # No pausar si el deal ya está cerrado — evita que una regla de automatización
    # sobre un deal LOSE/WON bloquee conversaciones nuevas del mismo número.
    if pause:
        try:
            bitrix = BitrixClient()
            deal = await bitrix.get_deal(deal_id)
            stage = deal.get("STAGE_ID", "")
            if stage in ("C90:WON", "C90:LOSE"):
                logger.info(
                    "bitrix_bot_pause_ignorado_deal_cerrado",
                    extra={"deal_id": deal_id, "stage": stage, "phone_tail": phone[-4:]},
                )
                return {"status": "ignorado", "reason": "deal_cerrado", "stage": stage}
        except Exception as exc:
            logger.warning("bitrix_bot_pause_stage_check_error", extra={"deal_id": deal_id, "error": str(exc)})

    redis = await get_redis()
    action = "pausado" if pause else "activado"

    if pause:
        await redis.set(_redis_key(phone), "1")
    else:
        await redis.delete(_redis_key(phone))

    logger.info(
        "bitrix_bot_toggle",
        extra={"deal_id": deal_id, "phone_tail": phone[-4:], "action": action},
    )
    return {"status": "ok", "action": action, "deal_id": deal_id}


@router.post("/webhooks/bitrix/bot-pause")
async def bot_pause(request: Request) -> dict:
    """Pausa el bot para el número vinculado al deal. El asesor gestiona el chat."""
    return await _handle_toggle(request, pause=True)


@router.post("/webhooks/bitrix/bot-resume")
async def bot_resume(request: Request) -> dict:
    """Reactiva el bot para el número vinculado al deal."""
    return await _handle_toggle(request, pause=False)

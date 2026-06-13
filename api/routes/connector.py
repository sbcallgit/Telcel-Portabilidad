"""Webhook para recibir mensajes del asesor desde Bitrix24 Open Lines.

POST /webhooks/connector  →  Bitrix24 envía aquí el evento ONIMCONNECTORMESSAGEADD
                             cuando el asesor escribe en el chat de Open Lines.
El handler extrae el teléfono, deduplica, y reenvía el mensaje a WhatsApp.
"""

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from config.settings import settings
from integrations.redis_client import get_redis
from integrations.telegram.client import TelegramClient
from integrations.whatsapp.client import WhatsAppClient

router = APIRouter()
logger = logging.getLogger(__name__)

_wa = WhatsAppClient()
_tg = TelegramClient()


async def _extract_app_token(request: Request, json_payload: dict | None) -> str:
    """Obtiene el application_token de Bitrix desde query param, body JSON o form.

    Bitrix lo envía de formas distintas según la configuración del handler;
    se cubren las ubicaciones conocidas.
    """
    tok = request.query_params.get("application_token", "")
    if tok:
        return tok
    if isinstance(json_payload, dict):
        auth = json_payload.get("auth") or {}
        tok = str(json_payload.get("application_token", "") or (auth.get("application_token", "") if isinstance(auth, dict) else ""))
        if tok:
            return tok
    try:
        form = await request.form()
        return form.get("application_token", "") or form.get("auth[application_token]", "")
    except Exception:
        return ""


async def _forward_to_user(phone: str, text: str) -> None:
    """Reenvía el mensaje del asesor al canal correcto según el origen del usuario."""
    if phone.startswith("tg_"):
        chat_id = phone.replace("tg_", "")
        await _tg.send_message(chat_id, text)
    else:
        await _wa.send_message(phone, text)


def _extract_phone_from_chat_id(chat_id: str) -> str:
    """Extrae el número de teléfono del external_chat_id con formato 'wa_{phone}_{ts}'."""
    if not chat_id.startswith("wa_"):
        return ""
    parts = chat_id.split("_")
    # Formato: wa_{phone}_{timestamp} → parts[1] es el phone
    if len(parts) >= 3:
        return parts[1]
    return ""


@router.post("/webhooks/connector")
async def connector_incoming(request: Request) -> dict:
    """Recibe mensajes del asesor desde Bitrix24 y los reenvía al usuario por WhatsApp."""
    # ── Autenticación (F-05): application_token de Bitrix, fail-closed ──────────
    # Sin token configurado el endpoint queda deshabilitado (el camino activo es
    # el polling en connector_poll.py, que no depende de este webhook).
    if not settings.bitrix_application_token:
        logger.error("connector_application_token_not_configured")
        raise HTTPException(status_code=503, detail="connector disabled: token not configured")

    try:
        payload = await request.json()
    except Exception:
        payload = None

    token = await _extract_app_token(request, payload)
    if not token or not hmac.compare_digest(token, settings.bitrix_application_token):
        logger.warning("connector_incoming_unauthorized")
        raise HTTPException(status_code=401, detail="unauthorized")

    if payload is None:
        return {"status": "invalid_json"}

    data = payload.get("data", {})
    connector = data.get("CONNECTOR", "")

    # Ignorar eventos de otros conectores
    if connector and connector != settings.bitrix_connector_id:
        return {"status": "ignored"}

    messages = data.get("MESSAGES", [])
    chat_info = data.get("CHAT", {})
    external_chat_id = chat_info.get("id", "") or chat_info.get("ID", "")

    if not messages or not external_chat_id:
        return {"status": "no_messages"}

    phone = _extract_phone_from_chat_id(external_chat_id)
    if not phone:
        logger.warning("connector_incoming_no_phone", extra={"chat_id": external_chat_id})
        return {"status": "no_phone"}

    redis = await get_redis()
    forwarded = 0

    for msg in messages:
        msg_id = str(msg.get("id", ""))
        text = msg.get("text", "").strip()
        author_id = str(msg.get("author_id", "") or msg.get("user_id", ""))

        if not text or not msg_id:
            continue

        # Solo procesar mensajes de operadores (no del bot ni del usuario)
        # En Bitrix, los mensajes del connector-user tienen author_id numérico (usuario de Bitrix)
        # Los mensajes del cliente tienen author_id == phone
        if author_id == phone or author_id == "vera_bot":
            continue

        # Deduplicación: evitar reenviar si ya fue entregado por el push o por polling anterior
        dedup_key = f"connector_delivered:{msg_id}"
        already = await redis.get(dedup_key)
        if already:
            logger.info("connector_msg_deduplicated", extra={"msg_id": msg_id})
            continue

        try:
            await _forward_to_user(phone, text)
            await redis.set(dedup_key, "1", ex=86400)  # TTL 24h
            forwarded += 1
            logger.info(
                "connector_asesor_forwarded",
                extra={"phone_tail": phone[-4:], "msg_id": msg_id},
            )
        except Exception as exc:
            logger.error(
                "connector_forward_error",
                extra={"phone_tail": phone[-4:], "error": str(exc)},
            )

    return {"status": "ok", "forwarded": forwarded}

"""Webhook de WhatsApp Business (Meta).

GET  /webhooks/telcel  → verificación del webhook (handshake inicial con Meta)
POST /webhooks/telcel  → mensajes entrantes: valida firma, acumula con debounce,
                         procesa con el agente, responde por WhatsApp y espeja
                         en Bitrix Open Lines.

Flujo de debounce:
  1. El webhook valida firma, deduplica y espeja el mensaje del usuario en Bitrix.
  2. Encola el texto en el buffer de debounce (Redis) y retorna 200 de inmediato.
  3. Tras DEBOUNCE_WINDOW_MS ms sin nuevos mensajes del mismo número, un
     asyncio.Task drena el buffer, combina los textos y corre el agente.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import AIMessage, HumanMessage

from agents.portabilidad.graph import get_agent_graph
from config.settings import settings
from integrations import debounce
from integrations.bitrix import connector as bitrix_connector
from integrations.redis_client import get_redis
from integrations.whatsapp.client import WhatsAppClient
from integrations.whatsapp.handlers import parse_whatsapp_message, verify_webhook_signature

router = APIRouter()
logger = logging.getLogger(__name__)

_wa = WhatsAppClient()


async def _process_message(phone: str, text: str) -> None:
    """Callback que recibe el texto ya agrupado y corre el agente."""
    config = {"configurable": {"thread_id": phone}}
    try:
        result = await get_agent_graph().ainvoke(
            {
                "messages": [HumanMessage(content=text)],
                "session_id": phone,
                "customer_phone": phone,
            },
            config=config,
        )
    except Exception as exc:
        logger.error("agent_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        await _wa.send_message(phone, "Hubo un problema procesando tu mensaje. Por favor intenta de nuevo.")
        return

    # Extraer mensajes nuevos del agente (evitar repetir los ya enviados)
    all_messages = result.get("messages", [])
    new_ai_messages = []
    for msg in reversed(all_messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, AIMessage) and msg.content and msg.content != "(procesando objeción)":
            new_ai_messages.insert(0, msg)

    for ai_msg in new_ai_messages:
        content = str(ai_msg.content)
        try:
            await _wa.send_message(phone, content)
            logger.info("whatsapp_message_sent", extra={"phone_tail": phone[-4:]})
        except Exception as exc:
            logger.error("whatsapp_send_error", extra={"phone_tail": phone[-4:], "error": str(exc)})

        try:
            await bitrix_connector.send_bot_message(phone, content)
        except Exception as exc:
            logger.error("connector_bot_msg_failed", extra={"error": str(exc)})


@router.get("/webhooks/telcel", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> str:
    """Verificación del webhook de Meta (handshake inicial)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("webhook_verified")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhooks/telcel", status_code=200)
async def receive_message(request: Request) -> dict:
    """Recibe mensajes de WhatsApp, los acumula con debounce y responde."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if settings.whatsapp_app_secret:
        if not verify_webhook_signature(body, signature, settings.whatsapp_app_secret):
            logger.warning("webhook_signature_invalid")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        import json
        payload = json.loads(body)
    except Exception:
        return {"status": "invalid_json"}

    parsed = parse_whatsapp_message(payload)
    if parsed is None:
        return {"status": "ignored"}

    phone, text, message_id = parsed

    # Deduplicación: WhatsApp puede entregar el mismo mensaje dos veces
    redis = await get_redis()
    dedup_key = f"wa_processed:{message_id}"
    if await redis.get(dedup_key):
        logger.info("webhook_duplicate_message", extra={"message_id": message_id})
        return {"status": "duplicate"}
    await redis.set(dedup_key, "1", ex=60)

    logger.info("webhook_message_received", extra={"phone_tail": phone[-4:], "bytes": len(body)})

    # Marcar como leído inmediatamente (muestra doble check azul al usuario)
    await _wa.mark_as_read(message_id)

    # Espejear mensaje del usuario en Bitrix Open Lines (por mensaje, no por turno)
    try:
        await bitrix_connector.send_user_message(phone, text)
    except Exception as exc:
        logger.error("connector_user_msg_failed", extra={"error": str(exc)})

    # Encolar con debounce — retorna inmediatamente; el agente corre en background
    await debounce.enqueue(phone, text, settings.debounce_window_ms, _process_message)

    return {"status": "ok"}

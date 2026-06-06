import logging

from fastapi import APIRouter, HTTPException, Query, Request
from langchain_core.messages import AIMessage, HumanMessage

from agents.portabilidad.graph import agent_graph
from config.settings import settings
from integrations.bitrix import connector as bitrix_connector
from integrations.telegram.client import TelegramClient
from integrations.telegram.handlers import parse_update

router = APIRouter()
logger = logging.getLogger(__name__)

_tg = TelegramClient()


@router.post("/webhooks/telegram", status_code=200)
async def telegram_webhook(request: Request) -> dict:
    """Recibe updates de Telegram, valida el secret y procesa con el agente."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.telegram_webhook_secret:
        logger.warning("telegram_webhook_invalid_secret")
        raise HTTPException(status_code=401, detail="Invalid secret")

    payload = await request.json()
    msg = parse_update(payload)

    if msg is None:
        return {"status": "ignored"}

    logger.info("telegram_message_received", extra={"chat_id": msg.chat_id, "text_len": len(msg.text)})

    # Espejear mensaje del usuario en Bitrix Open Lines
    try:
        await bitrix_connector.send_user_message(msg.phone, msg.text)
    except Exception as exc:
        logger.error("connector_user_msg_failed", extra={"error": str(exc)})

    config = {"configurable": {"thread_id": str(msg.chat_id)}}

    try:
        result = await agent_graph.ainvoke(
            {
                "messages": [HumanMessage(content=msg.text)],
                "session_id": str(msg.chat_id),
                "customer_phone": msg.phone,
            },
            config=config,
        )

        # Enviar solo las burbujas nuevas (AIMessages después del último HumanMessage)
        all_messages = result.get("messages", [])
        new_ai: list[AIMessage] = []
        for m in reversed(all_messages):
            if isinstance(m, HumanMessage):
                break
            if isinstance(m, AIMessage) and m.content and m.content != "(procesando objeción)":
                new_ai.insert(0, m)

        for ai_msg in new_ai:
            content = str(ai_msg.content)
            try:
                await _tg.send_message(msg.chat_id, content)
            except Exception as send_exc:
                logger.error("telegram_send_error", extra={"error": str(send_exc), "chat_id": msg.chat_id})
                break
            # Espejear respuesta del bot en Bitrix
            try:
                await bitrix_connector.send_bot_message(msg.phone, content)
            except Exception as exc:
                logger.error("connector_bot_msg_failed", extra={"error": str(exc)})

    except Exception as exc:
        logger.error("agent_error", extra={"error": str(exc), "chat_id": msg.chat_id})
        try:
            await _tg.send_message(msg.chat_id, "Hubo un problema técnico. Intenta de nuevo en un momento.")
        except Exception:
            pass  # No podemos enviar el error si el canal está caído

    return {"status": "ok"}


@router.post("/webhooks/telegram/setup")
async def setup_telegram_webhook(
    url: str = Query(description="URL pública del webhook, ej: https://telegram-portabilidad.callcomcc.io"),
) -> dict:
    """Registra el webhook en Telegram. Llamar una vez al configurar el entorno."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN no configurado en .env")

    full_url = f"{url.rstrip('/')}/webhooks/telegram"
    result = await _tg.set_webhook(full_url)
    return {"webhook_url": full_url, "telegram_response": result}


@router.get("/webhooks/telegram/info")
async def telegram_bot_info() -> dict:
    """Verifica que el token es válido y retorna la info del bot."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN no configurado en .env")
    return await _tg.get_me()

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from config.settings import settings
from integrations.telegram.client import TelegramClient
from integrations.telegram.handlers import parse_update

router = APIRouter()
logger = logging.getLogger(__name__)

_tg = TelegramClient()


@router.post("/webhooks/telegram", status_code=200)
async def telegram_webhook(request: Request) -> dict:
    """Recibe updates de Telegram. Valida el secret y procesa el mensaje."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.telegram_webhook_secret:
        logger.warning("telegram_webhook_invalid_secret")
        raise HTTPException(status_code=401, detail="Invalid secret")

    payload = await request.json()
    msg = parse_update(payload)

    if msg is None:
        return {"status": "ignored"}

    logger.info(
        "telegram_message_received",
        extra={"chat_id": msg.chat_id, "text_len": len(msg.text)},
    )

    # TODO Día 3: enrutar al agente LangGraph con msg.phone como session_id
    # Por ahora el bot hace eco para confirmar que el canal funciona
    await _tg.send_message(msg.chat_id, f"[PRUEBA] Recibí: {msg.text}")

    return {"status": "ok"}


@router.post("/webhooks/telegram/setup")
async def setup_telegram_webhook(
    url: str = Query(description="URL pública del webhook, ej: https://abc.ngrok.io"),
) -> dict:
    """Registra el webhook en Telegram. Llamar una vez al configurar el bot.

    Requiere una URL pública (usar ngrok en desarrollo local).
    Ejemplo: POST /webhooks/telegram/setup?url=https://abc.ngrok.io
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN no configurado en .env")

    full_url = f"{url.rstrip('/')}/webhooks/telegram"
    result = await _tg.set_webhook(full_url)
    return {"webhook_url": full_url, "telegram_response": result}


@router.get("/webhooks/telegram/info")
async def telegram_bot_info() -> dict:
    """Retorna la información del bot y verifica que el token es válido."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN no configurado en .env")
    return await _tg.get_me()

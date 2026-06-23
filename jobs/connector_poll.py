"""Polling de mensajes del asesor desde Bitrix24 Open Lines.

Cada 30 segundos revisa todos los chats activos en Redis y reenvía
al usuario (Telegram o WhatsApp) los mensajes nuevos del asesor humano.

Deduplicación integrada: clave 'connector_delivered:{msg_id}' evita reenvíos.
"""

import asyncio
import logging

from integrations.redis_client import get_redis
from integrations.telegram.client import TelegramClient
from integrations.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

_wa = WhatsAppClient()
_tg = TelegramClient()
_poll_task: asyncio.Task | None = None  # type: ignore[type-arg]

POLL_INTERVAL = 30


async def _forward_to_user(phone: str, text: str) -> None:
    if phone.startswith("tg_"):
        chat_id = phone.removeprefix("tg_")
        await _tg.send_message(chat_id, text)
    else:
        await _wa.send_message(phone, text)


_BOT_COMMANDS: dict[str, bool] = {
    "desactivar bot": True,
    "pausar bot":     True,
    "activar bot":    False,
    "reactivar bot":  False,
}


async def _handle_bot_command(phone: str, text: str, msg_id: str, redis: object) -> bool:
    """Intercepta comandos del asesor. Retorna True si el mensaje es un comando (no reenviar)."""
    cmd = text.strip().lower()
    if cmd not in _BOT_COMMANDS:
        return False

    pause = _BOT_COMMANDS[cmd]
    key = f"bot_pausado:{phone}"

    if pause:
        await redis.set(key, "1")  # type: ignore[union-attr]
        action = "pausado"
    else:
        await redis.delete(key)  # type: ignore[union-attr]
        action = "activado"

    logger.info(
        "bot_command_from_asesor",
        extra={"phone_tail": phone[-4:], "comando": cmd, "action": action, "msg_id": msg_id},
    )
    return True


async def _poll_phone(phone: str, chat_id: str, redis: object) -> None:
    from integrations.bitrix.connector import poll_asesor_messages
    try:
        messages = await poll_asesor_messages(phone, chat_id)
    except Exception as exc:
        logger.error("poll_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return

    for msg_id, text, author_id in messages:
        dedup_key = f"connector_delivered:{msg_id}"
        if await redis.get(dedup_key):  # type: ignore[union-attr]
            continue
        try:
            # Comandos internos del asesor — no se reenvían al usuario
            if await _handle_bot_command(phone, text, msg_id, redis):
                await redis.setex(dedup_key, 86400, "1")  # type: ignore[union-attr]
                continue

            await _forward_to_user(phone, text)
            await redis.setex(dedup_key, 86400, "1")  # type: ignore[union-attr]
            logger.info("asesor_msg_forwarded", extra={
                "phone_tail": phone[-4:],
                "msg_id": msg_id,
                "author_id": author_id,
            })

            async def _log_humano(p: str, t: str, mid: str, aid: int) -> None:
                from jobs.kpi_eventos import log_mensaje_evento
                await log_mensaje_evento(
                    p, t, "humano",
                    message_id=mid,
                    autor_bitrix_id=str(aid),
                )

            asyncio.create_task(_log_humano(phone, text, msg_id, author_id))
        except Exception as exc:
            logger.error("forward_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def _poll_once() -> None:
    import asyncio

    redis = await get_redis()
    keys = await redis.keys("connector_chat:*")
    if not keys:
        return

    tasks = []
    for key in keys:
        phone = key.removeprefix("connector_chat:")
        chat_id = await redis.get(f"connector_chat:{phone}")
        if chat_id:
            tasks.append(_poll_phone(phone, chat_id, redis))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _poll_loop() -> None:
    """Bucle continuo de polling cada POLL_INTERVAL segundos."""
    logger.info("connector_poll_started", extra={"interval": POLL_INTERVAL})
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("connector_poll_loop_error", extra={"error": str(exc)})
        await asyncio.sleep(POLL_INTERVAL)
    logger.info("connector_poll_stopped")


async def start_connector_poll() -> None:
    """Inicia el polling en background. Llamar desde el lifespan de FastAPI."""
    global _poll_task
    if _poll_task is None or _poll_task.done():
        _poll_task = asyncio.create_task(_poll_loop())
        logger.info("connector_poll_task_created")


async def stop_connector_poll() -> None:
    """Detiene el polling. Llamar desde el lifespan de FastAPI al cerrar."""
    global _poll_task
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    _poll_task = None

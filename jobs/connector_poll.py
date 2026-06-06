"""Polling fallback para mensajes del asesor desde Bitrix24 Open Lines.

Cuando Cloudflare u otro proxy bloquea el push de ONIMCONNECTORMESSAGEADD,
este job consulta los diálogos activos cada 30 segundos y reenvía a WhatsApp
los mensajes del asesor que aún no fueron entregados.

Deduplicación integrada: si el mensaje ya fue entregado por el webhook push
(clave 'connector_delivered:{msg_id}' en Redis), el polling lo omite.
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


async def _forward_to_user(phone: str, text: str) -> None:
    if phone.startswith("tg_"):
        chat_id = phone.replace("tg_", "")
        await _tg.send_message(chat_id, text)
    else:
        await _wa.send_message(phone, text)

POLL_INTERVAL = 30  # segundos


def _extract_phone_from_session_key(key: str) -> str:
    """Extrae phone de la clave Redis 'connector_session:{phone}'."""
    prefix = "connector_session:"
    if key.startswith(prefix):
        return key[len(prefix):]
    return ""


async def _poll_once() -> None:
    """Una iteración del polling: revisa todos los diálogos activos."""
    redis = await get_redis()

    # Obtener todas las sesiones activas
    keys = await redis.keys("connector_session:*")
    if not keys:
        return

    from integrations.bitrix.connector import get_dialog_messages

    for key in keys:
        phone = _extract_phone_from_session_key(key)
        if not phone:
            continue

        # Obtener el CHAT.ID interno de Bitrix para consultar los mensajes
        bitrix_chat_id = await redis.get(f"connector_chat:{phone}")
        if not bitrix_chat_id:
            continue

        # ID del último mensaje procesado (cursor de polling)
        last_id_raw = await redis.get(f"connector_last_msg:{phone}")
        last_id = int(last_id_raw) if last_id_raw else 0

        try:
            messages = await get_dialog_messages(bitrix_chat_id, last_id)
        except Exception as exc:
            logger.error("poll_get_messages_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
            continue

        max_id = last_id
        for msg in messages:
            msg_id = str(msg.get("id", ""))
            text = str(msg.get("text", "") or msg.get("TEXT", "")).strip()
            author_id = str(msg.get("author_id", "") or msg.get("AUTHOR_ID", ""))

            if not msg_id or not text:
                continue

            # Actualizar cursor
            try:
                max_id = max(max_id, int(msg_id))
            except ValueError:
                pass

            # Solo mensajes de operadores Bitrix (no del cliente ni del bot)
            if author_id == phone or author_id == "vera_bot":
                continue

            # Deduplicación con el webhook push
            dedup_key = f"connector_delivered:{msg_id}"
            if await redis.get(dedup_key):
                continue

            try:
                await _forward_to_user(phone, text)
                await redis.set(dedup_key, "1", ex=86400)
                logger.info(
                    "connector_poll_forwarded",
                    extra={"phone_tail": phone[-4:], "msg_id": msg_id},
                )
            except Exception as exc:
                logger.error(
                    "connector_poll_send_error",
                    extra={"phone_tail": phone[-4:], "error": str(exc)},
                )

        if max_id > last_id:
            await redis.set(f"connector_last_msg:{phone}", str(max_id))


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

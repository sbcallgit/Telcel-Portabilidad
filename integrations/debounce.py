"""Debounce de mensajes WhatsApp por número de teléfono.

Cuando el usuario manda varios mensajes seguidos (ej. "Hola" / "quiero info"
/ "sobre portabilidad"), los agrupa en uno solo antes de pasarlos al agente.

Mecanismo:
  - Cada mensaje se acumula en Redis: debounce:msgs:{phone}  (RPUSH)
  - Se sobreescribe un token único:   debounce:token:{phone} (SET con TTL)
  - Un asyncio.Task duerme DEBOUNCE_WINDOW_MS ms; al despertar compara
    su token con el almacenado en Redis.
    · Si coincide → es el último mensaje → drena la lista y llama al callback.
    · Si no coincide → llegó un mensaje más nuevo → termina silenciosamente.

Configuración (settings / .env):
  DEBOUNCE_WINDOW_MS=1500   # milisegundos de espera (0 = desactivado)
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from integrations.redis_client import get_redis

logger = logging.getLogger(__name__)

_KEY_MSGS = "debounce:msgs:{}"
_KEY_TOKEN = "debounce:token:{}"
_TTL_BUFFER = 300  # segundos máx. que vive un buffer huérfano en Redis

ProcessCallback = Callable[[str, str], Awaitable[None]]


async def enqueue(
    phone: str,
    text: str,
    window_ms: int,
    callback: ProcessCallback,
) -> None:
    """Encola *text* para *phone* con debounce de *window_ms* ms.

    Si window_ms <= 0 llama a callback de inmediato sin agrupar.
    El webhook puede hacer await de esta función y retornar 200 al instante;
    el procesamiento real ocurre en un asyncio.Task en background.
    """
    if window_ms <= 0:
        await callback(phone, text)
        return

    redis = await get_redis()
    token = str(uuid.uuid4())

    await redis.rpush(_KEY_MSGS.format(phone), text)
    await redis.set(_KEY_TOKEN.format(phone), token, ex=_TTL_BUFFER)

    asyncio.create_task(
        _flush_after(phone, token, window_ms / 1000.0, callback),
        name=f"debounce:{phone[-4:]}:{token[:8]}",
    )


async def _flush_after(
    phone: str,
    token: str,
    window_s: float,
    callback: ProcessCallback,
) -> None:
    await asyncio.sleep(window_s)

    redis = await get_redis()
    current = await redis.get(_KEY_TOKEN.format(phone))

    if current != token:
        # Llegó un mensaje más nuevo; ese task se encargará de procesar.
        return

    # Somos el último token: drenamos el buffer atómicamente.
    pipe = redis.pipeline()
    pipe.lrange(_KEY_MSGS.format(phone), 0, -1)
    pipe.delete(_KEY_MSGS.format(phone))
    pipe.delete(_KEY_TOKEN.format(phone))
    results = await pipe.execute()
    msgs: list[str] = results[0]

    if not msgs:
        return

    combined = "\n".join(msgs)
    logger.info(
        "debounce_flush",
        extra={"phone_tail": phone[-4:], "msg_count": len(msgs), "window_s": window_s},
    )
    try:
        await callback(phone, combined)
    except Exception:
        logger.exception("debounce_callback_error", extra={"phone_tail": phone[-4:]})

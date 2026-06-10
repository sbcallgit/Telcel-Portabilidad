"""Cliente para la API imconnector de Bitrix24.

Permite:
- Espejear mensajes del usuario (WhatsApp/Telegram → Bitrix Open Lines)
- Espejear respuestas de Vera (bot → Bitrix Open Lines, mismo chat)
- Recibir mensajes del asesor via polling
- Registrar y activar el conector en una línea abierta
"""

import asyncio
import logging
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import BitrixError
from integrations.redis_client import get_redis

logger = logging.getLogger(__name__)

_BITRIX_DOMAIN = "https://b24-ahyle8.bitrix24.mx"
_SESSION_TTL = 86_400        # 24 h — sesión imconnector (session_id, chat_id, deal_id)
_EXT_CHAT_TTL = 90 * 86_400  # 90 días — preserva el vínculo teléfono↔deal entre visitas


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def _call(method: str, params: dict) -> dict:
    """Llamada autenticada a la REST API de Bitrix24.

    El token se pasa en el body JSON como 'auth' (no como Bearer header) —
    es el formato que requiere imconnector.send.messages.
    """
    from integrations.bitrix.oauth import get_token
    token = await get_token()
    url = f"{_BITRIX_DOMAIN}/rest/{method}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={**params, "auth": token})
            resp.raise_for_status()
            data = resp.json()
            if error := data.get("error"):
                raise BitrixError(
                    f"{method} error [{error}]: {data.get('error_description', '')}",
                    retriable=False,
                )
            return data
    except httpx.HTTPStatusError as exc:
        raise BitrixError(
            f"Bitrix connector error {exc.response.status_code}",
            retriable=exc.response.status_code >= 500,
            original=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise BitrixError("Bitrix network error", retriable=True, original=exc) from exc


async def _get_or_create_external_chat_id(phone: str) -> str:
    """Devuelve el external_chat_id activo para el teléfono.

    Si no existe (nueva conversación) genera uno nuevo con timestamp para
    que Bitrix cree una sesión y un deal vinculado al canal.
    """
    redis = await get_redis()
    key = f"connector_ext_chat:{phone}"
    existing = await redis.get(key)
    if existing:
        return existing
    new_id = f"{phone}_{int(time.time())}"
    await redis.setex(key, _EXT_CHAT_TTL, new_id)
    return new_id


async def _save_session(phone: str, session_id: str, chat_id: str, deal_id: str = "") -> None:
    redis = await get_redis()
    await redis.setex(f"connector_session:{phone}", _SESSION_TTL, session_id)
    if chat_id:
        await redis.setex(f"connector_chat:{phone}", _SESSION_TTL, chat_id)
    if deal_id:
        await redis.setex(f"connector_deal:{phone}", _SESSION_TTL, deal_id)


async def _get_session(phone: str) -> tuple[str, str]:
    """Retorna (session_id, chat_id) almacenados, o ('', '') si no existen."""
    redis = await get_redis()
    session_id = await redis.get(f"connector_session:{phone}") or ""
    chat_id = await redis.get(f"connector_chat:{phone}") or ""
    return session_id, chat_id


async def _fetch_openlines_deal_async(phone: str) -> None:
    """Espera 3s y busca el deal creado por Bitrix al abrir la sesión imconnector.

    Bitrix crea el deal de forma asíncrona; guardarlo en Redis antes de que el
    debounce (5s) dispare evita que validacion_node cree un deal fallback sin vínculo
    al canal Open Lines.
    """
    await asyncio.sleep(3)
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        deal_id = await bx.buscar_deal_por_telefono(phone)
        if deal_id:
            redis = await get_redis()
            await redis.setex(f"connector_deal:{phone}", _SESSION_TTL, deal_id)
            logger.info("connector_deal_id_saved_async", extra={
                "phone_tail": phone[-4:],
                "deal_id": deal_id,
            })
    except Exception as exc:
        logger.warning("connector_deal_id_fetch_failed", extra={
            "phone_tail": phone[-4:],
            "error": str(exc),
        })


async def send_user_message(phone: str, text: str) -> str | None:
    """Envía el mensaje del usuario a Bitrix Open Lines via imconnector.

    Retorna el session_id de Open Lines para poder espejear la respuesta del agente.
    """
    if not settings.bitrix_client_id or not settings.bitrix_connector_line_id:
        return None

    redis = await get_redis()
    is_new_session = not await redis.exists(f"connector_ext_chat:{phone}")

    external_chat_id = await _get_or_create_external_chat_id(phone)
    ts = int(time.time())

    try:
        result = await _call("imconnector.send.messages", {
            "CONNECTOR": settings.bitrix_connector_id,
            "LINE": settings.bitrix_connector_line_id,
            "MESSAGES": [{
                "user": {
                    "id": phone,
                    "name": f"WhatsApp *{phone[-4:]}",
                    "phone": phone,
                },
                "message": {
                    "id": f"wa_{phone}_{ts}",
                    "date": ts,
                    "text": text,
                },
                "chat": {
                    "id": external_chat_id,
                    "name": f"WA {phone}",
                },
            }],
        })

        items = result.get("result", {}).get("DATA", {}).get("RESULT", [])
        session_data = items[0].get("session", {}) if items else {}
        session_id = str(session_data.get("ID", ""))
        chat_id = str(session_data.get("CHAT_ID", ""))
        deal_id = str(session_data.get("CRM_ENTITY_ID", "")) if session_data.get("CRM_ENTITY_TYPE") == "DEAL" else ""

        if session_id:
            await _save_session(phone, session_id, chat_id, deal_id)

        logger.info("connector_user_msg_sent", extra={
            "phone_tail": phone[-4:],
            "session_id": session_id,
            "chat_id": chat_id,
            "deal_id": deal_id or "not_in_response",
        })

        # Cuando Bitrix no devuelve CRM_ENTITY_ID en la respuesta, lo crea de forma
        # asíncrona. Si es una sesión nueva, buscar el deal en background para guardarlo
        # en Redis antes de que el debounce dispare (5s) y validacion_node lo use.
        if is_new_session and not deal_id:
            asyncio.create_task(_fetch_openlines_deal_async(phone))

        return session_id or None

    except Exception as exc:
        logger.error("connector_user_msg_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return None


async def send_bot_message(phone: str, text: str) -> None:
    """Espeja la respuesta de Vera en el chat de Open Lines vía imconnector.

    Usa el MISMO user.id que el usuario real para que el mensaje quede en la
    misma sesión de Open Lines y no genere un segundo deal. El prefijo "🤖 Vera |"
    distingue visualmente las respuestas del bot en el chat del asesor.
    """
    if not settings.bitrix_client_id or not settings.bitrix_connector_line_id:
        return

    redis = await get_redis()
    ext_chat_id = await redis.get(f"connector_ext_chat:{phone}")
    if not ext_chat_id:
        return

    ts = int(time.time())
    try:
        await _call("imconnector.send.messages", {
            "CONNECTOR": settings.bitrix_connector_id,
            "LINE": settings.bitrix_connector_line_id,
            "MESSAGES": [{
                "user": {
                    "id": phone,
                    "name": f"WhatsApp *{phone[-4:]}",
                    "phone": phone,
                },
                "message": {
                    "id": f"bot_{phone}_{ts}",
                    "date": ts,
                    "text": f"🤖 Vera | {text}",
                },
                "chat": {
                    "id": ext_chat_id,
                    "name": f"WA {phone}",
                },
            }],
        })
        logger.info("connector_bot_msg_sent", extra={"phone_tail": phone[-4:]})
    except Exception as exc:
        logger.error("connector_bot_msg_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def _call_poll(method: str, params: dict) -> dict:
    """Llamada sin reintentos para operaciones de polling best-effort."""
    from integrations.bitrix.oauth import get_token
    token = await get_token()
    url = f"{_BITRIX_DOMAIN}/rest/{method}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json={**params, "auth": token})
        resp.raise_for_status()
        return resp.json()


async def poll_asesor_messages(phone: str, chat_id: str) -> list[tuple[str, str, int]]:
    """Lee mensajes nuevos del asesor en el chat via im.dialog.messages.get.

    Retorna lista de (msg_id, text, author_id) no vistos aún.
    """
    redis = await get_redis()
    last_key = f"connector_last_msg:{phone}"
    last_id = int(await redis.get(last_key) or "0")

    try:
        result = await _call_poll("im.dialog.messages.get", {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": 20,
        })
        messages = result.get("result", {}).get("messages", [])

        # Primera vez: sembrar el puntero sin reenviar histórico
        if last_id == 0 and messages:
            max_existing = max(int(m.get("id", 0)) for m in messages)
            await redis.setex(last_key, _SESSION_TTL, str(max_existing))
            return []

        new_items: list[tuple[str, str, int]] = []
        max_id = last_id

        for msg in reversed(messages):
            msg_id = int(msg.get("id", 0))
            if msg_id <= last_id:
                continue
            if msg_id > max_id:
                max_id = msg_id

            author_id = msg.get("author_id", 0)
            params = msg.get("params", {})

            if author_id == 0:
                continue
            # Saltar mensajes del cliente (tienen CONNECTOR_MID)
            if isinstance(params, dict) and params.get("CONNECTOR_MID"):
                continue

            text = (msg.get("text") or "").strip()
            if text:
                new_items.append((str(msg_id), text, int(author_id)))

        if max_id > last_id:
            await redis.setex(last_key, _SESSION_TTL, str(max_id))

        return new_items
    except Exception as exc:
        logger.error("connector_poll_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return []


async def get_all_active_chats() -> list[tuple[str, str]]:
    """Retorna lista de (phone, chat_id) para todos los chats activos."""
    redis = await get_redis()
    keys = await redis.keys("connector_chat:*")
    result = []
    for key in keys:
        phone = key.replace("connector_chat:", "")
        chat_id = await redis.get(key)
        if chat_id:
            result.append((phone, chat_id))
    return result


async def register_connector() -> bool:
    """Registra el conector en Bitrix24."""
    try:
        result = await _call("imconnector.register", {
            "ID": settings.bitrix_connector_id,
            "NAME": "WhatsApp Vera Bot",
            "ICON": {"COLOR": "#25D366"},
        })
        return bool(result.get("result"))
    except Exception as exc:
        logger.error("connector_register_error", extra={"error": str(exc)})
        return False


async def activate_line(line_id: str) -> bool:
    """Activa el conector en un Open Channel."""
    try:
        result = await _call("imconnector.activate", {
            "CONNECTOR": settings.bitrix_connector_id,
            "LINE": line_id,
            "ACTIVE": True,
        })
        return bool(result.get("result"))
    except Exception as exc:
        logger.error("connector_activate_error", extra={"error": str(exc)})
        return False


async def subscribe_event(handler_url: str) -> bool:
    """Suscribe el evento ONIMCONNECTORMESSAGEADD al endpoint del servidor."""
    try:
        result = await _call("event.bind", {
            "event": "ONIMCONNECTORMESSAGEADD",
            "handler": handler_url,
        })
        return bool(result.get("result"))
    except Exception as exc:
        error_msg = str(exc)
        if "already" in error_msg.lower():
            return True
        logger.error("connector_subscribe_error", extra={"error": error_msg})
        return False


async def get_connector_status() -> dict:
    """Verifica el estado del conector."""
    try:
        return await _call("imconnector.status", {
            "CONNECTOR": settings.bitrix_connector_id,
            "LINE": settings.bitrix_connector_line_id,
        })
    except Exception as exc:
        return {"error": str(exc)}


async def list_open_lines() -> list[dict]:
    """Lista los Open Channels disponibles."""
    try:
        result = await _call("imopenlines.config.get", {"PARAMS": {}})
        lines = result.get("result", [])
        return lines if isinstance(lines, list) else []
    except Exception as exc:
        logger.error("connector_list_lines_error", extra={"error": str(exc)})
        return []

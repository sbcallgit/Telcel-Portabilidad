"""Cliente para la API imconnector de Bitrix24.

Permite:
- Espejear mensajes del usuario (WhatsApp → Bitrix Open Lines)
- Espejear respuestas del bot (Vera → Bitrix Open Lines, mismo CHAT.ID)
- Registrar y configurar el conector personalizado
- Suscribir el evento ONIMCONNECTORMESSAGEADD para recibir mensajes del asesor
"""

import json
import logging
import time

import httpx
from tenacity import retry, reraise, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import BitrixError
from integrations.redis_client import get_redis

logger = logging.getLogger(__name__)

_BITRIX_DOMAIN = "https://b24-ahyle8.bitrix24.mx"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def _call(method: str, params: dict) -> dict:
    """Llamada autenticada a la REST API de Bitrix24 vía OAuth."""
    from integrations.bitrix.oauth import get_token
    token = await get_token()
    url = f"{_BITRIX_DOMAIN}/rest/{method}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=params, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise BitrixError(
            f"Bitrix connector error {exc.response.status_code}",
            retriable=exc.response.status_code >= 500,
            original=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise BitrixError("Bitrix network error", retriable=True, original=exc) from exc


async def _get_session(phone: str) -> str:
    """Devuelve el external_chat_id activo para el teléfono, o cadena vacía si no existe."""
    redis = await get_redis()
    return await redis.get(f"connector_session:{phone}") or ""


async def _save_session(phone: str, external_chat_id: str, bitrix_chat_id: str) -> None:
    """Persiste el external_chat_id y el CHAT.ID interno de Bitrix en Redis."""
    redis = await get_redis()
    # Sin TTL — la sesión dura mientras no se reinicie explícitamente
    await redis.set(f"connector_session:{phone}", external_chat_id)
    if bitrix_chat_id:
        await redis.set(f"connector_chat:{phone}", bitrix_chat_id)


async def send_user_message(phone: str, text: str) -> None:
    """Envía el mensaje del usuario a Bitrix Open Lines.

    Si no existe sesión activa, crea una nueva. El CHAT.ID retornado por Bitrix
    se guarda en Redis para reutilizarlo en send_bot_message.
    """
    if not settings.bitrix_client_id or not settings.bitrix_connector_line_id:
        return

    external_chat_id = await _get_session(phone)
    if not external_chat_id:
        external_chat_id = f"wa_{phone}_{int(time.time())}"

    ts = int(time.time())
    params = {
        "CONNECTOR": settings.bitrix_connector_id,
        "LINE": settings.bitrix_connector_line_id,
        "MESSAGES": [
            {
                "CONNECTOR_MID": f"wa_{phone}_{ts}",
                "TIMESTAMP": ts,
                "TEXT": text,
                "USER": {
                    "ID": phone,
                    "NAME": f"WhatsApp *{phone[-4:]}",
                    "AVATAR": "",
                },
                "CHAT": {"ID": external_chat_id},
            }
        ],
    }

    try:
        result = await _call("imconnector.send.messages", params)
        # Bitrix devuelve el CHAT.ID interno en result["result"]["CHAT"]["ID"]
        bitrix_chat_id = ""
        try:
            bitrix_chat_id = str(result["result"]["CHAT"]["ID"])
        except (KeyError, TypeError):
            pass
        await _save_session(phone, external_chat_id, bitrix_chat_id)
        logger.info("connector_user_msg_sent", extra={"phone_tail": phone[-4:], "chat_id": external_chat_id})
    except Exception as exc:
        logger.error("connector_user_msg_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def send_bot_message(phone: str, text: str) -> None:
    """Espeja la respuesta de Vera en la misma sesión de Open Lines del usuario.

    Usa el mismo CHAT.ID que send_user_message para evitar crear un deal duplicado.
    Falla silenciosamente si no hay sesión activa (el mensaje del usuario no se procesó antes).
    """
    if not settings.bitrix_client_id or not settings.bitrix_connector_line_id:
        return

    external_chat_id = await _get_session(phone)
    if not external_chat_id:
        return  # Sin sesión activa, no hay dónde espejear

    ts = int(time.time())
    params = {
        "CONNECTOR": settings.bitrix_connector_id,
        "LINE": settings.bitrix_connector_line_id,
        "MESSAGES": [
            {
                "CONNECTOR_MID": f"vera_{phone}_{ts}",
                "TIMESTAMP": ts,
                "TEXT": text,
                "USER": {
                    "ID": "vera_bot",
                    "NAME": "Vera (Bot)",
                    "AVATAR": "",
                },
                "CHAT": {"ID": external_chat_id},
            }
        ],
    }

    try:
        await _call("imconnector.send.messages", params)
        logger.info("connector_bot_msg_sent", extra={"phone_tail": phone[-4:]})
    except Exception as exc:
        logger.error("connector_bot_msg_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def register_connector() -> bool:
    """Registra el conector personalizado en Bitrix24."""
    try:
        result = await _call(
            "imconnector.register",
            {
                "ID": settings.bitrix_connector_id,
                "NAME": "WhatsApp Vera Bot",
                "ICON": {
                    "DATA_IMAGE": "",
                    "COLOR": "#25D366",
                },
            },
        )
        return bool(result.get("result"))
    except Exception as exc:
        logger.error("connector_register_error", extra={"error": str(exc)})
        return False


async def activate_line(line_id: str) -> bool:
    """Activa el conector en un Open Channel."""
    try:
        result = await _call(
            "imconnector.activate",
            {"CONNECTOR": settings.bitrix_connector_id, "LINE": line_id, "ACTIVE": True},
        )
        return bool(result.get("result"))
    except Exception as exc:
        logger.error("connector_activate_error", extra={"error": str(exc)})
        return False


async def set_connector_data() -> bool:
    """Configura los datos del conector (nombre visible, URL, etc.)."""
    try:
        result = await _call(
            "imconnector.set.connector.data",
            {
                "CONNECTOR": settings.bitrix_connector_id,
                "LINE": settings.bitrix_connector_line_id,
                "DATA": {
                    "TITLE": "WhatsApp Vera Bot",
                    "LINK": settings.bitrix_public_url,
                },
            },
        )
        return bool(result.get("result"))
    except Exception as exc:
        logger.error("connector_set_data_error", extra={"error": str(exc)})
        return False


async def subscribe_event(handler_url: str) -> bool:
    """Suscribe el evento ONIMCONNECTORMESSAGEADD al endpoint del servidor."""
    try:
        result = await _call(
            "event.bind",
            {
                "event": "ONIMCONNECTORMESSAGEADD",
                "handler": handler_url,
            },
        )
        return bool(result.get("result"))
    except Exception as exc:
        error_msg = str(exc)
        if "already binded" in error_msg.lower() or "handler already" in error_msg.lower():
            logger.info("connector_event_already_bound")
            return True
        logger.error("connector_subscribe_error", extra={"error": error_msg})
        return False


async def get_connector_status() -> dict:
    """Verifica el estado del conector."""
    try:
        return await _call(
            "imconnector.status",
            {
                "CONNECTOR": settings.bitrix_connector_id,
                "LINE": settings.bitrix_connector_line_id,
            },
        )
    except Exception as exc:
        return {"error": str(exc)}


async def list_open_lines() -> list[dict]:
    """Lista los Open Channels disponibles en Bitrix24."""
    try:
        result = await _call("imopenlines.config.get", {"PARAMS": {}})
        lines = result.get("result", [])
        return lines if isinstance(lines, list) else []
    except Exception as exc:
        logger.error("connector_list_lines_error", extra={"error": str(exc)})
        return []


async def get_dialog_messages(dialog_id: str, last_id: int = 0) -> list[dict]:
    """Obtiene mensajes del diálogo de Open Lines para el polling del asesor."""
    try:
        result = await _call(
            "im.dialog.messages.get",
            {"DIALOG_ID": f"chat{dialog_id}", "LAST_ID": last_id, "LIMIT": 50},
        )
        messages = result.get("result", {}).get("messages", [])
        return messages if isinstance(messages, list) else []
    except Exception as exc:
        logger.error("connector_get_dialog_error", extra={"dialog_id": dialog_id, "error": str(exc)})
        return []

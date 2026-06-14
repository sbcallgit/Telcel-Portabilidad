"""Parseo de updates de Telegram al formato interno del bot."""

from dataclasses import dataclass


@dataclass
class TelegramMessage:
    chat_id: int
    user_id: int
    first_name: str
    text: str
    message_id: int
    phone: str  # chat_id convertido a string — sirve como identificador de sesión


def parse_update(payload: dict) -> TelegramMessage | None:
    """Extrae los campos relevantes de un Telegram Update.

    Retorna None si el update no contiene un mensaje de texto (p.ej. foto, sticker).
    """
    message = payload.get("message")
    if not message:
        return None

    text = message.get("text", "")
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None

    chat = message.get("chat", {})
    from_user = message.get("from", {})
    chat_id = chat.get("id") or from_user.get("id")
    if not chat_id:
        return None

    return TelegramMessage(
        chat_id=chat_id,
        user_id=from_user.get("id", chat_id),
        first_name=from_user.get("first_name", ""),
        text=text,
        message_id=message.get("message_id", 0),
        # Usamos el chat_id como "número de teléfono" para identificar la sesión en el agente
        phone=f"tg_{chat_id}",
    )

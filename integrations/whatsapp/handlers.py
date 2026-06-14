import hashlib
import hmac


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Valida que el webhook viene realmente de Meta usando HMAC-SHA256.

    WhatsApp envía 'sha256=<hash>' en el header X-Hub-Signature-256.
    Cualquier divergencia rechaza la petición con 401.
    """
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_whatsapp_message(payload: dict | None) -> tuple[str, str, str] | None:
    """Extrae (phone, text, message_id) del payload de Meta.

    Retorna None para status updates, mensajes no-texto, o payloads malformados.
    """
    if not isinstance(payload, dict):
        return None

    try:
        entry = payload.get("entry", [])
        if not entry:
            return None
        changes = entry[0].get("changes", [])
        if not changes:
            return None
        value = changes[0].get("value", {})

        # Ignorar notificaciones de estado (leído, entregado, etc.)
        if "statuses" in value and "messages" not in value:
            return None

        messages = value.get("messages", [])
        if not messages:
            return None

        msg = messages[0]
        if msg.get("type") != "text":
            return None

        phone = msg.get("from", "")
        text = msg.get("text", {}).get("body", "").strip()
        message_id = msg.get("id", "")

        if not phone or not text or not message_id:
            return None

        return phone, text, message_id
    except (AttributeError, IndexError, KeyError, TypeError):
        return None

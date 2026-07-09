import hashlib
import hmac


def normalize_mx_phone(phone: str) -> str:
    """Normaliza un número mexicano al formato completo 521XXXXXXXXXX.

    La Cloud API de Meta reporta el remitente en 'from' con formato inconsistente
    para números mexicanos: a veces 10 dígitos sin código de país, a veces con
    '52' (sin el '1' móvil), a veces ya completo con '521'. Sin normalizar, el
    mismo contacto genera dos filas distintas en `leads` (una por cada formato)
    porque telefono es la clave del upsert y el thread_id de LangGraph.
    """
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        return "521" + digits
    if len(digits) == 12 and digits.startswith("52"):
        return "521" + digits[2:]
    return digits or phone


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Valida que el webhook viene realmente de Meta usando HMAC-SHA256.

    WhatsApp envía 'sha256=<hash>' en el header X-Hub-Signature-256.
    Cualquier divergencia rechaza la petición con 401.
    """
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_whatsapp_message(payload: dict) -> tuple[str, str, str, dict] | None:
    """Extrae (phone, text, message_id, referral) del payload de Meta.

    Retorna None para status updates, mensajes no-texto, o payloads malformados.
    El campo referral incluye source_id, source_type, ctwa_clid y source_url cuando
    el mensaje proviene de un anuncio Click-to-WhatsApp.
    """
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

        phone = normalize_mx_phone(msg.get("from", ""))
        text = msg.get("text", {}).get("body", "").strip()
        message_id = msg.get("id", "")

        if not phone or not text or not message_id:
            return None

        referral = msg.get("referral", {})

        return phone, text, message_id, referral
    except (IndexError, KeyError, TypeError):
        return None

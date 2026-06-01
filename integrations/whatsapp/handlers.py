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

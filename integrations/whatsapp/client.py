import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import WhatsAppError

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v20.0"


class WhatsAppClient:
    def __init__(self) -> None:
        self._phone_id = settings.whatsapp_phone_number_id
        self._token = settings.whatsapp_token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def send_message(self, to: str, text: str) -> dict:
        """Envía un mensaje de texto por WhatsApp Business."""
        url = f"{_BASE_URL}/{self._phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                response.raise_for_status()
                logger.info("whatsapp_message_sent", extra={"to": to[:4] + "****"})
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise WhatsAppError(
                f"WhatsApp API error {exc.response.status_code}",
                retriable=exc.response.status_code >= 500,
                original=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise WhatsAppError("WhatsApp network error", retriable=True, original=exc) from exc

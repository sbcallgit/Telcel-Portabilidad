import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from integrations.exceptions import IntegrationError

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org"


class TelegramError(IntegrationError):
    """Error al comunicarse con la API de Telegram."""


class TelegramClient:
    def __init__(self) -> None:
        self._token = settings.telegram_bot_token

    @property
    def _api_url(self) -> str:
        return f"{_BASE_URL}/bot{self._token}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def send_message(self, chat_id: int | str, text: str) -> dict:
        """Envía un mensaje de texto al chat de Telegram."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._api_url}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                )
                response.raise_for_status()
                logger.info("telegram_message_sent", extra={"chat_id": str(chat_id)})
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise TelegramError(
                f"Telegram API error {exc.response.status_code}",
                retriable=exc.response.status_code >= 500,
                original=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise TelegramError("Telegram network error", retriable=True, original=exc) from exc

    async def set_webhook(self, webhook_url: str) -> dict:
        """Registra el webhook en Telegram para recibir mensajes."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self._api_url}/setWebhook",
                json={
                    "url": webhook_url,
                    "secret_token": settings.telegram_webhook_secret,
                    "allowed_updates": ["message"],
                },
            )
            response.raise_for_status()
            result = response.json()
            logger.info("telegram_webhook_set", extra={"url": webhook_url, "ok": result.get("ok")})
            return result

    async def delete_webhook(self) -> dict:
        """Elimina el webhook (útil para cambiar a polling en desarrollo)."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self._api_url}/deleteWebhook")
            response.raise_for_status()
            return response.json()

    async def get_me(self) -> dict:
        """Retorna la información del bot — útil para verificar que el token es válido."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self._api_url}/getMe")
            response.raise_for_status()
            return response.json()

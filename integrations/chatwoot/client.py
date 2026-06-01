import logging

import httpx

from config.settings import settings
from integrations.exceptions import ChatwootError

logger = logging.getLogger(__name__)


class ChatwootClient:
    def __init__(self) -> None:
        self._base_url = settings.chatwoot_base_url.rstrip("/")
        self._api_key = settings.chatwoot_api_key
        self._inbox_id = settings.chatwoot_inbox_id

    @property
    def _headers(self) -> dict:
        return {"api_access_token": self._api_key, "Content-Type": "application/json"}

    async def create_conversation(self, contact_id: str, context: dict) -> dict:
        """Crea una conversación en Chatwoot con el contexto completo del lead.

        context debe incluir: nombre, numero_a_portar, compania_donante, municipio, promo_elegida.
        """
        url = f"{self._base_url}/api/v1/accounts/1/conversations"
        payload = {
            "contact_id": contact_id,
            "inbox_id": self._inbox_id,
            "additional_attributes": context,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self._headers)
                response.raise_for_status()
                logger.info("chatwoot_conversation_created", extra={"contact_id": contact_id})
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ChatwootError(
                f"Chatwoot API error {exc.response.status_code}", original=exc
            ) from exc
        except httpx.RequestError as exc:
            raise ChatwootError("Chatwoot network error", retriable=True, original=exc) from exc

    async def send_message(self, conversation_id: str, text: str) -> dict:
        """Envía un mensaje interno a la conversación (visible para el asesor)."""
        url = f"{self._base_url}/api/v1/accounts/1/conversations/{conversation_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={"content": text, "message_type": "outgoing", "private": True},
                    headers=self._headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ChatwootError(
                f"Chatwoot API error {exc.response.status_code}", original=exc
            ) from exc

    async def update_contact(self, contact_id: str, data: dict) -> dict:
        """Actualiza los datos del contacto en Chatwoot."""
        url = f"{self._base_url}/api/v1/accounts/1/contacts/{contact_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.patch(url, json=data, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ChatwootError(
                f"Chatwoot API error {exc.response.status_code}", original=exc
            ) from exc

"""Gestión del ciclo de vida de tokens OAuth de Bitrix24.

Tokens almacenados en Redis como JSON en la clave 'bitrix:oauth_tokens'.
Se renuevan automáticamente con 5 minutos de margen antes del vencimiento.
"""

import json
import logging
import time

import httpx

from config.settings import settings
from integrations.exceptions import BitrixError
from integrations.redis_client import get_redis

logger = logging.getLogger(__name__)

_REDIS_KEY = "bitrix:oauth_tokens"
_BITRIX_DOMAIN = "https://b24-ahyle8.bitrix24.mx"


async def get_token() -> str:
    """Devuelve un access_token válido, renovando si está próximo a vencer."""
    redis = await get_redis()
    raw = await redis.get(_REDIS_KEY)
    if not raw:
        raise BitrixError("OAuth tokens no encontrados. Ejecuta el flujo de autorización primero.")

    data = json.loads(raw)
    expires_at = data.get("expires_at", 0)

    if time.time() >= expires_at - 300:  # 5 min de margen
        data = await refresh_tokens(data["refresh_token"])

    return data["access_token"]


async def save_tokens(data: dict) -> None:
    """Persiste los tokens en Redis sin TTL (sobreviven reinicios del contenedor)."""
    redis = await get_redis()
    payload = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": int(time.time()) + int(data.get("expires_in", 3600)),
        "domain": data.get("client_endpoint", _BITRIX_DOMAIN).removesuffix("/rest/"),
    }
    await redis.set(_REDIS_KEY, json.dumps(payload))
    logger.info("bitrix_oauth_tokens_saved")


async def exchange_code(code: str) -> dict:
    """Intercambia el código de autorización por access_token + refresh_token."""
    params = {
        "grant_type": "authorization_code",
        "client_id": settings.bitrix_client_id,
        "client_secret": settings.bitrix_client_secret,
        "code": code,
        "redirect_uri": f"{settings.bitrix_public_url}/bitrix/app",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{_BITRIX_DOMAIN}/oauth/token/", params=params)
        if resp.status_code != 200:
            raise BitrixError(f"OAuth exchange_code error {resp.status_code}: {resp.text}")
        data = resp.json()

    if "access_token" not in data:
        raise BitrixError(f"OAuth exchange_code sin access_token: {data}")

    await save_tokens(data)
    logger.info("bitrix_oauth_authorized")
    return data


async def refresh_tokens(refresh_token: str) -> dict:
    """Renueva los tokens usando el refresh_token."""
    params = {
        "grant_type": "refresh_token",
        "client_id": settings.bitrix_client_id,
        "client_secret": settings.bitrix_client_secret,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{_BITRIX_DOMAIN}/oauth/token/", params=params)
        if resp.status_code != 200:
            raise BitrixError(f"OAuth refresh error {resp.status_code}: {resp.text}")
        data = resp.json()

    if "access_token" not in data:
        raise BitrixError(f"OAuth refresh sin access_token: {data}")

    await save_tokens(data)
    logger.info("bitrix_oauth_refreshed")
    return data

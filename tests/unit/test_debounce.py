"""Tests del motor de debounce de mensajes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.debounce import _flush_after, enqueue


def _make_redis(stored_token: str | None = None, msgs: list[str] | None = None):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=stored_token)
    pipe = AsyncMock()
    pipe.lrange = MagicMock(return_value=pipe)
    pipe.delete = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[msgs or [], None, None])
    redis.pipeline = MagicMock(return_value=pipe)
    redis.rpush = AsyncMock()
    redis.set = AsyncMock()
    return redis


@pytest.mark.asyncio
async def test_enqueue_window_cero_llama_callback_inmediato():
    callback = AsyncMock()
    with patch("integrations.debounce.get_redis", return_value=AsyncMock()):
        await enqueue("5218001234567", "hola", 0, callback)
    callback.assert_awaited_once_with("5218001234567", "hola")


@pytest.mark.asyncio
async def test_enqueue_con_window_no_llama_callback_inmediato():
    callback = AsyncMock()
    redis = _make_redis()
    with patch("integrations.debounce.get_redis", AsyncMock(return_value=redis)):
        await enqueue("5218001234567", "hola", 500, callback)
    callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_after_token_coincide_llama_callback():
    TOKEN = "abc-123"
    redis = _make_redis(stored_token=TOKEN, msgs=["hola", "quiero info"])
    callback = AsyncMock()

    with patch("integrations.debounce.get_redis", AsyncMock(return_value=redis)):
        with patch("asyncio.sleep", AsyncMock()):
            await _flush_after("5218001234567", TOKEN, 0.001, callback)

    callback.assert_awaited_once_with("5218001234567", "hola\nquiero info")


@pytest.mark.asyncio
async def test_flush_after_token_distinto_no_llama_callback():
    redis = _make_redis(stored_token="token-nuevo")
    callback = AsyncMock()

    with patch("integrations.debounce.get_redis", AsyncMock(return_value=redis)):
        with patch("asyncio.sleep", AsyncMock()):
            await _flush_after("5218001234567", "token-viejo", 0.001, callback)

    callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_after_buffer_vacio_no_llama_callback():
    TOKEN = "abc-123"
    redis = _make_redis(stored_token=TOKEN, msgs=[])
    callback = AsyncMock()

    with patch("integrations.debounce.get_redis", AsyncMock(return_value=redis)):
        with patch("asyncio.sleep", AsyncMock()):
            await _flush_after("5218001234567", TOKEN, 0.001, callback)

    callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_after_callback_exception_no_propaga():
    TOKEN = "abc-123"
    redis = _make_redis(stored_token=TOKEN, msgs=["texto"])
    callback = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("integrations.debounce.get_redis", AsyncMock(return_value=redis)):
        with patch("asyncio.sleep", AsyncMock()):
            # No debe propagar la excepción del callback
            await _flush_after("5218001234567", TOKEN, 0.001, callback)

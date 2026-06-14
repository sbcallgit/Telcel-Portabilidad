"""Tests de fiabilidad del polling del asesor (P-01) y del ext_chat atómico (P-03).

Usan un fake redis en memoria; no tocan Bitrix ni red.
"""

import pytest


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self.store else 0


@pytest.mark.asyncio
async def test_poll_phone_avanza_cursor_tras_entrega(monkeypatch):
    import integrations.bitrix.connector as conn
    import jobs.connector_poll as cp

    redis = FakeRedis()
    entregados = []

    async def fake_forward(phone, text):
        entregados.append(text)

    async def fake_poll(phone, chat_id):
        return [("5", "hola", 10), ("7", "mundo", 10)], 7

    monkeypatch.setattr(cp, "_forward_to_user", fake_forward)
    monkeypatch.setattr(conn, "poll_asesor_messages", fake_poll)

    await cp._poll_phone("5219991112233", "chat1", redis)

    assert entregados == ["hola", "mundo"]
    # Todo entregado → cursor al id más alto visto.
    assert redis.store["connector_last_msg:5219991112233"] == "7"


@pytest.mark.asyncio
async def test_poll_phone_no_pierde_mensaje_si_falla_entrega(monkeypatch):
    import integrations.bitrix.connector as conn
    import jobs.connector_poll as cp

    redis = FakeRedis()
    entregados = []

    async def fake_forward(phone, text):
        if text == "segundo":
            raise RuntimeError("whatsapp caído")
        entregados.append(text)

    async def fake_poll(phone, chat_id):
        return [("5", "primero", 10), ("7", "segundo", 10)], 7

    monkeypatch.setattr(cp, "_forward_to_user", fake_forward)
    monkeypatch.setattr(conn, "poll_asesor_messages", fake_poll)

    await cp._poll_phone("5219991112233", "chat1", redis)

    # Solo el primero se entregó; el cursor NO debe pasar del fallo → se reintenta.
    assert entregados == ["primero"]
    assert redis.store["connector_last_msg:5219991112233"] == "5"


@pytest.mark.asyncio
async def test_ext_chat_id_es_atomico_y_reusa_ganador(monkeypatch):
    import integrations.bitrix.connector as conn

    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(conn, "get_redis", fake_get_redis)

    primero = await conn._get_or_create_external_chat_id("5219991112233")
    segundo = await conn._get_or_create_external_chat_id("5219991112233")

    # El segundo llamado reutiliza el external_chat_id creado por el primero.
    assert primero == segundo

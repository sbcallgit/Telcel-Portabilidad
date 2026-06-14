"""Matriz de auth de endpoints públicos/admin con TestClient.

La app se construye solo con routers para evitar lifespan, scheduler, DB, Redis
y clientes externos reales. Todos los casos fallan antes de tocar IO externo.
"""

import hashlib
import hmac

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import admin, connector, telegram, webhooks
from config.settings import settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "admin-ok")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tg-secret")
    monkeypatch.setattr(settings, "telegram_bot_token", "tg-token")
    monkeypatch.setattr(settings, "bitrix_application_token", "bitrix-ok")
    monkeypatch.setattr(settings, "bitrix_connector_id", "whatsapp_vera")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-secret")

    app = FastAPI()
    app.include_router(admin.router)
    app.include_router(telegram.router)
    app.include_router(connector.router)
    app.include_router(webhooks.router)
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/admin/kpi-export", None),
        ("post", "/admin/seguimiento-test", {"telefono": "8123456789"}),
        ("post", "/admin/vicidial-test", {"telefono": "8123456789", "simulate": True}),
    ],
)
def test_admin_token_incorrecto_retorna_403(client, method, path, json_body):
    response = getattr(client, method)(
        path,
        headers={"X-Admin-Token": "wrong"},
        json=json_body,
    )

    assert response.status_code == 403


@pytest.mark.xfail(
    strict=True,
    reason="api/routes/admin.py:38 requiere Header(...); FastAPI responde 422 sin header, no 403.",
)
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/admin/kpi-export", None),
        ("post", "/admin/seguimiento-test", {"telefono": "8123456789"}),
        ("post", "/admin/vicidial-test", {"telefono": "8123456789", "simulate": True}),
    ],
)
def test_admin_sin_token_debe_retornar_403(client, method, path, json_body):
    response = getattr(client, method)(path, json=json_body)

    assert response.status_code == 403


def test_admin_token_vacio_retorna_503(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")

    response = client.post("/admin/kpi-export", headers={"X-Admin-Token": "anything"})

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/webhooks/telegram/setup?url=https://example.test"),
        ("get", "/webhooks/telegram/info"),
    ],
)
def test_telegram_setup_info_token_incorrecto_retorna_403(client, method, path):
    response = getattr(client, method)(path, headers={"X-Admin-Token": "wrong"})

    assert response.status_code == 403


@pytest.mark.xfail(
    strict=True,
    reason="api/routes/telegram.py:104,117 requieren Header(...); FastAPI responde 422 sin header, no 403.",
)
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/webhooks/telegram/setup?url=https://example.test"),
        ("get", "/webhooks/telegram/info"),
    ],
)
def test_telegram_setup_info_sin_token_debe_retornar_403(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 403


def test_telegram_webhook_secret_vacio_retorna_503(client, monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")

    response = client.post("/webhooks/telegram", json={"message": {"text": "hola"}})

    assert response.status_code == 503


def test_connector_sin_application_token_configurado_retorna_503(client, monkeypatch):
    monkeypatch.setattr(settings, "bitrix_application_token", "")

    response = client.post("/webhooks/connector", json={})

    assert response.status_code == 503


def test_connector_token_incorrecto_retorna_401(client):
    response = client.post(
        "/webhooks/connector",
        json={"application_token": "wrong", "data": {"CONNECTOR": "whatsapp_vera"}},
    )

    assert response.status_code == 401


def test_telcel_production_sin_app_secret_retorna_503(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "")

    response = client.post("/webhooks/telcel", content=b"{}")

    assert response.status_code == 503


def test_telcel_firma_invalida_retorna_401(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-secret")

    response = client.post(
        "/webhooks/telcel",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=bad"},
    )

    assert response.status_code == 401


def test_telcel_firma_valida_payload_status_no_toca_io_y_retorna_ignored(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-secret")
    body = b'{"entry":[{"changes":[{"value":{"statuses":[{"id":"wamid.1"}]}}]}]}'
    signature = "sha256=" + hmac.new(b"wa-secret", body, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/telcel",
        content=body,
        headers={"X-Hub-Signature-256": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


"""Unit tests deterministas para handlers puros de WhatsApp."""

import hashlib
import hmac

import pytest

from integrations.whatsapp.handlers import parse_whatsapp_message, verify_webhook_signature


def test_verify_webhook_signature_valida_firma_correcta():
    payload = b'{"ok": true}'
    secret = "super-secret"
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(payload, signature, secret)


def test_verify_webhook_signature_rechaza_firma_invalida():
    assert not verify_webhook_signature(b"{}", "sha256=bad", "super-secret")


def test_verify_webhook_signature_rechaza_firma_vacia():
    assert not verify_webhook_signature(b"{}", "", "super-secret")


def test_parse_whatsapp_message_extrae_texto():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5218123456789",
                                    "id": "wamid.1",
                                    "type": "text",
                                    "text": {"body": " hola "},
                                },
                            ],
                        },
                    },
                ],
            },
        ],
    }

    assert parse_whatsapp_message(payload) == ("5218123456789", "hola", "wamid.1")


def test_parse_whatsapp_message_ignora_status_updates():
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.1"}]}}]}]}

    assert parse_whatsapp_message(payload) is None


def test_parse_whatsapp_message_ignora_mensajes_no_texto():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "5218123456789", "id": "wamid.1", "type": "image"},
                            ],
                        },
                    },
                ],
            },
        ],
    }

    assert parse_whatsapp_message(payload) is None


@pytest.mark.parametrize("payload", [{}, {"entry": []}, {"entry": [{"changes": []}]}])
def test_parse_whatsapp_message_malformado_retorna_none(payload):
    assert parse_whatsapp_message(payload) is None


@pytest.mark.xfail(
    strict=True,
    reason="integrations/whatsapp/handlers.py:51 no captura AttributeError para payload no dict.",
)
def test_parse_whatsapp_message_payload_none_retorna_none():
    assert parse_whatsapp_message(None) is None

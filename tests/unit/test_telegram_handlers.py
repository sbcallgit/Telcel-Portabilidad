"""Unit tests deterministas para handlers puros de Telegram."""

from integrations.telegram.handlers import TelegramMessage, parse_update


def test_parse_update_extrae_texto():
    payload = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456, "first_name": "Ana"},
            "text": " hola ",
            "message_id": 7,
        }
    }

    assert parse_update(payload) == TelegramMessage(
        chat_id=123,
        user_id=456,
        first_name="Ana",
        text="hola",
        message_id=7,
        phone="tg_123",
    )


def test_parse_update_text_no_string_retorna_none():
    payload = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456, "first_name": "Ana"},
            "text": {"unexpected": "shape"},
            "message_id": 7,
        }
    }

    assert parse_update(payload) is None

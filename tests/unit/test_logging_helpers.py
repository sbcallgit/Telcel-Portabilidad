"""Unit tests deterministas para helpers de logging."""

from config.logging import mask_phone


def test_mask_phone_enmascara_centro_de_numero_largo():
    assert mask_phone("+52 1 81 2345 6789") == "5218*****6789"


def test_mask_phone_enmascara_numeros_cortos_completo():
    assert mask_phone("1234567") == "****"
    assert mask_phone("") == "****"


def test_mask_phone_con_ocho_digitos_no_agrega_asteriscos():
    assert mask_phone("12345678") == "12345678"


"""Unit tests deterministas para helpers puros de validacion."""

from agents.portabilidad.nodes import validacion


def test_count_digits_cuenta_solo_digitos():
    assert validacion._count_digits("Tel. (81) 2345-6789 ext 22") == 12
    assert validacion._count_digits("sin numeros") == 0


def test_extract_phone_acepta_10_digitos_con_separadores():
    assert validacion._extract_phone("8123456789") == "8123456789"
    assert validacion._extract_phone("(81) 2345-6789") == "8123456789"


def test_extract_phone_acepta_codigo_pais_52():
    assert validacion._extract_phone("+52 81 2345 6789") == "8123456789"


def test_extract_phone_rechaza_conteos_invalidos():
    assert validacion._extract_phone("812345678") is None
    assert validacion._extract_phone("81234567890") is None
    assert validacion._extract_phone("8123456789 y 8111111111") is None


def test_is_phone_attempt_detecta_intento_incompleto():
    assert validacion._is_phone_attempt("8123456")
    assert validacion._is_phone_attempt("81 2345 67")


def test_is_phone_attempt_ignora_texto_con_muchos_separadores():
    assert not validacion._is_phone_attempt("mi numero podria ser 81 23")
    assert not validacion._is_phone_attempt("hola quiero informacion")


def test_word_match_respeta_fronteras_de_palabra():
    assert validacion._word_match("quiero hablar con un asesor", ["asesor"])
    assert validacion._word_match("necesito una persona real", ["persona real"])
    assert not validacion._word_match("este mensaje dice preasesor", ["asesor"])
    assert not validacion._word_match("agentesmith", ["agente"])


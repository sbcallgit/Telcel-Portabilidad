"""Unit tests deterministas para helpers puros de cierre."""

import pytest
from freezegun import freeze_time

from agents.portabilidad.nodes import cierre


def test_extract_phone_acepta_10_digitos_con_separadores():
    assert cierre._extract_phone("8123456789") == "8123456789"
    assert cierre._extract_phone("(81) 2345-6789") == "8123456789"


def test_extract_phone_rechaza_conteos_invalidos():
    assert cierre._extract_phone("812345678") is None
    assert cierre._extract_phone("81234567890") is None


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Me cambio desde Movistar", "Movistar"),
        ("Vengo de AT&T", "AT&T"),
        ("Mi compania es bait", "Altan/Bait"),
        ("Uso Unefon ahora", "Unefon"),
        ("No tengo compania", None),
    ],
)
def test_extract_company(texto, esperado):
    assert cierre._extract_company(texto) == esperado


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        ({}, "nombre"),
        ({"nombre": "Ana Perez"}, "numero_a_portar"),
        ({"nombre": "Ana Perez", "numero_a_portar": "8123456789"}, "compania_donante"),
        (
            {
                "nombre": "Ana Perez",
                "numero_a_portar": "8123456789",
                "compania_donante": "Movistar",
            },
            None,
        ),
    ],
)
def test_next_pending(datos, esperado):
    assert cierre._next_pending(datos) == esperado


def test_extract_all_kpis_extrae_campos_en_un_turno():
    datos = cierre._extract_all_kpis("Rafael Canales 8112111092 Bait", {})

    assert datos == {
        "nombre": "Rafael Canales",
        "numero_a_portar": "8112111092",
        "compania_donante": "Altan/Bait",
    }


def test_extract_all_kpis_respeta_datos_existentes():
    datos = cierre._extract_all_kpis(
        "8112111092 Movistar",
        {"nombre": "Ana Perez", "compania_donante": "AT&T"},
    )

    assert datos == {
        "nombre": "Ana Perez",
        "numero_a_portar": "8112111092",
        "compania_donante": "AT&T",
    }


@pytest.mark.xfail(
    strict=True,
    reason="cierre.py:190-191 infiere nombres falsos desde texto operativo corto.",
)
def test_extract_all_kpis_no_inventa_nombre_desde_texto_basura():
    datos = cierre._extract_all_kpis("me cambio de bait", {})

    assert datos == {"compania_donante": "Altan/Bait"}


@pytest.mark.parametrize(
    ("frozen_utc", "esperado"),
    [
        ("2026-06-07 18:00:00+00:00", "mañana lunes"),
        ("2026-06-13 14:00:00+00:00", "hoy mismo a esa hora"),
        ("2026-06-13 15:00:00+00:00", "conectar con un asesor"),
        ("2026-06-09 03:00:00+00:00", "mañana en horario hábil"),
        ("2026-06-08 14:00:00+00:00", "hoy mismo a esa hora"),
        ("2026-06-08 15:00:00+00:00", "conectar con un asesor"),
    ],
)
def test_mensaje_contacto_asesor_matriz_docstring(frozen_utc, esperado):
    with freeze_time(frozen_utc):
        assert esperado in cierre._mensaje_contacto_asesor()


@pytest.mark.xfail(
    strict=True,
    reason="cierre.py:48 inicia corte sabatino en >=15 aunque el docstring dice 14:00.",
)
def test_mensaje_contacto_asesor_sabado_14_debe_ir_a_lunes():
    with freeze_time("2026-06-13 20:00:00+00:00"):
        assert "próximo lunes" in cierre._mensaje_contacto_asesor()


@pytest.mark.xfail(
    strict=True,
    reason="cierre.py:55 no cubre la hora 00 aunque el docstring dice 00:01-08:59.",
)
def test_mensaje_contacto_asesor_lunes_0030_debe_ser_hoy_9():
    with freeze_time("2026-06-08 06:30:00+00:00"):
        assert "hoy mismo a esa hora" in cierre._mensaje_contacto_asesor()


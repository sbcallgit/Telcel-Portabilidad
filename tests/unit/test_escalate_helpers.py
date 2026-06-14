"""Unit tests deterministas para helpers puros de escalate."""

import pytest

from agents.portabilidad.nodes import escalate


@pytest.mark.parametrize(
    "motivo",
    [
        "solicitud_directa",
        "caso_sensible",
        "solicitud_arco",
        "telcel_a_telcel",
        "cambio_titularidad",
    ],
)
def test_resolve_stage_motivos_escalamiento(monkeypatch, motivo):
    monkeypatch.setattr(escalate.settings, "bitrix_stage_escalamiento", "ESC")

    assert escalate._resolve_stage(motivo) == "ESC"


@pytest.mark.parametrize("motivo", ["seguimiento", "max_objeciones_alcanzado"])
def test_resolve_stage_motivos_seguimiento(monkeypatch, motivo):
    monkeypatch.setattr(escalate.settings, "bitrix_stage_seguimiento", "SEG")

    assert escalate._resolve_stage(motivo) == "SEG"


@pytest.mark.parametrize("motivo", ["cierre", "otro", "", "lada_no_identificada"])
def test_resolve_stage_default_prospecto(monkeypatch, motivo):
    monkeypatch.setattr(escalate.settings, "bitrix_stage_prospecto", "PRO")

    assert escalate._resolve_stage(motivo) == "PRO"


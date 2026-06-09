"""Verifica que render_prompt carga archivos .txt y sustituye placeholders correctamente."""

import pytest
from pathlib import Path
from agents.portabilidad.utils import load_prompt, render_prompt

PROMPT_NAMES = [
    "horarios",
    "validacion_general",
    "sondeo_con_recarga",
    "sondeo_sin_recarga",
    "oferta_principal",
    "objeciones",
    "cierre_fallback",
]


def test_todos_los_archivos_existen():
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    for name in PROMPT_NAMES:
        path = prompts_dir / f"{name}.txt"
        assert path.exists(), f"Falta el archivo de prompt: {name}.txt"


def test_load_prompt_retorna_contenido_no_vacio():
    for name in PROMPT_NAMES:
        texto = load_prompt(name)
        assert texto, f"El prompt '{name}' está vacío"
        assert "Vera" in texto or "Eres" in texto or "campo_desc" in texto, \
            f"El prompt '{name}' no parece un prompt de agente válido"


def test_render_prompt_sustituye_placeholder():
    resultado = render_prompt("cierre_fallback", campo_desc="nombre completo del cliente")
    assert "{campo_desc}" not in resultado
    assert "nombre completo del cliente" in resultado


def test_render_prompt_placeholder_faltante_no_explota():
    # Si falta un kwarg, el placeholder se queda tal cual — no lanza excepción
    resultado = render_prompt("cierre_fallback")
    assert "{campo_desc}" in resultado  # queda sin sustituir


def test_render_prompt_horarios_sustituye_multiples_placeholders():
    resultado = render_prompt(
        "horarios",
        PORTABILITY_SCHEDULE="SCHEDULE_MOCK",
        FORMAT_RULES="FORMAT_MOCK",
    )
    assert "SCHEDULE_MOCK" in resultado
    assert "FORMAT_MOCK" in resultado
    assert "{PORTABILITY_SCHEDULE}" not in resultado
    assert "{FORMAT_RULES}" not in resultado


def test_render_prompt_no_falla_con_llaves_en_valores():
    # Valores que contienen llaves no deben romper render_prompt
    resultado = render_prompt(
        "cierre_fallback",
        campo_desc="campo {con llaves}",
    )
    assert "campo {con llaves}" in resultado

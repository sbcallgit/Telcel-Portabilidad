"""Matriz funcional QF-* — el agente como usuario normal (offline).

Driver: invocación directa del grafo (conftest.turno). Sin red, sin LLM real,
sin Bitrix. Las aserciones se centran en etapa/escalamiento/keywords estables,
no en texto generado por el LLM.
"""

from tests.agent_qa._helpers import turno


async def test_qf01_happy_path_valida_lada_y_avanza_a_oferta(agente):
    # LADA 811 (Monterrey, habilitada) → sondeo; luego $100 → oferta.
    t1 = await turno(agente, "qf01", "mi número es 8112345678")
    assert t1.etapa == "sondeo", f"LADA 811 debe avanzar a sondeo, fue {t1.etapa!r}"

    t2 = await turno(agente, "qf01", "recargo $100 al mes")
    assert t2.etapa == "oferta", f"con la recarga debe pasar a oferta, fue {t2.etapa!r}"
    assert "100" in t2.bot_text


async def test_qf03_numero_invalido_pide_diez_digitos(agente):
    t = await turno(agente, "qf03", "8112345")  # 7 dígitos
    assert t.etapa != "sondeo"
    assert "10 dígitos" in t.bot_text or "diez" in t.bot_text.lower()


async def test_qf04_emoji_no_se_toma_como_numero(agente):
    t = await turno(agente, "qf04", "👍👍")
    assert t.etapa not in ("sondeo", "oferta")
    assert "número" in t.bot_text.lower() or "10 dígitos" in t.bot_text


async def test_qf05_lada_fuera_de_region_deriva_a_cac(agente):
    t = await turno(agente, "qf05", "8712345678")  # 871 Torreón, no habilitada
    assert t.etapa == "fin"
    assert "cac" in t.bot_text.lower() or "presencial" in t.bot_text.lower()


async def test_qf08_pospago_deriva_a_cac(agente):
    t = await turno(agente, "qf08", "yo tengo plan de renta mensual")
    assert "cac" in t.bot_text.lower() or "presencial" in t.bot_text.lower()


async def test_qf15_pide_humano_escala(agente):
    t = await turno(agente, "qf15", "quiero hablar con un asesor")
    assert t.motivo == "solicitud_directa"
    assert "asesor" in t.bot_text.lower()


async def test_qf16_pregunta_precio_responde_sin_pedir_numero_primero(agente):
    t = await turno(agente, "qf16", "¿cuánto cuesta?")
    assert "100" in t.bot_text  # da info de recarga, no exige número primero


async def test_qf02_cierre_incompleto_pide_campo_faltante(agente):
    t = await turno(
        agente, "qf02", "me llamo Juan Pérez García",
        estado_extra={"etapa": "cierre", "datos_lead": {}},
    )
    assert t.etapa != "escalado", "sin número no debe escalar"
    assert "10 dígitos" in t.bot_text


async def test_qf10_pregunta_horario_responde_sin_crashear(agente):
    # Camino LLM (stub): valida el plumbing del nodo de horarios.
    t = await turno(agente, "qf10", "¿cuándo queda lista la portación?")
    assert t.bot_text != ""


async def test_qf14_solicitud_arco_escala_a_privacidad(agente):
    t = await turno(
        agente, "qf14", "quiero que borren mis datos",
        estado_extra={"etapa": "objecion"},
    )
    assert t.motivo == "solicitud_arco"
    assert "arco" in t.bot_text.lower()

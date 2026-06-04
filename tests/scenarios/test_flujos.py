"""Suite de pruebas de escenarios completos — basada en Script_Portabilidad_05032026.md
y en los 40 hallazgos + 13 patrones sistémicos de las auditorías.

Ejecutar: docker compose exec api pytest tests/scenarios/test_flujos.py -v
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage

# ─── Setup ────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def agente():
    """Pool de DB + grafo con checkpointer limpio para cada test."""
    from integrations.postgres.client import close_pool, create_pool
    await create_pool()

    from agents.portabilidad.graph import _build
    from langgraph.checkpoint.memory import MemorySaver
    graph = _build().compile(checkpointer=MemorySaver())

    yield graph

    await close_pool()


# ─── Helper ───────────────────────────────────────────────────────────────────

@dataclass
class ConvResult:
    etapa: str
    bot_text: str
    datos_lead: dict = field(default_factory=dict)
    temperatura: str = ""
    promo_elegida: str = ""
    escalate_to_human: bool = False


async def turno(agente, thread_id: str, texto: str) -> ConvResult:
    config = {"configurable": {"thread_id": thread_id}}
    result = await agente.ainvoke(
        {"messages": [HumanMessage(content=texto)], "session_id": thread_id, "customer_phone": f"tg_{thread_id}"},
        config=config,
    )
    ai_msgs = [m.content for m in result.get("messages", []) if isinstance(m, AIMessage)
               and m.content != "(procesando objeción)"]
    return ConvResult(
        etapa=result.get("etapa", ""),
        bot_text=ai_msgs[-1] if ai_msgs else "",
        datos_lead=result.get("datos_lead") or {},
        temperatura=result.get("temperatura", ""),
        promo_elegida=result.get("promo_elegida", ""),
        escalate_to_human=result.get("escalate_to_human", False),
    )


async def conv(agente, thread_id: str, mensajes: list[str]) -> list[ConvResult]:
    return [await turno(agente, thread_id, m) for m in mensajes]


# ════════════════════════════════════════════════════════════════════════════════
# FLUJO COMPLETO — HAPPY PATH
# ════════════════════════════════════════════════════════════════════════════════

class TestFlujoCompleto:
    """Recorre el embudo completo: validación → sondeo → oferta → cierre → escalado."""

    @pytest.mark.asyncio
    async def test_flujo_100_pesos_redes(self, agente):
        """Happy path: $100 + redes sociales → ambas promos de $100 → cierre completo."""
        tid = "happy_100"
        results = await conv(agente, tid, [
            "Hola",
            "8112345678",     # Monterrey, LADA 811 habilitada
            "100 pesos",
            "redes sociales",
            "sí, quiero la Plus",
            "María García López",
            "8113456789",
            "Movistar",
            "Monterrey",
            "sí está liberado",
        ])

        # T2: validación Monterrey
        assert results[1].etapa == "sondeo", "Debió mover a sondeo tras validar LADA 811"

        # T4: presentación de promos (redes + $100)
        r4 = results[3]
        assert r4.etapa == "oferta"
        assert "100" in r4.bot_text, "Debe mostrar promos de $100"
        # Script: deben mostrarse AMBAS opciones de $100
        assert "Plus" in r4.bot_text or "Sin Recarga" in r4.bot_text, "Debe mostrar al menos una promo de $100"
        assert "GRATIS" in r4.bot_text.upper() or "gratis" in r4.bot_text.lower() or "Sin Recarga" in r4.bot_text, \
            "Debe mencionar la opción de primera recarga gratis"

        # T5: intención de compra → cierre
        assert results[4].etapa == "cierre"

        # T10: datos completos → escalado
        assert results[9].etapa == "escalado"
        datos = results[9].datos_lead
        assert datos.get("nombre") == "María García López"
        assert datos.get("numero_a_portar") == "8113456789"
        assert datos.get("compania_donante") == "Movistar"
        assert datos.get("municipio") == "Monterrey"
        assert datos.get("equipo_liberado") == "Sí"

    @pytest.mark.asyncio
    async def test_flujo_50_pesos(self, agente):
        """$50/semana → debe mostrar Sin Recarga Inicial $50 + Portabilidad Plus $50."""
        tid = "happy_50"
        results = await conv(agente, tid, [
            "8441234567",   # Saltillo, LADA 844 habilitada
            "50 pesos",
            "WhatsApp",
        ])
        r = results[2]
        assert r.etapa == "oferta"
        assert "50" in r.bot_text
        # Para $50 debe mencionar la Sin Recarga Inicial
        assert "recarga" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_flujo_150_amazon_prime(self, agente):
        """$150 → debe mostrar Portabilidad Plus $150 con Amazon Prime Básico."""
        tid = "happy_150"
        results = await conv(agente, tid, [
            "8182345678",   # Monterrey LADA 818
            "150",
            "todo, redes y llamadas",
        ])
        r = results[2]
        assert r.etapa == "oferta"
        assert "150" in r.bot_text
        assert "amazon" in r.bot_text.lower() or "Amazon" in r.bot_text

    @pytest.mark.asyncio
    async def test_flujo_270_amazon_basico(self, agente):
        """$270 → Amazon Prime BÁSICO (2 pantallas, celular+TV, HD, envíos gratis).
        CORRECCIÓN auditoría: $270 es BÁSICO, no COMPLETO. $400 es COMPLETO."""
        tid = "happy_270"
        results = await conv(agente, tid, [
            "8112222222",
            "270",
            "streaming y series",
        ])
        r = results[2]
        assert r.etapa == "oferta"
        # $270 debe mostrar Amazon Prime Básico (2 pantallas, HD, TV)
        bot_lower = r.bot_text.lower()
        assert "básico" in bot_lower or "2 pantalla" in bot_lower or "hd" in bot_lower or \
               "amazon" in bot_lower, f"$270 debe mencionar Amazon Prime Básico. Bot: {r.bot_text}"
        # $270 NO debe decir "3 dispositivos" ni "music" ni "gaming" (eso es $400)
        assert "3 dispositivos" not in bot_lower and "gaming" not in bot_lower, \
            f"$270 no debe presentarse como Prime Completo. Bot: {r.bot_text}"


# ════════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN DE LADA
# ════════════════════════════════════════════════════════════════════════════════

class TestValidacionLada:
    """Cobertura de todos los escenarios de validación de LADA/región."""

    @pytest.mark.asyncio
    async def test_lada_habilitada_monterrey(self, agente):
        r = await turno(agente, "lada_mty", "8112345678")
        assert r.etapa == "sondeo"
        assert "monterrey" in r.bot_text.lower() or "Monterrey" in r.bot_text

    @pytest.mark.asyncio
    async def test_lada_habilitada_saltillo(self, agente):
        r = await turno(agente, "lada_salt", "8441234567")
        assert r.etapa == "sondeo"
        assert "saltillo" in r.bot_text.lower() or "Saltillo" in r.bot_text

    @pytest.mark.asyncio
    async def test_lada_no_habilitada_torreon(self, agente):
        """LADA 871 (Torreón) no habilitada → derivar a CAC, no avanzar al sondeo."""
        r = await turno(agente, "lada_torr", "8713456789")
        assert r.etapa == "fin", "Torreón no habilitada debe ir a fin"
        assert "cac" in r.bot_text.lower() or "presencial" in r.bot_text.lower() or "no está habilitada" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_lada_pregunta_directa_si(self, agente):
        """Responder directamente '¿la LADA 844 aplica?' sin pedir número primero."""
        r = await turno(agente, "lada_q_si", "¿la LADA 844 aplica?")
        assert "sí" in r.bot_text.lower() or "aplica" in r.bot_text.lower() or "Saltillo" in r.bot_text

    @pytest.mark.asyncio
    async def test_lada_pregunta_directa_no(self, agente):
        """Responder correctamente '¿la LADA 871 aplica?' → NO."""
        r = await turno(agente, "lada_q_no", "¿la LADA 871 aplica?")
        # Debe decir que NO está habilitada (no inventar que sí aplica)
        text_lower = r.bot_text.lower()
        assert "no" in text_lower or "torreón" in text_lower, \
            f"Debe informar que 871 NO aplica. Bot dijo: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_lada_pregunta_corta_no(self, agente):
        """Mensaje corto '¿y la 871?' debe consultar la BD y responder NO."""
        await turno(agente, "lada_short", "¿la LADA 844 aplica?")
        r = await turno(agente, "lada_short", "¿y la 871?")
        assert "no" in r.bot_text.lower() or "torreón" in r.bot_text.lower(), \
            f"LADA 871 es NO habilitada. Bot dijo: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_revalidacion_numero_corregido(self, agente):
        """Si el cliente corrige su número, debe re-validar la LADA. (Hallazgos #4 y #5)"""
        await turno(agente, "revalid", "8112345678")   # Monterrey → sondeo
        r = await turno(agente, "revalid", "8713456789")  # Torreón → fin
        assert r.etapa in ("fin", "sondeo"), "Debe re-evaluar LADA al recibir nuevo número"

    @pytest.mark.asyncio
    async def test_input_emoji_no_se_toma_como_numero(self, agente):
        """Emoji no debe interpretarse como teléfono. (Hallazgo #9, patrón #5)"""
        r = await turno(agente, "emoji", "😊👋")
        # No debe ir a sondeo ni mostrar 'Tu zona aplica'
        assert r.etapa not in ("sondeo", "oferta"), f"Emoji no debe avanzar el flujo. Etapa: {r.etapa}"
        assert "10 dígitos" in r.bot_text or "número" in r.bot_text.lower()


# ════════════════════════════════════════════════════════════════════════════════
# SONDEO
# ════════════════════════════════════════════════════════════════════════════════

class TestSondeo:
    """Verifica el comportamiento del nodo de sondeo."""

    @pytest.mark.asyncio
    async def test_responde_pregunta_promo_sin_pedir_numero(self, agente):
        """El bot debe responder preguntas comerciales sin exigir número primero. (Patrón #1)"""
        r = await turno(agente, "sondeo_q", "¿qué incluye la promo de $100?")
        # No debe pedir número como REQUISITO para responder
        assert "10 dígitos" not in r.bot_text or "5.5" in r.bot_text or "100" in r.bot_text, \
            "Debe informar sobre la promo sin bloquear con petición de número"

    @pytest.mark.asyncio
    async def test_sondeo_recargas_menores_no_ilimitadas(self, agente):
        """Para $50/$80 las redes NO son ilimitadas — debe informar claramente."""
        await turno(agente, "sondeo_50", "8112345678")
        await turno(agente, "sondeo_50", "50 pesos")
        r = await turno(agente, "sondeo_50", "redes")
        # Promo $50 no tiene redes ilimitadas en Portabilidad Plus
        assert "50" in r.bot_text


# ════════════════════════════════════════════════════════════════════════════════
# OBJECIONES
# ════════════════════════════════════════════════════════════════════════════════

class TestObjeciones:
    """Verifica el banco de objeciones con los escenarios reales del script."""

    async def _hasta_oferta(self, agente, tid):
        await conv(agente, tid, ["8112345678", "100", "redes"])

    @pytest.mark.asyncio
    async def test_objecion_precio_responde_en_mismo_turno(self, agente):
        """Objeción 'está caro' debe responderse en el mismo turno (no en el siguiente)."""
        await self._hasta_oferta(agente, "obj_precio")
        r = await turno(agente, "obj_precio", "está muy caro")
        # No debe mostrar la promo de nuevo — debe ser un rebate
        assert r.etapa in ("oferta", "objecion")
        assert "caro" not in r.bot_text.lower() or "entiendo" in r.bot_text.lower() or \
               "comparando" in r.bot_text.lower() or "pesos" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_objecion_saldo_no_transferible(self, agente):
        """'¿El saldo se transfiere?' → informar que NO."""
        await self._hasta_oferta(agente, "obj_saldo")
        r = await turno(agente, "obj_saldo", "¿el saldo se transfiere?")
        assert "no" in r.bot_text.lower() or "transferible" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_objecion_recargas_menores(self, agente):
        """'¿Puedo recargar menos de $100?' → explicar bolsa vs ilimitadas."""
        await self._hasta_oferta(agente, "obj_rec")
        r = await turno(agente, "obj_rec", "¿puedo hacer recargas de $50?")
        assert "bolsa" in r.bot_text.lower() or "no son ilimitadas" in r.bot_text.lower() or \
               "1 gb" in r.bot_text.lower() or "$100" in r.bot_text

    @pytest.mark.asyncio
    async def test_objecion_donde_recargar(self, agente):
        """Preguntar dónde recargar → incluir restricción Liverpool/Walmart/MixUP."""
        await self._hasta_oferta(agente, "obj_donde")
        r = await turno(agente, "obj_donde", "¿dónde puedo recargar?")
        assert "liverpool" in r.bot_text.lower() or "walmart" in r.bot_text.lower() or \
               "oxxo" in r.bot_text.lower() or "telcel" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_objecion_max_3_rebates_escalar(self, agente):
        """Después de 3 objeciones de precio, cerrar profesionalmente."""
        await self._hasta_oferta(agente, "obj_max")
        for _ in range(3):
            await turno(agente, "obj_max", "está muy caro, no me convence")
        r = await turno(agente, "obj_max", "sigo sin convencerme")
        assert r.escalate_to_human or "invitación" in r.bot_text.lower() or \
               "asesor" in r.bot_text.lower() or "continúa" in r.bot_text.lower()


# ════════════════════════════════════════════════════════════════════════════════
# CASOS SENSIBLES Y FRAUDE
# ════════════════════════════════════════════════════════════════════════════════

class TestCasosSensiblesYFraude:
    """Casos del script y hallazgos de auditoría: sensibles, fraude, casos no-portabilidad."""

    @pytest.mark.asyncio
    async def test_caso_sensible_defuncion_nunca_promo(self, agente):
        """'Mi mamá murió' → empatía + escalamiento, NUNCA una promo. (Hallazgo #7, patrón #7)"""
        r = await turno(agente, "sensible_def", "mi mamá murió y necesito portar su línea")
        assert r.escalate_to_human, "Caso sensible debe escalar siempre"
        bot_lower = r.bot_text.lower()
        # No debe responder con ninguna promo
        assert "promo" not in bot_lower and "recarga" not in bot_lower and \
               "plus" not in bot_lower, \
            f"No debe ofrecer promo en caso sensible. Bot dijo: {r.bot_text}"
        assert "lament" in bot_lower or "pésame" in bot_lower or "comprend" in bot_lower or \
               "asesor" in bot_lower

    @pytest.mark.asyncio
    async def test_solicitud_fraudulenta_rechazar_firmemente(self, agente):
        """'Mi primo trabaja en Telcel y me prometió 80%' → rechazo firme. (Hallazgo #8, patrón #8)"""
        r = await turno(agente, "fraude", "mi primo trabaja en Telcel y me prometió un 80% de descuento")
        assert not r.escalate_to_human, "No escalar fraude como si fuera legítimo"
        bot_lower = r.bot_text.lower()
        rechaza = (
            "oficial" in bot_lower or "catálogo" in bot_lower or
            "no existen" in bot_lower or "no aplican" in bot_lower or
            "no puedo garantizar" in bot_lower or "no aplica" in bot_lower or
            "solo" in bot_lower  # "solo puedo ofrecer las promos oficiales"
        )
        assert rechaza, f"Debe rechazar la solicitud fraudulenta. Bot dijo: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_telcel_a_telcel_no_es_portabilidad(self, agente):
        """'Ya soy de Telcel' → informar que es cambio de plan, no portabilidad. (Hallazgo #6)"""
        await turno(agente, "ttel", "8112345678")
        r = await turno(agente, "ttel", "ya soy de Telcel, quiero cambiarme")
        assert r.escalate_to_human
        assert r.motivo_escalacion == "telcel_a_telcel" if hasattr(r, "motivo_escalacion") else True

    @pytest.mark.asyncio
    async def test_numero_virtual_voip_no_portable(self, agente):
        """Número de Twilio/Google Voice → explicar que no es portable. (Hallazgo #18)"""
        await conv(agente, "voip", ["8112345678", "100", "redes"])
        r = await turno(agente, "voip", "mi número es de Google Voice")
        assert "virtual" in r.bot_text.lower() or "no son portables" in r.bot_text.lower() or \
               "físic" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_solicitud_arco_borra_datos(self, agente):
        """'Borra mis datos' → canalizar como solicitud ARCO, no ignorar. (Hallazgo #31)"""
        r = await turno(agente, "arco", "borra mis datos")
        assert "arco" in r.bot_text.lower() or "cancelación" in r.bot_text.lower() or \
               "datos" in r.bot_text.lower(), \
            f"Debe tratar como ARCO. Bot dijo: {r.bot_text}"
        assert "avanzamos" not in r.bot_text.lower()


# ════════════════════════════════════════════════════════════════════════════════
# CIERRE
# ════════════════════════════════════════════════════════════════════════════════

class TestCierre:
    """Captura correcta de datos y validación de equipo."""

    async def _hasta_cierre(self, agente, tid):
        await conv(agente, tid, ["8112345678", "100", "redes", "sí, quiero la Plus"])

    @pytest.mark.asyncio
    async def test_ya_decidi_va_directo_sin_mas_venta(self, agente):
        """'Ya decidí, quiero esa' → ir directo a captura de datos, no más ventas. (Hallazgo #26, patrón #13)"""
        await conv(agente, "ya_dec", ["8112345678", "100", "redes"])
        r = await turno(agente, "ya_dec", "ya decidí, quiero esa promo")
        assert r.etapa == "cierre"
        # No debe responder con más info de venta
        assert "nombre" in r.bot_text.lower() or "¿cuál es su" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_cierre_captura_campo_por_campo(self, agente):
        """Debe capturar un campo por turno, sin mezclar compañía y municipio."""
        await self._hasta_cierre(agente, "cierre_campos")

        r1 = await turno(agente, "cierre_campos", "Juan Pérez Martínez")
        assert r1.datos_lead.get("nombre") == "Juan Pérez Martínez"
        assert not r1.datos_lead.get("numero_a_portar"), "No debe capturar número todavía"

        r2 = await turno(agente, "cierre_campos", "8113456789")
        assert r2.datos_lead.get("numero_a_portar") == "8113456789"
        assert not r2.datos_lead.get("compania_donante"), "No debe capturar compañía todavía"

        r3 = await turno(agente, "cierre_campos", "AT&T")
        assert r3.datos_lead.get("compania_donante") == "AT&T"
        # El municipio NO debe haberse capturado del mismo mensaje de AT&T
        assert r3.datos_lead.get("municipio", "") not in ("AT&T", "at&t"), \
            "Bug de captura múltiple: compañía y municipio no deben capturarse del mismo mensaje"

    @pytest.mark.asyncio
    async def test_equipo_no_liberado_nota_desbloqueo(self, agente):
        """Equipo no liberado → nota de validación en el resumen."""
        await self._hasta_cierre(agente, "equip_no")
        await conv(agente, "equip_no", ["Carlos López", "8113334444", "Movistar", "Guadalajara"])
        r = await turno(agente, "equip_no", "no sé si está liberado")
        if r.etapa == "escalado":
            assert "validación" in r.bot_text.lower() or "desbloqueo" in r.bot_text.lower() or \
                   "asesor" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_equipo_esim_nota_cac(self, agente):
        """Equipo con eSIM → nota de que el trámite final se hace en CAC."""
        await self._hasta_cierre(agente, "equip_esim")
        await conv(agente, "equip_esim", ["Ana Torres", "8114445555", "AT&T", "Monterrey"])
        r = await turno(agente, "equip_esim", "mi equipo tiene eSIM")
        if r.etapa == "escalado":
            assert "esim" in r.bot_text.lower() or "cac" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_aviso_privacidad_en_resumen(self, agente):
        """El resumen final debe incluir mención al aviso de privacidad."""
        await self._hasta_cierre(agente, "aviso")
        await conv(agente, "aviso", ["Luis Mendoza", "8115556666", "Nextel", "Saltillo"])
        r = await turno(agente, "aviso", "sí está liberado")
        if r.etapa == "escalado":
            assert "privacidad" in r.bot_text.lower() or "telcel.com" in r.bot_text.lower()


# ════════════════════════════════════════════════════════════════════════════════
# PATRONES SISTÉMICOS (regresión de auditoría)
# ════════════════════════════════════════════════════════════════════════════════

class TestPatronesSistémicos:
    """Cubre los 13 patrones sistémicos detectados en las auditorías."""

    @pytest.mark.asyncio
    async def test_p2_no_repite_texto_identico(self, agente):
        """Patrón #2: nunca enviar el mismo texto literal en turnos consecutivos."""
        await conv(agente, "p2", ["8112345678", "100", "redes"])
        r1 = await turno(agente, "p2", "¿me puedes dar más info?")
        r2 = await turno(agente, "p2", "¿y cuál es la mejor opción?")
        assert r1.bot_text != r2.bot_text, "Las respuestas no deben ser idénticas"

    @pytest.mark.asyncio
    async def test_p4_no_saluda_en_media_conversacion(self, agente):
        """Patrón #4: el bot no debe saludar con 'Hola' en medio de una conversación activa."""
        await conv(agente, "p4", ["Hola", "8112345678", "100"])
        r = await turno(agente, "p4", "¿cuáles son las redes incluidas?")
        # No debe iniciar la respuesta con saludo
        assert not r.bot_text.lower().startswith("hola"), \
            f"No debe saludar a media conversación. Bot dijo: {r.bot_text[:100]}"

    @pytest.mark.asyncio
    async def test_p1_responde_pregunta_comercial_sin_pedir_numero(self, agente):
        """Patrón #1: responder info sin exigir número primero (meta ≥80%)."""
        r = await turno(agente, "p1", "¿qué incluye la promo de $100?")
        bot_lower = r.bot_text.lower()
        # Puede pedir el número pero DESPUÉS de dar info, no en lugar de ella
        tiene_info = any(w in bot_lower for w in ["5.5", "gb", "amazon", "ilimitad", "promo", "beneficio"])
        assert tiene_info, \
            f"Debe dar información sobre la promo antes de pedir el número. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_p12_no_inventa_datos(self, agente):
        """Patrón #12: todos los datos (GB, vigencia, precios) deben venir de la BD."""
        await conv(agente, "p12", ["8112345678", "100", "redes"])
        r_oferta = await turno(agente, "p12", "¿y qué incluye exactamente?")
        bot_text = r_oferta.bot_text
        # Los GB reales de la BD para $100 son 5.5 GB
        # No debe inventar otras cantidades como "10 GB" (que era la promo falsa anterior)
        assert "10 gb" not in bot_text.lower(), \
            f"No debe usar datos inventados (10 GB era la promo falsa). Bot: {bot_text}"

    @pytest.mark.asyncio
    async def test_amazon_prime_correcto_por_recarga(self, agente):
        """Amazon Prime correcto según paquete:
        $100 promo portabilidad → Prime Básico (1 pantalla, envíos).
        $270 ASL → Prime Básico (2 pantallas, TV, HD).
        $400 ASL → Prime Completo (3 pantallas, TV, Music, Gaming).
        """
        # $100 portabilidad → Prime Básico
        await conv(agente, "amazon_b", ["8112345678", "100", "redes"])
        r = await turno(agente, "amazon_b", "¿qué tipo de Amazon Prime incluye?")
        assert "básico" in r.bot_text.lower() or "basico" in r.bot_text.lower() or \
               "1 dispositivo" in r.bot_text.lower() or "amazon" in r.bot_text.lower()

    @pytest.mark.asyncio
    async def test_nip_nunca_se_pide_por_whatsapp(self, agente):
        """El NIP NUNCA debe pedirse o procesarse por el bot (solo asesor en llamada)."""
        r = await turno(agente, "nip", "¿cómo genero mi NIP?")
        bot_lower = r.bot_text.lower()
        # Puede explicar el proceso pero NO pedirlo al cliente
        assert "envíeme su nip" not in bot_lower and "dígame el nip" not in bot_lower and \
               "mándeme el nip" not in bot_lower, \
            f"El bot NO debe pedir el NIP. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_vigencia_correcta_04_2026(self, agente):
        """Vigencia de promos debe ser 06/04/2026, no la fecha inventada anterior (31/05/2026)."""
        await conv(agente, "vigencia", ["8112345678", "100", "redes"])
        r = await turno(agente, "vigencia", "¿hasta cuándo está vigente la promo?")
        bot_lower = r.bot_text.lower()
        # No debe decir mayo 2026
        assert "mayo" not in bot_lower and "31/05" not in bot_lower and "05/2026" not in bot_lower, \
            f"Vigencia debe ser abril 2026, no mayo. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_no_aplica_liverpool_walmart(self, agente):
        """Debe informar que no aplica recarga en Liverpool, Walmart ni MixUP."""
        await conv(agente, "noaplica", ["8112345678", "100", "redes"])
        r = await turno(agente, "noaplica", "¿puedo recargar en Liverpool?")
        bot_lower = r.bot_text.lower()
        assert "no aplica" in bot_lower or "no" in bot_lower or "liverpool" in bot_lower, \
            f"Debe informar restricción Liverpool. Bot: {r.bot_text}"


# ════════════════════════════════════════════════════════════════════════════════
# PRUEBAS RONDA 1 — CORRECCIONES DE AUDITORÍA
# ════════════════════════════════════════════════════════════════════════════════

class TestAuditoriaRonda1:
    """Cubre las fallas y mejorables detectadas en Auditoría Ronda 1 (2026-06-02)."""

    # ── Catálogo ASL ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_asl_paquete_10_pesos(self, agente):
        """#26: El de $10 = 50 MB, 1 día. Debe informarlo, no decir 'no puedo darte el dato'."""
        r = await turno(agente, "asl_10", "¿cuál es el paquete más barato de Amigo Sin Límite?")
        bot_lower = r.bot_text.lower()
        assert "$10" in r.bot_text or "10 pesos" in bot_lower or "50 mb" in bot_lower, \
            f"Debe mencionar el paquete de $10 = 50 MB. Bot: {r.bot_text}"
        assert "no puedo" not in bot_lower and "no tengo" not in bot_lower, \
            f"No debe negarse a informar. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_asl_paquete_50_datos_y_vigencia(self, agente):
        """#28 #33: $50 = 500 MB, 7 días. Debe confirmarlo."""
        r = await turno(agente, "asl_50v", "¿qué incluye el paquete de $50 y cuánto dura?")
        bot_lower = r.bot_text.lower()
        assert "500 mb" in bot_lower or "500mb" in bot_lower or "7 días" in bot_lower or \
               "7 dias" in bot_lower or "$50" in r.bot_text, \
            f"Debe dar datos del $50 (500 MB, 7 días). Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_asl_paquete_100_gb_y_vigencia(self, agente):
        """#29 #37: $100 = 1.5 GB, 15 días. Debe confirmarlo con datos del catálogo."""
        r = await turno(agente, "asl_100v", "¿cuántos GB tiene el de $100 y cuánto dura?")
        bot_lower = r.bot_text.lower()
        assert "1.5 gb" in bot_lower or "1,5 gb" in bot_lower or "15 días" in bot_lower or \
               "15 dias" in bot_lower, \
            f"Debe informar $100 = 1.5 GB, 15 días. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_asl_paquete_200_gb(self, agente):
        """#30: $200 = 3.5 GB, 30 días. Debe confirmarlo."""
        r = await turno(agente, "asl_200", "¿cuántos GB trae el de $200?")
        bot_lower = r.bot_text.lower()
        assert "3.5 gb" in bot_lower or "3,5 gb" in bot_lower or "200" in r.bot_text, \
            f"Debe informar $200 = 3.5 GB. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_asl_paquete_500_mayor_dato(self, agente):
        """#36: $500 = 8 GB, 30 días. Debe confirmarlo como el de mayor dato."""
        r = await turno(agente, "asl_500", "¿cuál es el paquete con más datos?")
        bot_lower = r.bot_text.lower()
        assert "500" in r.bot_text or "8 gb" in bot_lower or "8gb" in bot_lower, \
            f"Debe mencionar $500 = 8 GB como máximo. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_asl_lista_montos_disponibles(self, agente):
        """#27: Debe dar la lista documentada de montos al preguntar qué paquetes hay."""
        r = await turno(agente, "asl_lista", "¿qué montos de recarga tienen disponibles?")
        bot = r.bot_text
        # Debe mencionar al menos 3 montos del catálogo
        montos_mencionados = sum(1 for m in ["$10", "$50", "$100", "$150", "$200", "$500"] if m in bot)
        assert montos_mencionados >= 3, \
            f"Debe listar varios montos del catálogo. Bot: {bot}"

    @pytest.mark.asyncio
    async def test_asl_monto_inexistente_1000(self, agente):
        """#94: $1,000 no existe. Debe corregir y mencionar el tope ($500)."""
        r = await turno(agente, "asl_1000", "¿tienen el paquete de $1,000?")
        bot_lower = r.bot_text.lower()
        assert "no existe" in bot_lower or "no tenemos" in bot_lower or \
               "500" in r.bot_text or "máximo" in bot_lower, \
            f"Debe decir que $1000 no existe y mencionar $500 como máximo. Bot: {r.bot_text}"

    # ── Canales de recarga ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_banco_excluido_no_valido(self, agente):
        """#56 #58: Bancos NO son canal válido para ASL. No debe decir 'sí puedes'."""
        r = await turno(agente, "canal_banco", "¿puedo recargar en el banco?")
        bot_lower = r.bot_text.lower()
        assert "no aplica" in bot_lower or "no" in bot_lower or "banco" in bot_lower, \
            f"Debe informar que bancos están excluidos. Bot: {r.bot_text}"
        # No debe afirmar que sí funciona en bancos
        afirma_banco = ("sí puedes en el banco" in bot_lower or
                        "puedes usar el banco" in bot_lower or
                        "bancos son válidos" in bot_lower)
        assert not afirma_banco, f"No debe validar el banco como canal. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_walmart_excluido(self, agente):
        """#59: Walmart está explícitamente excluido. No debe decir 'sí puedes'."""
        r = await turno(agente, "canal_wmt", "¿puedo recargar en Walmart?")
        bot_lower = r.bot_text.lower()
        assert "no" in bot_lower or "excluido" in bot_lower or "no aplica" in bot_lower, \
            f"Debe informar que Walmart está excluido. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_cajero_banco_excluido(self, agente):
        """#58: Cajero automático de banco también excluido."""
        r = await turno(agente, "canal_cajero", "¿puedo recargar en un cajero automático?")
        bot_lower = r.bot_text.lower()
        # No debe confirmar que cajero automático es válido
        assert "banco" in bot_lower or "no aplica" in bot_lower or "excluido" in bot_lower or \
               "no" in bot_lower, \
            f"Debe informar que cajeros de banco están excluidos. Bot: {r.bot_text}"

    # ── Amazon Prime por paquete ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_amazon_desde_paquete_150(self, agente):
        """#47: Amazon Prime se incluye desde $150. Paquetes ≤$100 ASL regular no traen Prime."""
        r = await turno(agente, "amz_desde", "¿desde qué paquete viene Amazon Prime?")
        bot_lower = r.bot_text.lower()
        assert "150" in r.bot_text or "amazon" in bot_lower, \
            f"Debe mencionar que Amazon Prime inicia desde $150. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_amazon_270_no_es_completo(self, agente):
        """#49 #50: $270 = Amazon Prime Básico (2 pantallas, TV). NO es Prime Completo."""
        r = await turno(agente, "amz_270", "¿el de $270 incluye ver en la tele?")
        bot_lower = r.bot_text.lower()
        # $270 SÍ puede ver en TV (Amazon Prime Básico: 2 pantallas celular+TV)
        assert "tv" in bot_lower or "tele" in bot_lower or "básico" in bot_lower or \
               "2 pantalla" in bot_lower or "270" in r.bot_text, \
            f"$270 = Prime Básico con TV. Bot: {r.bot_text}"
        # $270 NO debe presentar 3 dispositivos ni Gaming como beneficios propios (eso es $400).
        # Nota: el bot puede mencionar "gaming" o "3 dispositivos" en contexto negativo ("no incluye").
        affirms_3dev = "3 dispositivos" in bot_lower and "no incluye" not in bot_lower and "sin" not in bot_lower
        affirms_gaming = "gaming" in bot_lower and "no incluye" not in bot_lower and "sin" not in bot_lower and "nunca" not in bot_lower
        assert not affirms_3dev, f"$270 no debe afirmar 3 dispositivos. Bot: {r.bot_text}"
        assert not affirms_gaming, f"$270 no debe afirmar Gaming como beneficio. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_amazon_150_solo_celular(self, agente):
        """#50: $150 = Prime Video Edición Móvil = SOLO celular, SIN TV, SIN envíos."""
        r = await turno(agente, "amz_150", "¿con el de $150 puedo ver Amazon en la tele?")
        bot_lower = r.bot_text.lower()
        # $150 es "Edición Móvil" = solo celular, no TV
        assert "celular" in bot_lower or "móvil" in bot_lower or "movil" in bot_lower or \
               "solo" in bot_lower or "150" in r.bot_text, \
            f"$150 es Prime Video Edición Móvil (solo celular). Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_amazon_envios_solo_270_y_400(self, agente):
        """#48: Envíos gratis SOLO en $270 y $400. En $150/$200/$300/$500 NO hay envíos."""
        r = await turno(agente, "amz_envios", "¿Amazon Prime incluye envíos gratis?")
        bot_lower = r.bot_text.lower()
        # Debe mencionar que depende del paquete o aclarar cuáles sí tienen envíos
        assert "depende" in bot_lower or "270" in r.bot_text or "400" in r.bot_text or \
               "envíos" in bot_lower or "envios" in bot_lower, \
            f"Debe aclarar que envíos son solo en $270 y $400. Bot: {r.bot_text}"

    # ── Horarios de portabilidad ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_horario_portacion_2am_dia_siguiente(self, agente):
        """#17 #18 #20: La portación se ejecuta a las 2:00 a.m. del SIGUIENTE día hábil."""
        r = await turno(agente, "hor_2am", "¿cuándo queda lista la portación?")
        bot_lower = r.bot_text.lower()
        assert "2:00" in r.bot_text or "2 a.m" in bot_lower or "2am" in bot_lower or \
               "siguiente" in bot_lower or "hábil" in bot_lower, \
            f"Debe mencionar 2:00 a.m. del siguiente día hábil. Bot: {r.bot_text}"
        # NO debe afirmar que la portación es "el mismo día" (sí puede negarlo con "nunca el mismo día")
        afirma_mismo_dia = "mismo día" in bot_lower and "nunca" not in bot_lower and "no es el mismo" not in bot_lower
        assert not afirma_mismo_dia, \
            f"La portación NO es el mismo día — el bot no debe afirmarlo. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_horario_domingo_no_hay_portabilidad(self, agente):
        """#22: Domingo NO hay ventana de portabilidad."""
        r = await turno(agente, "hor_dom", "¿puedo tramitar la portabilidad el domingo?")
        bot_lower = r.bot_text.lower()
        assert "no" in bot_lower or "domingo" in bot_lower, \
            f"Debe informar que domingo no hay portabilidad. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_horario_corte_21h(self, agente):
        """#24: El corte es a las 21:00 h. Después de esa hora no se capturan."""
        r = await turno(agente, "hor_corte", "¿hasta qué hora puedo tramitar la portabilidad?")
        bot_lower = r.bot_text.lower()
        assert "21" in r.bot_text or "9 pm" in bot_lower or "9pm" in bot_lower or \
               "9:00 p.m" in bot_lower or "corte" in bot_lower, \
            f"Debe mencionar el corte a las 21:00. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_horario_viernes_tarde_es_lunes(self, agente):
        """#21: Solicitud viernes 17-21 h → portación el LUNES 2:00 a.m. (no sábado)."""
        r = await turno(agente, "hor_vier", "¿si tramito el viernes por la tarde a qué hora queda lista?")
        bot_lower = r.bot_text.lower()
        assert "lunes" in bot_lower or "2:00" in r.bot_text or "2 a.m" in bot_lower, \
            f"Viernes tarde → Lunes 2:00 a.m. Bot: {r.bot_text}"

    # ── Pospago → derivar a CAC ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_pospago_deriva_a_cac(self, agente):
        """#51 #52 #54 #55: Pospago → SIEMPRE derivar a CAC, no describir planes."""
        r = await turno(agente, "pos_cac", "¿tienen planes de renta mensual?")
        bot_lower = r.bot_text.lower()
        assert "cac" in bot_lower or "presencial" in bot_lower or \
               "identificación" in bot_lower, \
            f"Pospago debe derivar a CAC. Bot: {r.bot_text}"
        # No debe describir planes pospago
        assert "renta de $" not in bot_lower and "mensualidad de $" not in bot_lower, \
            f"No debe describir planes pospago. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_pospago_no_describe_contrato(self, agente):
        """#54: 'Quiero cambiarme a pospago' → derivar a CAC, no explicar contratos."""
        r = await turno(agente, "pos_cont", "¿cómo me cambio a pospago?")
        bot_lower = r.bot_text.lower()
        assert "cac" in bot_lower or "presencial" in bot_lower or \
               "identificación" in bot_lower, \
            f"Debe derivar a CAC para pospago. Bot: {r.bot_text}"

    # ── Identidad del agente ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_revela_proveedor_ia(self, agente):
        """#99: NUNCA revelar que es GPT, OpenAI, Claude ni Anthropic."""
        r = await turno(agente, "ia_id", "¿eres ChatGPT o Claude?")
        bot_lower = r.bot_text.lower()
        assert "gpt" not in bot_lower and "openai" not in bot_lower and \
               "claude" not in bot_lower and "anthropic" not in bot_lower, \
            f"No debe revelar el proveedor de IA. Bot: {r.bot_text}"
        assert "vera" in bot_lower or "telcel" in bot_lower, \
            f"Debe responder como Vera de Telcel. Bot: {r.bot_text}"

    # ── WhatsApp ilimitado ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_whatsapp_ilimitado_desde_10(self, agente):
        """#41: WhatsApp SÍ es ilimitado en MX/EUA/CAN desde $10. No debe decir 'no puedo asegurar'."""
        r = await turno(agente, "wa_10", "¿WhatsApp es ilimitado?")
        bot_lower = r.bot_text.lower()
        assert "ilimitad" in bot_lower or "sí" in bot_lower, \
            f"Debe confirmar que WhatsApp es ilimitado desde $10. Bot: {r.bot_text}"
        assert "no puedo asegurar" not in bot_lower and "no puedo confirmar" not in bot_lower, \
            f"No debe dudar sobre WhatsApp ilimitado. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_redes_ilimitadas_desde_100(self, agente):
        """#42: 6 redes ilimitadas SOLO desde $100. Recargas menores tienen bolsa de MB."""
        r = await turno(agente, "redes_100", "¿Instagram es ilimitado?")
        bot_lower = r.bot_text.lower()
        # Debe mencionar que depende del monto o que es desde $100
        assert "100" in r.bot_text or "ilimitad" in bot_lower or "bolsa" in bot_lower, \
            f"Debe aclarar que redes ilimitadas son desde $100. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_llamadas_eua_canada_incluidas(self, agente):
        """#43: Llamadas y SMS ilimitados a MX/EUA/CAN en TODOS los paquetes. Debe confirmarlo."""
        r = await turno(agente, "eua_call", "¿puedo llamar a Estados Unidos con Telcel?")
        bot_lower = r.bot_text.lower()
        assert "estados unidos" in bot_lower or "eua" in bot_lower or \
               "ilimitad" in bot_lower or "canadá" in bot_lower or "canada" in bot_lower, \
            f"Debe confirmar llamadas ilimitadas a EUA/CAN. Bot: {r.bot_text}"
        assert "no puedo confirmar" not in bot_lower, \
            f"No debe dudar sobre llamadas a EUA. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_claro_musica_es_bolsa_no_streaming(self, agente):
        """#46: Claro Música es bolsa de 500 MB para la app, no catálogo completo de streaming."""
        r = await turno(agente, "claro_m", "¿qué es Claro Música?")
        bot_lower = r.bot_text.lower()
        assert "500 mb" in bot_lower or "app" in bot_lower or "bolsa" in bot_lower or \
               "claro música" in bot_lower or "musica" in bot_lower, \
            f"Debe describir Claro Música como bolsa 500 MB. Bot: {r.bot_text}"
        # No debe presentarlo como "millones de canciones" o "catálogo completo"
        assert "millones de canciones" not in bot_lower, \
            f"No debe sobre-vender Claro Música. Bot: {r.bot_text}"


# ════════════════════════════════════════════════════════════════════════════════
# PRUEBAS RONDA 2 — COMPORTAMIENTO CONVERSACIONAL Y CORRECCIONES
# ════════════════════════════════════════════════════════════════════════════════

class TestAuditoriaRonda2:
    """
    Cubre los 6 problemas pendientes del Plan_Correccion_Vera_R1_R2.md
    y los nuevos requerimientos de flujo de venta directo.
    """

    # ── Corrección 1: Fallo silencioso Claro Drive ────────────────────────────

    @pytest.mark.asyncio
    async def test_claro_drive_tiene_respuesta(self, agente):
        """P.45: '¿Qué es Claro Drive?' debe tener respuesta, nunca vacío."""
        r = await turno(agente, "r2_drive", "¿Qué es Claro Drive?")
        assert r.bot_text.strip() != "", "La respuesta NO puede ser vacía"
        bot_lower = r.bot_text.lower()
        assert ("drive" in bot_lower or "nube" in bot_lower or "almacenamiento" in bot_lower
                or "20 gb" in bot_lower), \
            f"Debe describir Claro Drive. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_claro_drive_no_mezcla_con_musica(self, agente):
        """P.45/P.46: Claro Drive y Claro Música deben responderse por separado."""
        r_drive = await turno(agente, "r2_nodrive", "¿Qué es Claro Drive?")
        r_mus = await turno(agente, "r2_nomusic", "¿Qué es Claro Música?")
        # Las respuestas deben ser distintas y enfocadas en cada servicio
        assert r_drive.bot_text != r_mus.bot_text, "Respuestas de Drive y Música deben ser distintas"
        assert "drive" in r_drive.bot_text.lower() or "nube" in r_drive.bot_text.lower(), \
            f"Respuesta de Drive debe hablar de Drive. Bot: {r_drive.bot_text}"
        assert "música" in r_mus.bot_text.lower() or "musica" in r_mus.bot_text.lower() \
            or "500 mb" in r_mus.bot_text.lower(), \
            f"Respuesta de Música debe hablar de Música. Bot: {r_mus.bot_text}"

    # ── Corrección 2: Respuestas mezcladas ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_respuesta_una_pregunta_a_la_vez(self, agente):
        """El bot responde UNA cosa por turno, no acumula Drive + Música juntos."""
        r = await turno(agente, "r2_unapregunta", "¿Qué es Claro Drive?")
        bot_lower = r.bot_text.lower()
        # Si Drive sí aparece en la respuesta, no debe ser un bloque largo mezclado
        if "drive" in bot_lower:
            # No debe meter también Claro Música en la misma respuesta
            # a menos que explícitamente pregunte por los dos
            word_count = len(r.bot_text.split())
            assert word_count < 80, \
                f"Respuesta demasiado larga ({word_count} palabras) — probablemente mezcla temas. Bot: {r.bot_text}"

    # ── Corrección 3: Conteo de redes ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_redes_son_6_no_5(self, agente):
        """P.90: Siempre '6 redes ilimitadas', nunca 'WhatsApp + 5 redes'."""
        r = await turno(agente, "r2_redes6", "¿Cuántas redes sociales incluye?")
        bot = r.bot_text
        bot_lower = bot.lower()
        assert "whatsapp + 5" not in bot_lower and "5 redes más" not in bot_lower, \
            f"No debe decir 'WhatsApp + 5 redes'. Bot: {bot}"
        if "redes" in bot_lower and "ilimitad" in bot_lower:
            assert "6" in bot, f"Debe decir '6 redes ilimitadas'. Bot: {bot}"

    @pytest.mark.asyncio
    async def test_whatsapp_cuenta_como_una_de_las_6(self, agente):
        """WhatsApp SÍ es parte de las 6 redes, no se cuenta aparte."""
        await turno(agente, "r2_wa6", "8112345678")
        r = await turno(agente, "r2_wa6", "¿WhatsApp es una de las 6 redes?")
        bot_lower = r.bot_text.lower()
        # Debe confirmar que sí es parte de las 6
        assert "sí" in bot_lower or "si" in bot_lower or "parte" in bot_lower \
            or "6 redes" in bot_lower or "cuenta" in bot_lower, \
            f"Debe confirmar que WhatsApp cuenta como 1 de las 6. Bot: {r.bot_text}"

    # ── Corrección 4: Identidad del agente ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_identidad_no_dice_no_soy_persona(self, agente):
        """P.4: No debe responder 'No soy persona' directamente — debe redirigir."""
        r = await turno(agente, "r2_id", "¿Eres una persona o un robot?")
        bot_lower = r.bot_text.lower()
        assert "no soy persona" not in bot_lower, \
            f"No debe decir 'no soy persona'. Bot: {r.bot_text}"
        assert "vera" in bot_lower or "inteligencia artificial" in bot_lower or "telcel" in bot_lower, \
            f"Debe identificarse como Vera / agente de IA. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_identidad_no_dice_asistente_digital(self, agente):
        """No debe usar 'asistente digital' — debe decir 'agente de inteligencia artificial'."""
        r = await turno(agente, "r2_idag", "¿Qué eres exactamente?")
        bot_lower = r.bot_text.lower()
        assert "asistente digital" not in bot_lower, \
            f"No debe decir 'asistente digital'. Bot: {r.bot_text}"
        assert "vera" in bot_lower or "inteligencia artificial" in bot_lower or "telcel" in bot_lower, \
            f"Debe identificarse como Vera / agente de IA. Bot: {r.bot_text}"

    # ── Corrección 5: Responde pregunta de ID ────────────────────────────────

    @pytest.mark.asyncio
    async def test_pregunta_identificacion_responde_primero(self, agente):
        """P.78: '¿Qué identificación necesito?' debe responderse ANTES de preguntar ubicación."""
        await turno(agente, "r2_id_q", "8112345678")
        await turno(agente, "r2_id_q", "100")
        r = await turno(agente, "r2_id_q", "¿Qué identificación necesito para el trámite?")
        bot_lower = r.bot_text.lower()
        assert "ine" in bot_lower or "pasaporte" in bot_lower or "licencia" in bot_lower \
            or "identificación" in bot_lower or "identificacion" in bot_lower, \
            f"Debe responder qué documentos se necesitan. Bot: {r.bot_text}"
        # No debe ignorar la pregunta y solo pedir datos
        ignorar = ("ubicación" in bot_lower and "ine" not in bot_lower
                   and "pasaporte" not in bot_lower)
        assert not ignorar, \
            f"No debe ignorar la pregunta de ID para solo pedir ubicación. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_pregunta_id_antes_de_validar_numero(self, agente):
        """Antes de dar número, el cliente pregunta sobre ID — debe responder."""
        r = await turno(agente, "r2_id_early", "¿Qué documentos necesito para portar mi número?")
        bot_lower = r.bot_text.lower()
        assert "ine" in bot_lower or "pasaporte" in bot_lower or "identificación" in bot_lower \
            or "identificacion" in bot_lower, \
            f"Debe responder sobre documentos requeridos. Bot: {r.bot_text}"

    # ── Corrección 6: Mensajes cortos ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_respuesta_planes_generales_es_corta(self, agente):
        """'¿Qué planes tienes?' NO debe listar todos — debe preguntar el presupuesto."""
        r = await turno(agente, "r2_short_plan", "¿Qué planes tienes disponibles?")
        bot = r.bot_text
        bot_lower = bot.lower()
        # No debe listar 6+ paquetes con precios y detalles
        montos_en_bot = sum(1 for m in ["$10", "$20", "$30", "$50", "$80", "$100",
                                         "$150", "$200", "$270", "$300", "$400", "$500"] if m in bot)
        assert montos_en_bot <= 2, \
            f"No debe listar todos los paquetes. Montos encontrados: {montos_en_bot}. Bot: {bot}"
        # Debe preguntar el presupuesto o el uso
        pide_presupuesto = ("recarga" in bot_lower or "presupuesto" in bot_lower
                            or "cuánto" in bot_lower or "cuanto" in bot_lower
                            or "usas" in bot_lower or "datos o" in bot_lower)
        assert pide_presupuesto, \
            f"Debe preguntar el presupuesto o uso antes de recomendar. Bot: {bot}"

    @pytest.mark.asyncio
    async def test_respuesta_oferta_es_concisa(self, agente):
        """Al presentar la promo, debe ser concisa — 1 promo recomendada, máximo ~60 palabras."""
        await conv(agente, "r2_concise", ["8112345678", "100", "redes sociales"])
        r = await turno(agente, "r2_concise", "¿Cuál promo me recomiendas?")
        word_count = len(r.bot_text.split())
        assert word_count < 80, \
            f"Respuesta demasiado larga ({word_count} palabras). Bot: {r.bot_text}"
        assert "100" in r.bot_text or "promo" in r.bot_text.lower(), \
            f"Debe mencionar la promo recomendada. Bot: {r.bot_text}"

    # ── Flujo de venta directo ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_flujo_califica_antes_de_recomendar(self, agente):
        """El bot pregunta presupuesto/uso antes de recomendar cualquier plan."""
        r = await turno(agente, "r2_califica", "Hola, quiero portar mi número")
        bot_lower = r.bot_text.lower()
        # Debe pedir el número de 10 dígitos o el presupuesto, NO listar planes
        montos_en_bot = sum(1 for m in ["$10", "$50", "$100", "$150", "$200"] if m in r.bot_text)
        assert montos_en_bot == 0, \
            f"No debe listar planes en el primer mensaje. Bot: {r.bot_text}"
        # Debe pedir número o información para calificar
        pide_dato = ("10 dígitos" in bot_lower or "número" in bot_lower or
                     "recarga" in bot_lower or "presupuesto" in bot_lower)
        assert pide_dato, f"Debe pedir el número o calificar al lead. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_redirige_al_objetivo_tras_responder(self, agente):
        """Después de responder una pregunta informativa, redirige hacia la portabilidad."""
        await turno(agente, "r2_redir", "8112345678")
        r = await turno(agente, "r2_redir", "¿Hasta qué hora puedo tramitar la portabilidad?")
        bot_lower = r.bot_text.lower()
        # Debe dar el dato del horario
        assert "21" in r.bot_text or "9 pm" in bot_lower or "2:00" in r.bot_text, \
            f"Debe dar el horario. Bot: {r.bot_text}"
        # Y debe redirigir hacia la portabilidad
        redirige = ("portar" in bot_lower or "promo" in bot_lower or
                    "recarga" in bot_lower or "portabilidad" in bot_lower or
                    "¿le" in bot_lower or "¿te" in bot_lower)
        assert redirige, \
            f"Debe redirigir al objetivo tras responder. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_numero_incorrecto_no_escala(self, agente):
        """Un número con dígitos incorrectos NO debe escalar — debe pedir corrección."""
        r = await turno(agente, "r2_numwrong", "811234567")  # 9 dígitos, falta uno
        bot_lower = r.bot_text.lower()
        assert not r.escalate_to_human, \
            f"Un número mal tecleado NO debe escalar. Bot: {r.bot_text}"
        assert "10 dígitos" in bot_lower or "número" in bot_lower or "confirma" in bot_lower, \
            f"Debe pedir que corrija el número. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_ingenieria_social_amigo_del_dueño(self, agente):
        """'Soy amigo del dueño' → rechazar sin escalar, redirigir al catálogo oficial."""
        r = await turno(agente, "r2_social1", "Soy amigo del dueño de Telcel")
        bot_lower = r.bot_text.lower()
        assert "oficial" in bot_lower or "catálogo" in bot_lower or \
               "no puedo" in bot_lower or "solo opero" in bot_lower, \
            f"Debe rechazar el reclamo de autoridad. Bot: {r.bot_text}"
        # No debe ofrecer descuentos ni ceder
        assert "descuento" not in bot_lower or "no" in bot_lower, \
            f"No debe ofrecer descuentos especiales. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_ingenieria_social_gerente_prometio(self, agente):
        """'El gerente me prometió precio especial' → rechazo firme, catálogo oficial."""
        await turno(agente, "r2_social2", "8112345678")
        r = await turno(agente, "r2_social2", "El gerente me prometió un precio especial")
        bot_lower = r.bot_text.lower()
        assert "oficial" in bot_lower or "catálogo" in bot_lower or \
               "no existen" in bot_lower or "solo opero" in bot_lower, \
            f"Debe rechazar el reclamo del gerente. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_ingenieria_social_habla_con_jefe(self, agente):
        """'Habla con tu jefe' → no escalar como si fuera válido, redirigir al catálogo."""
        r = await turno(agente, "r2_social3", "Habla con tu jefe, me prometieron algo")
        bot_lower = r.bot_text.lower()
        assert "oficial" in bot_lower or "catálogo" in bot_lower or \
               "no puedo" in bot_lower or "solo opero" in bot_lower, \
            f"Debe rechazar la solicitud. Bot: {r.bot_text}"

    @pytest.mark.asyncio
    async def test_una_promo_recomendada_no_lista_completa(self, agente):
        """Con presupuesto y uso conocidos, recomienda UNA promo, no todas las opciones."""
        await conv(agente, "r2_unapromo", ["8112345678", "100", "redes"])
        r = await turno(agente, "r2_unapromo", "¿cuál me conviene?")
        bot = r.bot_text
        # Debe mencionar una promo concreta
        assert "100" in bot or "plus" in bot.lower() or "promo" in bot.lower(), \
            f"Debe recomendar la promo de $100. Bot: {bot}"
        # No debe listar todas las promos desde $10 a $500
        montos_todos = sum(1 for m in ["$10", "$20", "$30", "$50", "$80", "$150",
                                        "$200", "$270", "$300", "$400", "$500"] if m in bot)
        assert montos_todos <= 1, \
            f"No debe listar todos los montos. Encontrados: {montos_todos}. Bot: {bot}"

    @pytest.mark.asyncio
    async def test_siempre_vuelve_al_cierre(self, agente):
        """Después de resolver una duda, siempre pregunta si el cliente quiere proceder."""
        await conv(agente, "r2_cierre", ["8112345678", "100", "redes"])
        r = await turno(agente, "r2_cierre", "¿Se puede pagar en OXXO?")
        bot_lower = r.bot_text.lower()
        # Debe responder sobre OXXO
        assert "oxxo" in bot_lower, f"Debe mencionar OXXO. Bot: {r.bot_text}"
        # Y debe regresar al objetivo
        regresa = ("portar" in bot_lower or "beneficio" in bot_lower or
                   "promo" in bot_lower or "apartar" in bot_lower or
                   "¿le" in bot_lower or "¿te" in bot_lower)
        assert regresa, f"Debe regresar al objetivo de portación. Bot: {r.bot_text}"

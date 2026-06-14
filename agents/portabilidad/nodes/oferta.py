"""Nodo de oferta: presenta las promos reales y detecta intención de compra u objeción."""

import logging
import re

from langchain_core.messages import AIMessage, SystemMessage

from agents.llm import get_llm
from agents.portabilidad.context import (
    AMAZON_PRIME_BY_PACKAGE,
    ANTI_RENDICION,
    CLARO_DRIVE_MUSICA,
    FORMAT_RULES,
    HARD_RULES,
    ID_DOCS_INFO,
    OFFER_TEMPLATE,
    PORTABILITY_SCHEDULE,
)
from agents.portabilidad.state import PortabilidadState
from agents.portabilidad.utils import render_prompt, split_msg
from integrations.postgres import client as db

logger = logging.getLogger(__name__)

_BUY_WORDS = [
    "sí", "si", "quiero", "acepto", "adelante", "vamos", "ok", "dale", "listo",
    "me interesa", "claro que sí", "apúnteme", "anóteme", "confirmado", "procede",
    "la quiero", "esa me gusta", "me convenciste", "va", "bueno", "de acuerdo",
]


def _has_buy_intent(lower: str) -> bool:
    """Detecta intención de compra con word boundaries para palabras cortas."""
    for w in _BUY_WORDS:
        if " " in w:
            if w in lower:
                return True
        else:
            if re.search(rf"\b{re.escape(w)}\b", lower):
                return True
    return False
_CLOSE_PHRASES = ["ya decidí", "me quedo con", "la acepto", "esa opción", "quiero la de"]
_OBJECTION_WORDS = [
    "caro", "pensarlo", "esperar", "luego", "dudas", "no sé", "tal vez",
    "quizás", "más tiempo", "no me convence", "lo voy a pensar", "déjeme pensar",
    "piénselo", "no estoy seguro", "me parece mucho",
    "convencerme", "sin convenc", "no me convenció", "sigo sin",
]
_ESCALATION = ["asesor", "humano", "persona", "agente", "supervisor"]
_SEGUIMIENTO = [
    "llámame después", "llamame despues", "llámame mañana", "llamame mañana",
    "contáctenme", "contactenme", "me contactan", "me llaman", "llámenme", "llamenme",
    "más adelante", "mas adelante", "en otro momento", "luego te confirmo",
    "mañana te digo", "ahorita no puedo", "ahorita no", "después me comunico",
    "me comunico después", "me comunico despues", "ya me comunico",
    "cuando pueda", "cuando esté listo", "cuando este listo",
]
_TELCEL_TELCEL = ["ya soy de telcel", "tengo telcel", "soy cliente de telcel", "ya tengo telcel"]
_TITULARIDAD = ["titularidad", "a nombre de", "cambio de nombre", "transferir la línea"]
_VOIP = ["twilio", "google voice", "virtual", "voip", "número virtual"]
_SALDO_Q = ["saldo", "¿se transfiere", "me llevo mi saldo"]
_AMAZON_Q = ["amazon", "prime", "streaming"]
_RECARGA_MENOR = ["menos de 100", "50 pesos", "80 pesos", "recarga chica", "recarga menor"]
_EQUIPO_Q = ["liberado", "desbloqueado", "chip", "esim", "imei", "mi equipo"]
_POSPAGO = [
    "renta mensual", "plan pospago", "pospago", "postpago", "contrato mensual",
    "plan de renta", "plan con contrato", "factura mensual", "cambiar a pospago",
    "quiero un plan", "plan de $", "mensualidad",
]
_CANALES_Q = ["recargar", "donde recargo", "dónde recargo", "pagar", "donde pago",
              "banco", "bancos", "walmart", "liverpool", "mixup", "oxxo", "cajero"]
_HORARIO_Q = ["cuándo", "cuando", "cuanto tarda", "cuánto tarda", "horas",
              "portación", "portacion", "se ejecuta", "queda lista", "domingo"]
_CAC_Q = ["cac", "centro de atención", "sucursal", "oficina telcel", "donde ir",
          "dónde ir", "presencial"]
_ID_Q = [
    "identificación", "identificacion", "id oficial", "ine", "pasaporte", "licencia",
    "qué documento", "que documento", "qué necesito", "que necesito llevar",
    "qué papeles", "que papeles", "documentos necesarios", "requisitos",
]
_CLARO_DRIVE_Q = ["claro drive", "clarodrive", "almacenamiento", "nube", "guardar fotos",
                  "guardar archivos", "20 gb"]
_CLARO_MUSICA_Q = ["claro música", "claro musica", "app de música", "app de musica",
                   "500 mb música", "500 mb musica"]


async def _get_promos(recarga: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT nombre, recarga, beneficios, vigencia, condicion FROM promos WHERE activa = true ORDER BY recarga, nombre"
    )
    all_promos = [dict(r) for r in rows]

    if recarga <= 60:
        return [p for p in all_promos if p["recarga"] == 50]
    if recarga <= 90:
        return [p for p in all_promos if p["recarga"] == 80] or [p for p in all_promos if p["recarga"] == 50]
    if recarga <= 130:
        return [p for p in all_promos if p["recarga"] == 100]
    if recarga <= 175:
        return [p for p in all_promos if p["recarga"] == 150]
    if recarga <= 250:
        return [p for p in all_promos if p["recarga"] == 200]
    if recarga <= 290:
        return [p for p in all_promos if p["recarga"] == 270]
    if recarga <= 360:
        return [p for p in all_promos if p["recarga"] == 300]
    return [p for p in all_promos if p["recarga"] == 400]


def _format_promo(p: dict) -> str:
    sin_recarga = "Sin Recarga Inicial" in p["nombre"]
    tag = " ⭐ PRIMERA RECARGA GRATIS" if sin_recarga else ""
    lines = [f"📦 *{p['nombre']}*{tag}"]
    for b in p["beneficios"].split("|"):
        b = b.strip()
        if b:
            lines.append(f"  • {b}")
    lines.append(f"  📅 Vigente hasta {p['vigencia']}")
    lines.append(f"  📌 {p['condicion']}")
    return "\n".join(lines)


def _amazon_info_for_recarga(recarga: int) -> str:
    if recarga == 400:
        return (
            "Amazon Prime Completo: 3 pantallas (celular + TV), calidad HD/Ultra HD, "
            "Amazon Music, Prime Gaming y envíos gratis en Amazon."
        )
    if recarga == 270:
        return (
            "Amazon Prime Básico: 2 pantallas (celular + TV), calidad HD, "
            "envíos gratis en Amazon. No incluye Amazon Music ni Prime Gaming."
        )
    if recarga in (150, 200, 300, 500):
        return (
            "Prime Video Edición Móvil: 1 pantalla, solo celular, calidad estándar. "
            "No incluye envíos gratis, Amazon Music ni Prime Gaming."
        )
    # Paquetes < $150 no incluyen Amazon Prime (fuente: spec sec. 5.3)
    return ""


async def oferta_node(state: PortabilidadState) -> dict:
    messages = state.get("messages") or []
    datos = state.get("datos_lead") or {}
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()
    promo_actual = state.get("promo_elegida", "")
    recarga_num = int(datos.get("recarga_habitual") or 0)

    # ── Casos que no son portabilidad prepago ─────────────────────────────
    if any(p in lower for p in _TELCEL_TELCEL):
        return {
            "messages": [AIMessage(content=(
                "Si ya es cliente de Telcel, lo que necesita es un cambio de plan, no una portabilidad. "
                "Eso lo gestiona un asesor directamente. ¿Lo conecto?"
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "telcel_a_telcel",
        }

    # Pospago → derivar a CAC (regla 10.2)
    if any(w in lower for w in _POSPAGO):
        return {
            "messages": [AIMessage(content=(
                "Para planes de renta mensual (pospago) le invito a acudir a un CAC Telcel "
                "con su identificación oficial. El trámite es presencial. "
                "¿Le ubico el CAC más cercano a su municipio?"
            ))]
        }

    if any(p in lower for p in _TITULARIDAD):
        return {
            "messages": [AIMessage(content=(
                "El cambio de titularidad es un trámite distinto a la portabilidad. "
                "Un asesor puede orientarle mejor en ese proceso. ¿Lo conecto?"
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "cambio_titularidad",
        }

    if any(p in lower for p in _VOIP):
        return {
            "messages": [AIMessage(content=(
                "Los números virtuales (Twilio, Google Voice) no son portables a Telcel. "
                "Solo aplica la portabilidad desde líneas físicas de otro operador. "
                "¿Tiene otro número físico de una compañía como Movistar o AT&T?"
            ))],
        }

    # Escalación
    if any(w in lower for w in _ESCALATION):
        return {
            "messages": [AIMessage(content="Claro, lo conecto con un asesor. ¿Su nombre?")],
            "escalate_to_human": True,
            "motivo_escalacion": "solicitud_directa",
        }

    # Quiere ser contactado después
    if any(w in lower for w in _SEGUIMIENTO):
        return {
            "messages": [AIMessage(content="Perfecto, queda registrado. Un asesor te contactará cuando estés listo.")],
            "escalate_to_human": True,
            "motivo_escalacion": "seguimiento",
        }

    # Pregunta sobre saldo
    if any(w in lower for w in _SALDO_Q):
        return {
            "messages": [AIMessage(content=(
                "El saldo no es transferible. "
                "Si tiene saldo con su compañía actual, deberá agotarlo antes de portar. "
                "¿Tiene saldo en este momento?"
            ))]
        }

    # Pregunta sobre canales de recarga
    if any(w in lower for w in _CANALES_Q):
        return {
            "messages": [AIMessage(content=(
                "Los canales válidos para recargar con Amigo Sin Límite son:\n"
                "✅ CAC Telcel, Centros de Venta Telcel, Mi Telcel (app), www.Telcel.com, "
                "Distribuidores Autorizados y cadenas comerciales como OXXO y farmacias.\n"
                "❌ NO aplica en Liverpool, Walmart, MixUp ni en bancos (incluyendo apps bancarias y cajeros)."
            ))]
        }

    # Pregunta sobre horarios de portabilidad
    if any(w in lower for w in _HORARIO_Q):
        llm = get_llm()
        system = render_prompt("horarios", PORTABILITY_SCHEDULE=PORTABILITY_SCHEDULE, FORMAT_RULES=FORMAT_RULES)
        ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-4:]))
        return {"messages": split_msg(ai_msg.content)}

    # Pregunta sobre equipo
    if any(w in lower for w in _EQUIPO_Q):
        return {
            "messages": [AIMessage(content=(
                "Para portar necesita un equipo liberado o compatible con Telcel. "
                "¿Me dice la marca y modelo de su celular? "
                "Si viene de Movistar, AT&T o Unefon podemos conseguirle el código de desbloqueo. "
                "Si no está seguro, el asesor lo verifica en el CAC."
            ))]
        }

    # Pregunta sobre Amazon Prime
    if any(w in lower for w in _AMAZON_Q):
        prime_info = _amazon_info_for_recarga(recarga_num)
        if recarga_num == 0:
            # No sabemos el paquete, dar información general
            return {
                "messages": [AIMessage(content=(
                    "Amazon Prime se incluye desde el paquete de $150 (Prime Video Edición Móvil: 1 pantalla, solo celular).\n"
                    "• $270 → Amazon Prime Básico (2 pantallas, celular+TV, HD, envíos gratis)\n"
                    "• $400 → Amazon Prime Completo (3 pantallas, celular+TV, HD/Ultra HD, Music, Gaming, envíos)\n"
                    "• $150/$200/$300/$500 → Prime Video Edición Móvil (1 pantalla, solo celular, sin envíos)\n"
                    "Paquetes ≤$100 NO incluyen Amazon Prime (excepto la promo Portabilidad Plus $100 que sí lo incluye)."
                ))]
            }
        return {
            "messages": [AIMessage(content=(
                f"Con su paquete incluye: {prime_info}\n"
                "El link para activarlo le llega por SMS en 24-36 horas tras su primera recarga en Telcel. "
                "¿Le gustaría proceder con la portabilidad?"
            ))]
        }

    # Pregunta sobre documentos de identificación
    if any(w in lower for w in _ID_Q):
        return {
            "messages": [AIMessage(content=(
                "Para portarte necesitas una ID oficial vigente con foto: "
                "INE/IFE, Pasaporte o Licencia de conducir 😊\n"
                "Si otra persona va al CAC por ti, lleva su propio ID, "
                "carta de autorización simple y copia de tu ID."
            ))]
        }

    # Pregunta sobre Claro Drive
    if any(w in lower for w in _CLARO_DRIVE_Q):
        return {
            "messages": [AIMessage(content=(
                "Claro Drive es almacenamiento en la nube de 20 GB para fotos, "
                "videos, contactos y archivos 📂\n"
                "Se incluye desde $100 y se usa desde la app o en www.clarodrive.com."
            ))]
        }

    # Pregunta sobre Claro Música
    if any(w in lower for w in _CLARO_MUSICA_Q):
        return {
            "messages": [AIMessage(content=(
                "Claro Música es una bolsa de 500 MB para navegar dentro de la app 🎵\n"
                "No es streaming completo tipo Spotify; es una bolsa de datos dedicada. "
                "Incluida desde $150."
            ))]
        }

    # Pregunta sobre recargas menores
    if any(w in lower for w in _RECARGA_MENOR):
        return {
            "messages": [AIMessage(content=(
                "Sí puede recargar $50 o $80. Con esos montos obtiene una bolsa de MB para redes sociales "
                "(no son ilimitadas). Para tener 6 redes sociales ilimitadas y Amazon Prime, "
                "la recarga mínima es de $100 en la promo Portabilidad Plus. "
                "¿Le platico los beneficios exactos de cada opción?"
            ))]
        }

    # "Ya decidí" → ir directo a cierre
    if any(p in lower for p in _CLOSE_PHRASES):
        return {
            "messages": [AIMessage(content="¡Perfecto! Vamos directo. ¿Cuál es su nombre completo?")],
            "etapa": "cierre",
        }

    # Intención de compra con promo ya mostrada
    if promo_actual and _has_buy_intent(lower):
        return {
            "messages": [AIMessage(content=(
                "¡Buenísimo! 🎉 Para apartar tu beneficio necesito 3 datos:\n"
                "1) Tu nombre completo\n"
                "2) El número de 10 dígitos que vas a portar\n"
                "3) De qué compañía te vienes\n\n"
                "¿Me los compartes?"
            ))],
            "etapa": "cierre",
        }

    # Objeción → delegar al nodo de objeciones
    if any(w in lower for w in _OBJECTION_WORDS):
        from agents.portabilidad.nodes.objeciones import objeciones_node
        return await objeciones_node({**dict(state), "etapa": "objecion"})

    # Presentar / re-presentar la promo
    promos = await _get_promos(recarga_num)
    if not promos:
        rows = await db.fetch(
            "SELECT nombre, recarga, beneficios, vigencia, condicion FROM promos WHERE activa = true AND recarga = 100"
        )
        promos = [dict(r) for r in rows]

    llm = get_llm()
    promos_text = "\n\n".join(_format_promo(p) for p in promos)

    system = render_prompt(
        "oferta_principal",
        recarga_num=recarga_num,
        promos_text=promos_text,
        OFFER_TEMPLATE=OFFER_TEMPLATE,
        AMAZON_PRIME_BY_PACKAGE=AMAZON_PRIME_BY_PACKAGE,
        CLARO_DRIVE_MUSICA=CLARO_DRIVE_MUSICA,
        ID_DOCS_INFO=ID_DOCS_INFO,
        ANTI_RENDICION=ANTI_RENDICION,
        HARD_RULES=HARD_RULES,
        FORMAT_RULES=FORMAT_RULES,
    )

    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-6:]))
    promo_nombre = promos[0]["nombre"] if promos else promo_actual

    return {
        "messages": split_msg(ai_msg.content),
        "promo_elegida": promo_nombre,
    }

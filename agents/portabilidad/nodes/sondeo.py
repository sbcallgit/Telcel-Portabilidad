"""Sondeo: pregunta el monto de recarga y presenta comparativa de beneficios Telcel.

Flujo simplificado:
  1. ¿Cuánto recargas normalmente?
  2. Con ese dato → mostrar qué tiene hoy vs. qué tendría con Telcel (oferta puntual).
"""

import logging
import re

from langchain_core.messages import AIMessage, SystemMessage

from agents.llm import get_llm
from agents.portabilidad.utils import render_prompt, split_msg
from agents.portabilidad.context import (
    AMAZON_PRIME_BY_PACKAGE,
    ANTI_RENDICION,
    ASL_CATALOG,
    CHANNEL_RULES,
    CLARO_DRIVE_MUSICA,
    FORMAT_RULES,
    HARD_RULES,
    ID_DOCS_INFO,
    OFFER_TEMPLATE,
    PORTABILITY_SCHEDULE,
    SALES_APPROACH,
)
from agents.portabilidad.state import PortabilidadState
from integrations.postgres import client as db

logger = logging.getLogger(__name__)

_SENSITIVE = ["mamá", "papá", "murió", "falleció", "muerto", "difunto", "funeral", "accidente"]
_ESCALATION = ["asesor", "humano", "persona real", "agente", "supervisor", "hablar con alguien"]
_SEGUIMIENTO = [
    "llámame después", "llamame despues", "llámame mañana", "llamame mañana",
    "contáctenme", "contactenme", "me contactan", "me llaman", "llámenme", "llamenme",
    "más adelante", "mas adelante", "en otro momento", "luego te confirmo",
    "mañana te digo", "ahorita no puedo", "ahorita no", "después me comunico",
    "me comunico después", "me comunico despues", "ya me comunico",
    "cuando pueda", "cuando esté listo", "cuando este listo",
]
_FRAUD_OFFER = ["primo", "familiar", "conocido", "compadre"]
_FRAUD_CLAIM = ["prometió", "descuento especial", "80%", "90%", "gratis me dijeron", "me dijo mi"]
_POSPAGO = [
    "renta mensual", "plan pospago", "pospago", "postpago", "contrato mensual",
    "plan de renta", "plan con contrato", "factura mensual", "cambiar a pospago",
    "quiero un plan", "mensualidad",
]
_HORARIO_Q = ["cuándo", "cuando", "cuanto tarda", "cuánto tarda", "tiempo", "horas",
              "portación", "portacion", "se ejecuta", "queda lista", "domingo", "sábado noche",
              "viernes tarde"]
_CANALES_Q = ["recargar en", "donde recargo", "dónde recargo", "banco", "bancos",
              "walmart", "liverpool", "mixup", "oxxo", "cajero"]
_CAC_Q = ["cac", "centro de atención", "sucursal", "oficina telcel", "donde ir", "dónde ir"]
_ID_Q = [
    "identificación", "identificacion", "id oficial", "ine", "pasaporte", "licencia",
    "qué documento", "que documento", "qué necesito", "que necesito llevar",
    "qué papeles", "que papeles", "documentos", "requisitos",
]
_CLARO_DRIVE_Q = ["claro drive", "clarodrive", "almacenamiento", "nube", "guardar fotos",
                  "guardar archivos", "20 gb"]
_CLARO_MUSICA_Q = ["claro música", "claro musica", "música", "musica", "app de música",
                   "streaming", "canciones"]

_SOCIAL_ENGINEERING = [
    "amigo del dueño", "amigo del director", "amigo del gerente", "conoce al dueño",
    "conozco al dueño", "conozco al director", "trabajo en telcel", "soy empleado",
    "soy trabajador de telcel", "habla con tu jefe", "habla con el gerente",
    "habla con el encargado", "quiero hablar con el director", "hablar con el dueño",
    "el gerente me prometió", "el director me dijo", "el dueño me autorizó",
    "tengo una carta", "traigo una autorización especial", "ya hablé con el director",
    "soy socio de telcel", "soy accionista", "me mandó el corporativo",
]


def _extract_amount(text: str) -> int | None:
    match = re.search(r"\$?\s*(\d{2,3})\b", text)
    if match:
        v = int(match.group(1))
        if 30 <= v <= 500:
            return v
    return None


def _classify(recarga: int) -> str:
    if recarga >= 150:
        return "caliente"
    if recarga >= 100:
        return "tibio"
    return "frio"


async def _get_promos_para_oferta(recarga: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT nombre, recarga, beneficios, vigencia, condicion FROM promos WHERE activa = true ORDER BY recarga, nombre"
    )
    all_promos = [dict(r) for r in rows]

    if recarga <= 60:
        candidatos = [p for p in all_promos if p["recarga"] == 50]
    elif recarga <= 90:
        candidatos = [p for p in all_promos if p["recarga"] in (80, 50) and "Sin Recarga" in p["nombre"]]
        if not candidatos:
            candidatos = [p for p in all_promos if p["recarga"] == 80]
    elif recarga <= 130:
        candidatos = [p for p in all_promos if p["recarga"] == 100]
    elif recarga <= 175:
        candidatos = [p for p in all_promos if p["recarga"] == 150]
    elif recarga <= 250:
        candidatos = [p for p in all_promos if p["recarga"] == 200]
    elif recarga <= 290:
        candidatos = [p for p in all_promos if p["recarga"] == 270]
    elif recarga <= 360:
        candidatos = [p for p in all_promos if p["recarga"] == 300]
    else:
        candidatos = [p for p in all_promos if p["recarga"] == 400]

    return candidatos or all_promos[:2]


def _format_promo_completa(p: dict) -> str:
    sin_recarga = "Sin Recarga Inicial" in p["nombre"]
    encabezado = (
        f"🎁 *{p['nombre']}* — Recarga ${p['recarga']} {'(primera recarga GRATIS)' if sin_recarga else ''}\n"
    )
    beneficios = "\n".join(f"  • {b.strip()}" for b in p["beneficios"].split("|") if b.strip())
    return f"{encabezado}{beneficios}\n📌 {p['condicion']}"


async def sondeo_node(state: PortabilidadState) -> dict:
    messages = state.get("messages") or []
    datos = dict(state.get("datos_lead") or {})
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()
    # Caso sensible
    if any(w in lower for w in _SENSITIVE):
        return {
            "messages": [AIMessage(content=(
                "Lamentamos mucho lo que está atravesando. "
                "Lo conecto con un asesor para que lo oriente con más calma."
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "caso_sensible",
        }

    # Telcel→Telcel (no es portabilidad)
    _telcel_telcel = ["ya soy de telcel", "tengo telcel", "soy cliente de telcel", "ya tengo telcel"]
    if any(p in lower for p in _telcel_telcel):
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

    # Solicitud de asesor
    if any(w in lower for w in _ESCALATION):
        return {
            "messages": [AIMessage(content="Claro, lo conecto con un asesor. ¿Me dice su nombre?")],
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

    # Intento fraudulento
    if any(w in lower for w in _FRAUD_OFFER) and any(w in lower for w in _FRAUD_CLAIM):
        return {
            "messages": [AIMessage(content=(
                "Solo puedo ofrecerle las promociones del catálogo oficial de Telcel. "
                "No existen descuentos adicionales por conocidos o familiares. "
                "¿Le platico las promos reales disponibles?"
            ))]
        }

    # Solicitud ARCO
    if re.search(r"\b(borra|elimina|cancela|borrar|eliminar)\b.*dato", lower) or "ARCO" in user_text:
        return {
            "messages": [AIMessage(content=(
                "Recibido. Tiene derecho a solicitar la cancelación de sus datos (derecho ARCO). "
                "En breve lo contactamos para gestionar su solicitud formalmente."
            ))],
            "etapa": "fin",
        }

    # Preguntas sobre horarios de portabilidad
    if any(w in lower for w in _HORARIO_Q):
        llm = get_llm()
        system = render_prompt("horarios", PORTABILITY_SCHEDULE=PORTABILITY_SCHEDULE, FORMAT_RULES=FORMAT_RULES)
        ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-4:]))
        return {"messages": split_msg(ai_msg.content), "datos_lead": datos}

    # Preguntas sobre canales de recarga
    if any(w in lower for w in _CANALES_Q):
        return {
            "messages": [AIMessage(content=(
                "Los canales válidos para recargar con Amigo Sin Límite son:\n"
                "✅ CAC Telcel, Centros de Venta Telcel, Mi Telcel (app), www.Telcel.com, "
                "Distribuidores Autorizados y cadenas comerciales como OXXO y farmacias.\n"
                "❌ NO aplica en Liverpool, Walmart, MixUp ni en bancos (incluyendo apps bancarias y cajeros)."
            ))],
            "datos_lead": datos,
        }

    # Preguntas sobre identificación / documentos
    if any(w in lower for w in _ID_Q):
        return {
            "messages": [AIMessage(content=(
                "Para portar necesitas una identificación oficial vigente con foto: "
                "INE/IFE, Pasaporte mexicano o Licencia de conducir 😊\n"
                "Si otra persona va al CAC por ti, debe llevar su propio ID, "
                "carta de autorización simple y copia de tu ID."
            ))],
            "datos_lead": datos,
        }

    # Preguntas sobre Claro Drive
    if any(w in lower for w in _CLARO_DRIVE_Q):
        return {
            "messages": [AIMessage(content=(
                "Claro Drive es almacenamiento en la nube de 20 GB para guardar "
                "fotos, videos, contactos y archivos 📂\n"
                "Se incluye desde recargas de $100 y lo usas desde la app Claro Drive "
                "o en www.clarodrive.com."
            ))],
            "datos_lead": datos,
        }

    # Preguntas sobre Claro Música
    if any(w in lower for w in _CLARO_MUSICA_Q) and "drive" not in lower:
        return {
            "messages": [AIMessage(content=(
                "Claro Música es una bolsa de 500 MB de datos para navegar dentro "
                "de la app Claro Música 🎵\n"
                "No es un catálogo completo tipo Spotify; es una bolsa dedicada a esa app. "
                "Se incluye desde recargas de $150."
            ))],
            "datos_lead": datos,
        }

    # ── Recopilar recarga y presentar comparativa ──────────────────────────
    if not datos.get("recarga_habitual"):
        amount = _extract_amount(user_text)
        if amount:
            datos["recarga_habitual"] = str(amount)
            recarga = amount
            temperatura = _classify(recarga)
            promos = await _get_promos_para_oferta(recarga)
            promos_text = "\n\n".join(_format_promo_completa(p) for p in promos)

            llm = get_llm()
            system = render_prompt(
                "sondeo_con_recarga",
                recarga=recarga,
                promos_text=promos_text,
                ASL_CATALOG=ASL_CATALOG,
                AMAZON_PRIME_BY_PACKAGE=AMAZON_PRIME_BY_PACKAGE,
                OFFER_TEMPLATE=OFFER_TEMPLATE,
                ANTI_RENDICION=ANTI_RENDICION,
                HARD_RULES=HARD_RULES,
                FORMAT_RULES=FORMAT_RULES,
            )
            ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-4:]))

            return {
                "messages": split_msg(ai_msg.content),
                "datos_lead": datos,
                "temperatura": temperatura,
                "promo_elegida": promos[0]["nombre"] if promos else "",
                "etapa": "oferta",
            }

    # Ingeniería social / reclamo de autoridad falsa
    if any(p in lower for p in _SOCIAL_ENGINEERING):
        return {
            "messages": [AIMessage(content=(
                "Entiendo lo que comentas, pero no puedo procesar ese tipo de solicitudes. "
                "Solo opero con las promociones del catálogo oficial de Telcel. "
                "¿Le platico las opciones disponibles?"
            ))],
        }

    # ── Sondeo natural con Claude (aún no tenemos el monto de recarga) ─────
    llm = get_llm()
    recarga_c = datos.get("recarga_habitual", "desconocida")

    system = render_prompt(
        "sondeo_sin_recarga",
        recarga_c=recarga_c,
        ASL_CATALOG=ASL_CATALOG,
        AMAZON_PRIME_BY_PACKAGE=AMAZON_PRIME_BY_PACKAGE,
        PORTABILITY_SCHEDULE=PORTABILITY_SCHEDULE,
        CLARO_DRIVE_MUSICA=CLARO_DRIVE_MUSICA,
        ID_DOCS_INFO=ID_DOCS_INFO,
        ANTI_RENDICION=ANTI_RENDICION,
        HARD_RULES=HARD_RULES,
        FORMAT_RULES=FORMAT_RULES,
    )

    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-6:]))
    return {"messages": split_msg(ai_msg.content), "datos_lead": datos}

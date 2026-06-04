"""Nodo de objeciones: rebate hasta 3 veces usando el banco de objeciones de la BD."""

import logging

from langchain_core.messages import AIMessage, SystemMessage

from agents.llm import get_llm
from agents.portabilidad.utils import split_msg
from agents.portabilidad.context import FORMAT_RULES, HARD_RULES, OBJECTIONS_BANK
from agents.portabilidad.state import PortabilidadState
from integrations.postgres import client as db

logger = logging.getLogger(__name__)

_MAX_REBATES = 3
_SENSITIVE = ["mamá", "papá", "murió", "falleció", "muerto", "difunto", "funeral"]
_FRAUD_OFFER = ["primo", "familiar", "conocido", "compadre"]
_FRAUD_CLAIM = ["prometió", "descuento especial", "80%", "90%", "gratis"]
_BUY_WORDS = ["sí", "si ", "quiero", "acepto", "adelante", "ok", "dale", "listo",
              "me convenciste", "está bien", "va", "anótame"]
_ESCALATION = ["asesor", "humano", "persona real", "agente", "supervisor"]
_PRIVACY = ["borra", "elimina", "mis datos", "arco"]
_POSPAGO = [
    "renta mensual", "plan pospago", "pospago", "postpago", "contrato mensual",
    "plan de renta", "plan con contrato", "factura mensual", "cambiar a pospago",
    "mensualidad",
]


async def _find_objection(text: str) -> dict | None:
    """Busca la respuesta más relevante en el banco de objeciones por similitud de texto."""
    lower = text.lower()
    # Prioridad: buscar por categoría basado en palabras clave
    categoria = None
    if any(w in lower for w in ["caro", "precio", "cobr", "cost"]):
        categoria = "precio"
    elif any(w in lower for w in ["pensar", "pens", "luego", "tiempo", "esperar"]):
        categoria = "tiempo"
    elif any(w in lower for w in ["confiar", "confi", "segur", "miedo"]):
        categoria = "confianza"
    elif any(w in lower for w in ["recargué", "recargue", "recargu", "acabo de"]):
        categoria = "timing"
    elif any(w in lower for w in ["señal", "cobertura", "servicio", "red"]):
        categoria = "cobertura"
    elif any(w in lower for w in ["datos", "privacidad", "información personal"]):
        categoria = "privacidad"

    if categoria:
        row = await db.fetchrow(
            "SELECT texto, categoria, respuesta FROM objeciones WHERE categoria = $1 LIMIT 1",
            categoria,
        )
        if row:
            return dict(row)

    # Fallback: primera objeción disponible
    row = await db.fetchrow("SELECT texto, categoria, respuesta FROM objeciones LIMIT 1")
    return dict(row) if row else None


async def objeciones_node(state: PortabilidadState) -> dict:
    messages = state.get("messages") or []
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()
    rebates = state.get("objeciones_rebatidas") or 0
    promo = state.get("promo_elegida", "")
    datos = state.get("datos_lead") or {}

    # Caso sensible → escalar siempre
    if any(w in lower for w in _SENSITIVE):
        return {
            "messages": [AIMessage(content=(
                "Lamentamos mucho tu situación. "
                "Te conecto con un asesor que puede orientarte con más calma y empatía."
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "caso_sensible",
        }

    # Solicitud de privacidad / ARCO
    if any(w in lower for w in _PRIVACY):
        return {
            "messages": [AIMessage(content=(
                "Recibido. Tienes derecho a solicitar la cancelación de tus datos (derecho ARCO). "
                "Un asesor te contactará para gestionar tu solicitud formalmente."
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "solicitud_arco",
        }

    # Pospago → derivar a CAC
    if any(w in lower for w in _POSPAGO):
        return {
            "messages": [AIMessage(content=(
                "Para planes de renta mensual (pospago) le invito a acudir a un CAC Telcel "
                "con su identificación oficial. El trámite es presencial. "
                "¿Le ubico el CAC más cercano a su municipio?"
            ))]
        }

    # Intento fraudulento
    if any(w in lower for w in _FRAUD_OFFER) and any(w in lower for w in _FRAUD_CLAIM):
        return {
            "messages": [AIMessage(content=(
                "Entiendo lo que comentas, pero no existen descuentos especiales por conocidos o familiares. "
                "Las promos que tengo son las del catálogo oficial de Telcel. "
                "¿Quieres que repasemos las opciones disponibles?"
            ))]
        }

    # Solicitud directa de asesor
    if any(w in lower for w in _ESCALATION):
        return {
            "messages": [AIMessage(content="Claro, te conecto con un asesor. ¿Tu nombre?")],
            "escalate_to_human": True,
            "motivo_escalacion": "solicitud_directa",
        }

    # Intención de compra → cerrar
    if any(w in lower for w in _BUY_WORDS):
        return {
            "messages": [AIMessage(content="¡Perfecto! Vamos con los datos. ¿Cuál es tu nombre completo?")],
            "etapa": "cierre",
        }

    # Máximo de rebates alcanzado → cerrar con puerta abierta y escalar
    if rebates >= _MAX_REBATES:
        return {
            "messages": [AIMessage(content=(
                "Entiendo perfectamente. Te dejo aquí mi contacto por si más adelante "
                "quieres aprovechar la promo. ¡Que tengas excelente día! 🌟"
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "max_objeciones_alcanzado",
        }

    # Buscar respuesta en banco de objeciones
    objection = await _find_objection(user_text)

    llm = get_llm()
    base_response = objection["respuesta"] if objection else ""
    # Sustituir placeholders básicos
    if objection:
        vigencia = datos.get("vigencia", "pronto")
        beneficios = datos.get("beneficios", "los beneficios de la promo")
        base_response = base_response.replace("{vigencia}", str(vigencia)).replace("{beneficios}", beneficios)

    system = (
        "Eres Vera, asistente de Telcel para portabilidad. El cliente tiene una objeción.\n\n"
        f"Promo en discusión: {promo or 'portabilidad Telcel'}\n"
        f"Respuesta sugerida del banco de objeciones: {base_response or '(no disponible)'}\n\n"
        f"{OBJECTIONS_BANK}\n"
        f"{HARD_RULES}\n"
        f"{FORMAT_RULES}\n"
        "Construye una respuesta empática y convincente:\n"
        "- Reconoce la objeción\n"
        "- Usa la respuesta del OBJECTIONS_BANK más parecida a la objeción actual, adaptándola de forma natural\n"
        "- Si el cliente dice 'está caro' → mostrar que con la misma recarga tiene el triple de beneficios\n"
        "- Cierra con una pregunta que invite a seguir\n"
        "Tono cálido, sin presión excesiva."
    )

    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-6:]))

    return {
        "messages": split_msg(ai_msg.content),
        "objeciones_rebatidas": rebates + 1,
        "etapa": "oferta",
    }

"""Nodo de cierre: captura los 3 campos KPI obligatorios del cliente.

Campos KPI (bloqueantes para escalar — spec sec. 3.3):
  1. nombre completo
  2. número a portar (10 dígitos)
  3. compañía donante

Los campos adicionales (municipio, equipo) se enriquecen el payload si el cliente los da,
pero no bloquean el escalamiento al asesor.
"""

import logging
import re

from langchain_core.messages import AIMessage, SystemMessage

from agents.llm import get_llm
from agents.portabilidad.utils import render_prompt, split_msg
from agents.portabilidad.state import PortabilidadState

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")
_COMPANIAS = {
    "movistar": "Movistar",
    "att": "AT&T",
    "at&t": "AT&T",
    "nextel": "Nextel",
    "altan": "Altan/Bait",
    "bait": "Altan/Bait",
    "unefon": "Unefon",
    "izzi": "Izzi",
    "virgin": "Virgin Mobile",
    "flash": "Flash Mobile",
    "weex": "Weex",
    "oui": "Oui Mobile",
}
_LIBERADO_SI = ["sí", "si ", "liberado", "desbloqueado", "sí está", "funciona", "acepta chip", "lo probé", "ya está"]
_LIBERADO_NO = ["no", "no sé", "no lo sé", "no estoy seguro", "no sabe", "creo que no", "nunca lo probé"]
_ESIM = ["esim", "e-sim", "no tiene ranura", "no tiene slot"]
_ESCALATION = ["asesor", "humano", "persona real", "agente"]
_SEGUIMIENTO = [
    "llámame después", "llamame despues", "llámame mañana", "llamame mañana",
    "contáctenme", "contactenme", "me contactan", "me llaman", "llámenme", "llamenme",
    "más adelante", "mas adelante", "en otro momento", "luego te confirmo",
    "mañana te digo", "ahorita no puedo", "ahorita no", "después me comunico",
    "me comunico después", "me comunico despues", "ya me comunico",
    "cuando pueda", "cuando esté listo", "cuando este listo",
]


def _extract_phone(text: str) -> str | None:
    match = _PHONE_RE.search(text)
    if match:
        return match.group(1)
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) == 10 else None


def _extract_company(text: str) -> str | None:
    lower = text.lower()
    for key, name in _COMPANIAS.items():
        if key in lower:
            return name
    return None


def _next_pending(datos: dict) -> str | None:
    """Retorna el siguiente campo KPI obligatorio sin capturar."""
    for campo in ("nombre", "numero_a_portar", "compania_donante"):
        if not datos.get(campo):
            return campo
    return None


_PREGUNTAS = {
    "nombre": "¿Cuál es tu nombre completo?",
    "numero_a_portar": "¿Cuál es el número de 10 dígitos que vas a portar?",
    "compania_donante": "¿De qué compañía te vienes? (Movistar, AT&T, Nextel, Unefon, etc.)",
}

_AVISO_PRIVACIDAD = (
    "Le informo que cualquier dato personal que nos proporcione será tratado "
    "conforme al Aviso de Privacidad de Telcel, disponible en www.telcel.com."
)


async def cierre_node(state: PortabilidadState) -> dict:
    messages = state.get("messages") or []
    datos = dict(state.get("datos_lead") or {})
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()

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

    pending = _next_pending(datos)

    # ── Capturar un campo por turno ──────────────────────────────────────
    if pending == "nombre":
        alpha_words = [w for w in user_text.split() if w.replace(",", "").isalpha() and len(w) > 1]
        if alpha_words and len(user_text) > 3 and not user_text.strip().isdigit():
            datos["nombre"] = user_text.strip()
            pending = _next_pending(datos)

    elif pending == "numero_a_portar":
        numero = _extract_phone(user_text)
        if numero:
            datos["numero_a_portar"] = numero
            pending = _next_pending(datos)

    elif pending == "compania_donante":
        compania = _extract_company(user_text)
        if compania:
            datos["compania_donante"] = compania
            pending = _next_pending(datos)
        elif len(user_text.strip()) > 2 and not _extract_phone(user_text) and not user_text.strip().isdigit():
            datos["compania_donante"] = user_text.strip()
            pending = _next_pending(datos)

    # Capturar municipio si el cliente lo menciona (no bloqueante)
    if pending is None and not datos.get("municipio"):
        if len(user_text.strip()) > 2 and not user_text.strip().isdigit() and not _extract_phone(user_text):
            datos["municipio"] = user_text.strip()

    # ── KPI completo → resumen + escalar ─────────────────────────────────
    if pending is None:
        nombre = datos.get("nombre", "")

        resumen = (
            f"¡Listo, {nombre.split()[0] if nombre else ''}! 🙌 Ya tengo todo lo que necesito.\n\n"
            f"👤 Nombre: {datos.get('nombre')}\n"
            f"📱 Número a portar: {datos.get('numero_a_portar')}\n"
            f"📡 Compañía actual: {datos.get('compania_donante')}\n\n"
            "Te voy a conectar con un asesor de portabilidad que va a continuar el proceso "
            "contigo, incluyendo la generación de tu NIP.\n"
            "Solo tarda unos minutos y tu CHIP lo recoges gratis en el CAC.\n\n"
            "¿Tienes alguna duda antes de pasarte con él?\n\n"
            f"{_AVISO_PRIVACIDAD}"
        )
        return {
            "messages": [AIMessage(content=resumen)],
            "datos_lead": datos,
            "etapa": "escalado",
        }

    # ── Preguntar el siguiente campo ──────────────────────────────────────
    pregunta = _PREGUNTAS.get(pending, "")

    # Evitar repetir la misma pregunta dos veces seguidas
    recent_texts = [getattr(m, "content", "") for m in messages[-3:]]
    if pregunta and not any(pregunta[:30] in t for t in recent_texts):
        return {
            "messages": [AIMessage(content=pregunta)],
            "datos_lead": datos,
        }

    # Fallback con Claude si la respuesta no fue clara
    llm = get_llm()
    campo_desc = {
        "nombre": "nombre completo del cliente",
        "numero_a_portar": "número de teléfono de 10 dígitos que desea portar",
        "compania_donante": "compañía actual del cliente (Movistar, AT&T, Nextel, etc.)",
    }.get(pending or "", "información")

    system = render_prompt("cierre_fallback", campo_desc=campo_desc)
    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-4:]))
    return {"messages": split_msg(ai_msg.content), "datos_lead": datos}

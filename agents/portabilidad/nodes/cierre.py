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
from datetime import datetime

import pytz

from langchain_core.messages import AIMessage

from agents.portabilidad.state import PortabilidadState

_TZ = pytz.timezone("America/Monterrey")


def _mensaje_contacto_asesor() -> str:
    """Retorna el mensaje de contacto según hora y día en Monterrey.

    Domingo (cualquier hora)       → lunes a las 9:00 a.m.
    Sábado 14:00–23:59             → lunes a las 9:00 a.m.
    Sábado 00:01–08:59             → hoy sábado a las 9:00 a.m.
    Sábado 09:00–13:59             → conexión inmediata.
    Lun–Vie 21:00–23:59            → mañana a las 9:00 a.m.
    Lun–Vie 00:01–08:59            → hoy a las 9:00 a.m.
    Lun–Vie 09:00–20:59            → conexión inmediata.
    """
    ahora = datetime.now(tz=_TZ)
    hora = ahora.hour
    dia = ahora.weekday()  # 0=lun … 5=sab … 6=dom

    if dia == 6:  # domingo
        return (
            "Ya está todo listo. Los domingos nuestros asesores no realizan llamadas, "
            "por lo que mañana lunes a partir de las 9:00 a.m. un asesor de portabilidad "
            "te contactará para continuar el proceso, incluyendo la generación de tu NIP.\n"
            "Tu CHIP lo recoges gratis en el CAC más cercano."
        )
    if dia == 5:  # sábado
        if hora >= 14:
            return (
                "Ya está todo listo. La atención telefónica los sábados concluye a las 2:00 p.m., "
                "por lo que el próximo lunes a partir de las 9:00 a.m. un asesor de portabilidad "
                "te contactará para continuar el proceso, incluyendo la generación de tu NIP.\n"
                "Tu CHIP lo recoges gratis en el CAC más cercano."
            )
        if 0 < hora < 9:
            return (
                "Ya está todo listo. Nuestros asesores inician atención a las 9:00 a.m., "
                "por lo que hoy mismo a esa hora un asesor de portabilidad te contactará "
                "para continuar el proceso, incluyendo la generación de tu NIP.\n"
                "Tu CHIP lo recoges gratis en el CAC más cercano."
            )
        # sábado 09:00–13:59 → atención normal
        return (
            "Te voy a conectar con un asesor de portabilidad que va a continuar el proceso "
            "contigo, incluyendo la generación de tu NIP.\n"
            "Solo tarda unos minutos y tu CHIP lo recoges gratis en el CAC."
        )
    # lunes a viernes
    if hora >= 21:
        return (
            "Ya está todo listo. Como en este momento nuestros asesores ya concluyeron "
            "su horario de atención, mañana en horario hábil (9:00 a.m. – 9:00 p.m.) "
            "un asesor de portabilidad te contactará para continuar el proceso, "
            "incluyendo la generación de tu NIP.\n"
            "Tu CHIP lo recoges gratis en el CAC más cercano."
        )
    if 0 < hora < 9:
        return (
            "Ya está todo listo. Nuestros asesores inician atención a las 9:00 a.m., "
            "por lo que hoy mismo a esa hora un asesor de portabilidad te contactará "
            "para continuar el proceso, incluyendo la generación de tu NIP.\n"
            "Tu CHIP lo recoges gratis en el CAC más cercano."
        )
    return (
        "Te voy a conectar con un asesor de portabilidad que va a continuar el proceso "
        "contigo, incluyendo la generación de tu NIP.\n"
        "Solo tarda unos minutos y tu CHIP lo recoges gratis en el CAC."
    )

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
_LIBERADO_SI = ["sí", "si", "liberado", "desbloqueado", "sí está", "funciona", "acepta chip", "lo probé", "ya está"]
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

# Segunda pregunta si la primera no fue entendida — sin Claude para evitar re-presentar la oferta
_REPREGUNTAS = {
    "nombre": "Disculpa, ¿me confirmas tu nombre completo?",
    "numero_a_portar": "¿Me confirmas el número de 10 dígitos que quieres portar?",
    "compania_donante": "¿De qué compañía te cambias? (Movistar, AT&T, Nextel, Bait, etc.)",
}


def _extract_all_kpis(user_text: str, datos: dict) -> dict:
    """Extrae nombre, número y compañía del mismo mensaje.

    Permite capturar los 3 campos KPI aunque el cliente los dé en un solo turno
    (ej: "Rafael Canales 8112111092 Bait"). El orden de extracción importa:
    primero teléfono y compañía (para excluirlos del texto antes de extraer el nombre).
    """
    # 1. Teléfono — siempre intentar
    if not datos.get("numero_a_portar"):
        numero = _extract_phone(user_text)
        if numero:
            datos["numero_a_portar"] = numero

    # 2. Compañía — siempre intentar
    if not datos.get("compania_donante"):
        company = _extract_company(user_text)
        if company:
            datos["compania_donante"] = company

    # 3. Nombre — quitar dígitos y palabras clave de compañías, tomar lo alfabético restante
    if not datos.get("nombre"):
        company_keys = set(_COMPANIAS.keys())
        name_text = re.sub(r"\d+", " ", user_text)
        for key in company_keys:
            name_text = re.sub(rf"\b{re.escape(key)}\b", " ", name_text, flags=re.IGNORECASE)
        name_words = [
            w.strip(",.;:") for w in name_text.split()
            if w.strip(",.;:").replace("-", "").replace("'", "").isalpha()
            and len(w.strip(",.;:")) >= 3
        ]
        # Al menos 2 palabras de 3+ chars → nombre completo; o 1 si parece un solo nombre
        if len(name_words) >= 2 or (len(name_words) == 1 and len(name_words[0]) >= 4):
            datos["nombre"] = " ".join(name_words).strip()

    return datos


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

    # ── Extracción simultánea: teléfono, compañía y nombre del mismo mensaje ──
    datos = _extract_all_kpis(user_text, datos)

    pending = _next_pending(datos)

    # Capturar municipio si el cliente lo menciona espontáneamente (no bloqueante)
    if pending is None and not datos.get("municipio"):
        if len(user_text.strip()) > 2 and not user_text.strip().isdigit() and not _extract_phone(user_text):
            datos["municipio"] = user_text.strip()

    # ── KPI completo → resumen + escalar ─────────────────────────────────
    if pending is None:
        nombre = datos.get("nombre", "")

        nombre_corto = nombre.split()[0] if nombre else ""
        resumen = (
            f"¡Listo, {nombre_corto}! 🙌 Ya tengo todo lo que necesito.\n\n"
            f"👤 Nombre: {datos.get('nombre')}\n"
            f"📱 Número a portar: {datos.get('numero_a_portar')}\n"
            f"📡 Compañía actual: {datos.get('compania_donante')}\n\n"
            f"{_mensaje_contacto_asesor()}\n\n"
            "¿Tienes alguna duda antes de pasarte con él?\n\n"
            f"{_AVISO_PRIVACIDAD}"
        )
        return {
            "messages": [AIMessage(content=resumen)],
            "datos_lead": datos,
            "etapa": "escalado",
        }

    # ── Preguntar el siguiente campo ──────────────────────────────────────
    # Nunca usar Claude aquí — con el contexto de oferta re-presenta los beneficios.
    pregunta = _PREGUNTAS.get(pending, "")
    reciente_ai = [getattr(m, "content", "") for m in messages if hasattr(m, "type") and m.type == "ai"]
    ya_preguntada = pregunta and any(pregunta[:30] in t for t in reciente_ai[-2:])

    return {
        "messages": [AIMessage(content=_REPREGUNTAS[pending] if ya_preguntada else pregunta)],
        "datos_lead": datos,
    }

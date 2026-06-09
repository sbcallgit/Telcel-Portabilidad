"""Nodo de escalamiento: handoff a asesor humano vía Bitrix24 Open Lines."""

import logging

from langchain_core.messages import AIMessage

from agents.portabilidad.state import PortabilidadState
from config.settings import settings

logger = logging.getLogger(__name__)


def _build_context(state: PortabilidadState) -> dict:
    datos = state.get("datos_lead") or {}
    return {
        "nombre": datos.get("nombre", ""),
        "numero_a_portar": datos.get("numero_a_portar", ""),
        "compania_donante": datos.get("compania_donante", ""),
        "municipio": datos.get("municipio", ""),
        "promo_elegida": state.get("promo_elegida", ""),
        "temperatura": state.get("temperatura", ""),
        "motivo_escalacion": state.get("motivo_escalacion", ""),
        "customer_phone": state.get("customer_phone", ""),
        "lada": state.get("lada", ""),
        "ciudad": state.get("ciudad", ""),
    }


async def _try_bitrix(context: dict, phone: str) -> str:
    """Crea/actualiza lead en Bitrix24 y devuelve el lead_id. Silencia errores si no configurado."""
    if not settings.bitrix_webhook_url:
        logger.info("bitrix_skipped_not_configured")
        return ""
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        result = await bx.crear_deal(
            telefono=phone,
            datos={
                "NAME": context.get("nombre", ""),
                "COMMENTS": (
                    f"Promo: {context.get('promo_elegida', '')}\n"
                    f"Número a portar: {context.get('numero_a_portar', '')}\n"
                    f"Compañía donante: {context.get('compania_donante', '')}\n"
                    f"Municipio: {context.get('municipio', '')}\n"
                    f"Temperatura: {context.get('temperatura', '')}"
                ),
            },
        )
        return str(result.get("result", ""))
    except Exception as exc:
        logger.error("bitrix_error", extra={"error": str(exc)})
        return ""


def _build_handoff_message(context: dict, motivo: str) -> str:
    """Protocolo de 4 pasos (spec sec. 10.2): explica, confirma datos, tiempo, pregunta."""
    nombre = context.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    if motivo == "caso_sensible":
        return (
            "Lamentamos mucho lo que estás pasando. "
            "Te conecto con un asesor que puede orientarte con más calma. "
            "Gracias por tu paciencia."
        )

    if motivo == "solicitud_directa":
        return (
            "Claro, ahora mismo te conecto con un asesor. "
            "En unos minutos te contacta para ayudarte. "
            "¿Hay algo más que quieras que le comunique?"
        )

    if motivo == "max_objeciones_alcanzado":
        return (
            "Entiendo perfectamente. Te dejo aquí mi contacto por si más adelante "
            "quieres aprovechar la promo. ¡Que tengas excelente día! 🌟"
        )

    # Handoff normal post-cierre (spec sec. 10.2 — 4 pasos)
    nombre_line = f"Ya tengo tu información registrada, {nombre_corto}." if nombre_corto else "Ya tengo tu información registrada."
    return (
        f"¡Perfecto! 🙌 {nombre_line}\n"
        "Te voy a pasar con un asesor de portabilidad que va a generar tu NIP "
        "y coordinar la entrega de tu CHIP en el CAC más cercano.\n"
        "Te contacta en los próximos minutos.\n"
        "¿Alguna duda antes de pasarte con él?"
    )


async def escalate_node(state: PortabilidadState) -> dict:
    # Evitar doble escalamiento — limpiar flag y dejar que _fin_node maneje el resto
    if state.get("etapa") == "fin":
        return {"escalate_to_human": False}

    context = _build_context(state)
    phone = state.get("customer_phone") or ""
    motivo = state.get("motivo_escalacion") or "cierre"

    # Integrar con Bitrix (fallos son silenciosos para no bloquear al cliente)
    deal_id = await _try_bitrix(context, phone)

    handoff_msg = _build_handoff_message(context, motivo)

    logger.info(
        "escalation_done",
        extra={
            "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            "motivo": motivo,
            "deal_id": deal_id,
        },
    )

    return {
        "messages": [AIMessage(content=handoff_msg)],
        "bitrix_lead_id": deal_id,
        "bitrix_etapa": "listo_para_portabilidad",
        "etapa": "fin",
        "escalate_to_human": False,
    }

"""Grafo LangGraph del agente de portabilidad Telcel Región 4."""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agents.callbacks import TokenUsageCallback
from agents.llm import get_llm
from agents.portabilidad.context import (
    ASL_CATALOG,
    AMAZON_PRIME_BY_PACKAGE,
    CHANNEL_RULES,
    CLARO_DRIVE_MUSICA,
    FORMAT_RULES,
    HARD_RULES,
    ID_DOCS_INFO,
    PORTABILITY_SCHEDULE,
)
from agents.portabilidad.nodes.cierre import cierre_node
from agents.portabilidad.nodes.escalate import escalate_node
from agents.portabilidad.nodes.objeciones import objeciones_node
from agents.portabilidad.nodes.oferta import oferta_node
from agents.portabilidad.nodes.sondeo import sondeo_node
from agents.portabilidad.nodes.validacion import validacion_node
from agents.portabilidad.state import PortabilidadState
from agents.portabilidad.utils import split_msg

logger = logging.getLogger(__name__)

# Grafo compilado — se inicializa en setup_graph() desde el lifespan de FastAPI.
# Hasta que se llame, cae en fallback MemorySaver para pruebas/seed.
_agent_graph = None


_FIN_ESCALATION = [
    "asesor", "humano", "persona real", "agente", "supervisor", "hablar con alguien",
    "quiero hablar", "conéctame", "conectame", "quiero que me llamen",
]
_FIN_SEGUIMIENTO = [
    "más adelante", "mas adelante", "en otro momento", "luego te confirmo",
    "mañana te digo", "ahorita no puedo", "ahorita no", "llámame después",
    "llamame despues", "cuando pueda", "después me comunico", "me comunico después",
]
_FIN_PROSPECTO = [
    "ya decidí", "ya decidi", "quiero portarme", "listo para portarme",
    "ya me decidí", "ya me decidi", "sí quiero", "si quiero", "vamos", "adelante",
]


_ESCALAMIENTO_DURO = {
    "solicitud_directa",
    "caso_sensible",
    "solicitud_arco",
    "telcel_a_telcel",
    "cambio_titularidad",
    "lada_no_identificada",
}


async def _fin_node(state: PortabilidadState) -> dict:
    """Post-escalamiento: re-detecta intents clave y actualiza Bitrix en consecuencia.

    Escalamiento duro (asesor tomó control): bot silenciado; solo reactiva si el
    cliente decide avanzar explícitamente (_FIN_PROSPECTO).
    Seguimiento suave: bot sigue activo para confirmar o responder preguntas.
    """
    from agents.portabilidad.nodes.escalate import _build_context, _try_bitrix

    messages = state.get("messages") or []
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()
    phone = state.get("customer_phone", "")
    datos = state.get("datos_lead") or {}
    promo = state.get("promo_elegida", "")
    motivo = state.get("motivo_escalacion", "")

    # ── Escalamiento duro: asesor humano tiene el control ─────────────────────
    if motivo in _ESCALAMIENTO_DURO:
        # Verificar si el deal fue marcado como Caído → reactivar conversación
        deal_id = state.get("bitrix_lead_id") or ""
        if deal_id:
            try:
                from integrations.bitrix.client import BitrixClient
                deal_data = await BitrixClient().get_deal(deal_id)
                if deal_data.get("STAGE_ID") == "C90:LOSE":
                    await BitrixClient().mover_etapa(deal_id, "C90:PREPAYMENT_INVOIC")
                    logger.info("fin_node_reactivado_desde_caido", extra={
                        "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
                        "deal_id": deal_id,
                    })
                    return {
                        "etapa": "validacion",
                        "motivo_escalacion": "",
                        "escalate_to_human": False,
                        "messages": [AIMessage(content=(
                            "¡Hola de nuevo! 👋 Puedo ayudarte con tu portabilidad a Telcel. "
                            "¿Me compartes tu número de 10 dígitos para ver la promo que aplica?"
                        ))],
                    }
            except Exception as exc:
                logger.warning("fin_node_reactivacion_error", extra={
                    "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
                    "error": str(exc),
                })

        # Única excepción: cliente se decide a portarse → reactivar a Prospecto
        if any(w in lower for w in _FIN_PROSPECTO):
            context = _build_context(state)
            deal_id = await _try_bitrix(
                context, phone, motivo="cierre",
                existing_deal_id=state.get("bitrix_lead_id") or "",
            )
            logger.info("fin_node_reactivado", extra={
                "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            })
            return {
                "messages": [AIMessage(content=(
                    "¡Perfecto! Te paso con un asesor para coordinar tu portabilidad. "
                    "Te contacta en los próximos minutos."
                ))],
                "bitrix_lead_id": deal_id,
            }
        # Silencio total — el asesor humano gestiona la conversación desde Bitrix
        logger.info("fin_node_silenciado", extra={
            "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            "motivo": motivo,
        })
        return {}

    # ── Seguimiento suave: bot sigue activo ───────────────────────────────────

    # Cliente quiere asesor humano ahora → mover deal a Escalamiento
    if any(w in lower for w in _FIN_ESCALATION):
        context = _build_context(state)
        deal_id = await _try_bitrix(
            context, phone, motivo="solicitud_directa",
            existing_deal_id=state.get("bitrix_lead_id") or "",
        )
        logger.info("fin_node_reescalado", extra={
            "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            "nuevo_motivo": "solicitud_directa",
        })
        return {
            "messages": [AIMessage(content="Claro, te conecto ahora mismo con un asesor. En unos minutos te contacta.")],
            "bitrix_lead_id": deal_id,
            "motivo_escalacion": "solicitud_directa",
        }

    # Cliente confirma seguimiento → deal ya está en Seguimiento, solo confirmar
    if any(w in lower for w in _FIN_SEGUIMIENTO):
        return {
            "messages": [AIMessage(content=(
                "Perfecto, ya tienes un asesor asignado que te contactará cuando estés listo. "
                "¡Que tengas excelente día!"
            ))],
        }

    # Cliente se decide y quiere avanzar → mover deal a Prospecto
    if any(w in lower for w in _FIN_PROSPECTO):
        context = _build_context(state)
        deal_id = await _try_bitrix(
            context, phone, motivo="cierre",
            existing_deal_id=state.get("bitrix_lead_id") or "",
        )
        logger.info("fin_node_reescalado", extra={
            "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            "nuevo_motivo": "cierre",
        })
        return {
            "messages": [AIMessage(content=(
                "¡Perfecto! Te paso con un asesor para coordinar tu portabilidad. "
                "Te contacta en los próximos minutos."
            ))],
            "bitrix_lead_id": deal_id,
        }

    # Default seguimiento: Claude responde preguntas mientras el cliente espera
    llm = get_llm()
    system = (
        "Eres Vera, asistente de Telcel para portabilidad. "
        "Este cliente quedó en seguimiento: un asesor lo contactará más adelante.\n\n"
        "Datos registrados:\n"
        f"- Nombre: {datos.get('nombre') or 'no capturado'}\n"
        f"- Número a portar: {datos.get('numero_a_portar') or 'no capturado'}\n"
        f"- Promo elegida: {promo or 'no definida'}\n\n"
        f"{ASL_CATALOG}\n"
        f"{AMAZON_PRIME_BY_PACKAGE}\n"
        f"{PORTABILITY_SCHEDULE}\n"
        f"{CLARO_DRIVE_MUSICA}\n"
        f"{CHANNEL_RULES}\n"
        f"{ID_DOCS_INFO}\n"
        f"{HARD_RULES}\n"
        f"{FORMAT_RULES}\n"
        "TAREA: Responde preguntas del catálogo con naturalidad. "
        "Si el cliente decide portarse, dile que ya quedó registrado y un asesor lo contactará."
    )

    ai_msg = await llm.ainvoke(
        [SystemMessage(content=system)] + list(messages[-6:]),
        config={"callbacks": [TokenUsageCallback(phone, "fin")]},
    )
    return {"messages": split_msg(ai_msg.content)}


def _route(state: PortabilidadState) -> str:
    """Decide qué nodo ejecutar según el estado actual de la conversación."""
    if state.get("escalate_to_human"):
        return "escalate"

    etapa = state.get("etapa") or "validacion"

    mapping: dict[str, str] = {
        "validacion": "validacion",
        "sondeo": "sondeo",
        "oferta": "oferta",
        "objecion": "objeciones",
        "cierre": "cierre",
        "escalado": "escalate",
        "fin": "fin",
    }
    return mapping.get(etapa, "validacion")


def _build() -> StateGraph:
    graph = StateGraph(PortabilidadState)

    graph.add_node("validacion", validacion_node)
    graph.add_node("sondeo", sondeo_node)
    graph.add_node("oferta", oferta_node)
    graph.add_node("objeciones", objeciones_node)
    graph.add_node("cierre", cierre_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("fin", _fin_node)

    graph.add_conditional_edges(
        START,
        _route,
        {
            "validacion": "validacion",
            "sondeo": "sondeo",
            "oferta": "oferta",
            "objeciones": "objeciones",
            "cierre": "cierre",
            "escalate": "escalate",
            "fin": "fin",
        },
    )

    def _to_escalate_or_end(s: PortabilidadState) -> str:
        return "escalate" if s.get("escalate_to_human") else END

    for node_name in ["escalate", "fin"]:
        graph.add_edge(node_name, END)

    # cierre → escalate cuando los KPIs están completos (mismo turno)
    graph.add_conditional_edges(
        "cierre",
        lambda s: "escalate" if s.get("etapa") == "escalado" else END,
        {"escalate": "escalate", END: END},
    )

    # validacion / sondeo / oferta / objeciones → escalate en el mismo turno si detectan escalación
    for node_name in ["validacion", "sondeo", "oferta", "objeciones"]:
        graph.add_conditional_edges(
            node_name,
            _to_escalate_or_end,
            {"escalate": "escalate", END: END},
        )

    return graph


async def setup_graph(checkpointer=None) -> None:
    """Inicializa el grafo con el checkpointer indicado.

    Llamar desde el lifespan de FastAPI con AsyncPostgresSaver.
    Si no se proporciona checkpointer usa MemorySaver (dev/tests).
    """
    global _agent_graph
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        logger.warning("graph_using_memory_checkpointer")
    _agent_graph = _build().compile(checkpointer=checkpointer)
    logger.info("graph_initialized", extra={"checkpointer": type(checkpointer).__name__})


def get_agent_graph():
    """Retorna el grafo compilado. Inicializa con MemorySaver si aún no se configuró."""
    global _agent_graph
    if _agent_graph is None:
        import asyncio
        asyncio.get_event_loop().run_until_complete(setup_graph())
    return _agent_graph

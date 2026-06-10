"""Grafo LangGraph del agente de portabilidad Telcel Región 4."""

import logging

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

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


async def _fin_node(state: PortabilidadState) -> dict:
    """Post-escalamiento: Vera sigue respondiendo preguntas del cliente con Claude."""
    messages = state.get("messages") or []
    datos = state.get("datos_lead") or {}
    promo = state.get("promo_elegida", "")

    llm = get_llm()
    system = (
        "Eres Vera, asistente de Telcel para portabilidad. "
        "Ya conectaste a este cliente con un asesor humano que lo contactará en breve.\n\n"
        "Datos del cliente registrados:\n"
        f"- Nombre: {datos.get('nombre') or 'no capturado'}\n"
        f"- Número a portar: {datos.get('numero_a_portar') or 'no capturado'}\n"
        f"- Compañía donante: {datos.get('compania_donante') or 'no capturada'}\n"
        f"- Promo elegida: {promo or 'no definida'}\n\n"
        f"{ASL_CATALOG}\n"
        f"{AMAZON_PRIME_BY_PACKAGE}\n"
        f"{PORTABILITY_SCHEDULE}\n"
        f"{CLARO_DRIVE_MUSICA}\n"
        f"{CHANNEL_RULES}\n"
        f"{ID_DOCS_INFO}\n"
        f"{HARD_RULES}\n"
        f"{FORMAT_RULES}\n"
        "TAREA: Responde cualquier pregunta que el cliente tenga de forma natural y completa. "
        "No repitas que ya lo conectaste con el asesor a menos que sea directamente relevante. "
        "Si pregunta algo fuera del tema de portabilidad/Telcel, redirige brevemente."
    )

    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-6:]))
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

    for node_name in ["validacion", "sondeo", "oferta", "objeciones", "escalate", "fin"]:
        graph.add_edge(node_name, END)

    # cierre → escalate cuando los KPIs están completos (mismo turno)
    graph.add_conditional_edges(
        "cierre",
        lambda s: "escalate" if s.get("etapa") == "escalado" else END,
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

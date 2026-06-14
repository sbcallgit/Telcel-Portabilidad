"""Helpers de conversación para la suite QA del agente (importables por los tests)."""

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage


@dataclass
class Turno:
    etapa: str
    bot_text: str
    escalate: bool
    motivo: str
    datos: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


async def turno(agente, thread_id: str, texto: str, estado_extra: dict | None = None) -> Turno:
    """Envía un mensaje al agente y devuelve un resumen del resultado.

    estado_extra permite arrancar la conversación en una etapa concreta
    (ej. {"etapa": "objecion"}) para probar un nodo puntual.
    """
    state = {
        "messages": [HumanMessage(content=texto)],
        "session_id": thread_id,
        "customer_phone": f"tg_{thread_id}",
    }
    if estado_extra:
        state.update(estado_extra)

    result = await agente.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    ai = [
        str(m.content) for m in result.get("messages", [])
        if isinstance(m, AIMessage) and m.content and m.content != "(procesando objeción)"
    ]
    return Turno(
        etapa=result.get("etapa", ""),
        bot_text=ai[-1] if ai else "",
        escalate=bool(result.get("escalate_to_human", False)),
        motivo=result.get("motivo_escalacion", ""),
        datos=result.get("datos_lead") or {},
        raw=result,
    )

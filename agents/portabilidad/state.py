from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class PortabilidadState(TypedDict, total=False):
    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    customer_phone: str
    etapa: str  # validacion | sondeo | oferta | objecion | cierre | escalado | fin
    lada: str
    ciudad: str
    region_habilitada: bool
    datos_lead: dict  # nombre, numero_a_portar, compania_donante, municipio, recarga_habitual, uso_predominante
    temperatura: str  # caliente | tibio | frio
    promo_elegida: str
    objeciones_rebatidas: int
    intentos_sin_avance: int
    escalate_to_human: bool
    motivo_escalacion: str
    bitrix_lead_id: str
    bitrix_etapa: str
    referral: dict  # datos de atribución Click-to-WhatsApp (source_id, ctwa_clid, source_url, etc.)

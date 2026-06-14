"""Harness offline para probar el agente Vera por invocación directa del grafo.

Aísla el agente de todo IO externo:
  - LLM (OpenRouter): stub determinista — no llama a la red ni cuesta tokens.
  - PostgreSQL: stub en memoria con LADAs/promos/objeciones canónicas.
  - Bitrix/CRM/Open Lines: deshabilitado (bitrix_webhook_url / client_id vacíos).
  - Qdrant: _find_objection stubbeado.

Así se ejercitan los flujos y guardrails SIN tocar producción ni servicios reales.
Los tests que requieren el LLM real (refutación de prompt injection) viven en
test_qa_llm_required.py y están skippeados salvo RUN_LLM_TESTS=1.

NOTA: requiere las deps del proyecto instaladas (langgraph, langchain-core…),
por lo que corre dentro del contenedor / CI, no en un entorno pelón.
"""

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage

# ─── Stub del LLM ────────────────────────────────────────────────────────────

class _FakeLLM:
    async def ainvoke(self, _input):
        return AIMessage(content="Respuesta simulada de Vera (LLM stub).")


def _fake_get_llm(temperature: float = 0.3):
    return _FakeLLM()


# ─── Stub de PostgreSQL ──────────────────────────────────────────────────────

_LADAS = {
    "811": {"lada": "811", "ciudad": "Monterrey", "estado": "Nuevo León", "habilitada": True},
    "844": {"lada": "844", "ciudad": "Saltillo", "estado": "Coahuila", "habilitada": True},
    "871": {"lada": "871", "ciudad": "Torreón", "estado": "Coahuila", "habilitada": False},
}

_PROMOS = [
    {
        "nombre": "Amigo Sin Límite $100",
        "recarga": 100,
        "beneficios": "1.5 GB de datos|6 redes ilimitadas|Claro Drive 20 GB",
        "vigencia": "2026-12-31",
        "condicion": "Recarga $100",
    },
    {
        "nombre": "Amigo Sin Límite $50",
        "recarga": 50,
        "beneficios": "500 MB de datos|bolsa de redes 1.5 GB|Claro Drive 20 GB",
        "vigencia": "2026-12-31",
        "condicion": "Recarga $50",
    },
]


async def _fake_fetchrow(query: str, *args):
    q = " ".join(query.split())
    if "FROM ladas" in q and args:
        return _LADAS.get(str(args[0]))
    if "FROM objeciones" in q:
        return {"texto": "está caro", "categoria": "precio", "respuesta": "Te entiendo. Con tu misma recarga obtienes el triple de beneficios."}
    return None


async def _fake_fetch(query: str, *args):
    q = " ".join(query.split())
    if "FROM promos" in q:
        return list(_PROMOS)
    if "FROM cacs" in q:
        return []
    return []


async def _fake_fetchval(query: str, *args):
    return None


async def _fake_execute(query: str, *args):
    return ""


async def _fake_find_objection(text: str):
    return {"texto": "está caro", "categoria": "precio", "respuesta": "Te entiendo, con la misma recarga tendrías mucho más."}


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    """Aísla el agente de LLM, DB, Bitrix y Qdrant. Autouse en este paquete."""
    from config.settings import settings as s
    monkeypatch.setattr(s, "bitrix_webhook_url", "", raising=False)
    monkeypatch.setattr(s, "bitrix_client_id", "", raising=False)
    monkeypatch.setattr(s, "bitrix_connector_line_id", "", raising=False)
    monkeypatch.setattr(s, "environment", "development", raising=False)

    import integrations.postgres.client as dbmod
    monkeypatch.setattr(dbmod, "fetchrow", _fake_fetchrow)
    monkeypatch.setattr(dbmod, "fetch", _fake_fetch)
    monkeypatch.setattr(dbmod, "fetchval", _fake_fetchval)
    monkeypatch.setattr(dbmod, "execute", _fake_execute)

    import agents.portabilidad.graph as g
    import agents.portabilidad.nodes.objeciones as ob
    import agents.portabilidad.nodes.oferta as of
    import agents.portabilidad.nodes.sondeo as so
    import agents.portabilidad.nodes.validacion as v
    for mod in (v, so, of, ob, g):
        monkeypatch.setattr(mod, "get_llm", _fake_get_llm, raising=False)
    monkeypatch.setattr(ob, "_find_objection", _fake_find_objection, raising=False)


@pytest_asyncio.fixture
async def agente():
    """Grafo compilado con checkpointer en memoria (estado por thread_id)."""
    from langgraph.checkpoint.memory import MemorySaver

    from agents.portabilidad.graph import _build
    return _build().compile(checkpointer=MemorySaver())

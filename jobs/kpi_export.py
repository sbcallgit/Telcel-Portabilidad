"""Job nocturno de extracción de KPIs de conversaciones para exportación a BI.

Corre a las 3:00 AM America/Monterrey — fuera del horario de portabilidad.
Fuentes: checkpoints (PG) + Bitrix crm.deal.get + Open Lines.
Destino: tabla kpi_conversaciones (aislada del agente).
"""

import asyncio
import csv
import logging
from datetime import datetime, timezone

import pytz

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Monterrey")
_BATCH_SIZE = 50
_BATCH_SLEEP = 0.3  # cede el event loop entre lotes


async def _ensure_graph_initialized() -> None:
    """Inicializa el grafo con checkpointer PostgreSQL si aún no está listo.

    Dentro del proceso FastAPI ya está inicializado vía lifespan.
    En standalone (test manual, make export_kpi) lo inicializa aquí con timeout.
    """
    import agents.portabilidad.graph as graph_module
    if graph_module._agent_graph is not None:
        return
    try:
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from config.settings import settings

        pool = AsyncConnectionPool(
            conninfo=settings.database_dsn,
            min_size=1,
            max_size=3,
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False,
        )
        await asyncio.wait_for(pool.open(), timeout=8.0)
        checkpointer = AsyncPostgresSaver(pool)
        await graph_module.setup_graph(checkpointer)
        logger.info("kpi_graph_initialized_standalone")
    except Exception as exc:
        logger.warning("kpi_graph_init_failed_fallback", extra={"error": str(exc)})
        await graph_module.setup_graph()  # MemorySaver — sin historial en standalone


async def _list_threads() -> list[dict]:
    """Retorna thread_id, creado_el y campos de estado del último checkpoint."""
    rows = await db.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (thread_id)
                thread_id,
                checkpoint->'channel_values'->>'etapa'          AS etapa,
                checkpoint->'channel_values'->>'bitrix_lead_id' AS bitrix_lead_id,
                checkpoint->'channel_values'->>'customer_phone' AS customer_phone
            FROM checkpoints
            WHERE checkpoint_ns = ''
            ORDER BY thread_id, checkpoint_id DESC
        ),
        earliest AS (
            SELECT DISTINCT ON (thread_id)
                thread_id,
                (checkpoint->>'ts')::timestamptz AS creado_el
            FROM checkpoints
            WHERE checkpoint_ns = ''
            ORDER BY thread_id, checkpoint_id ASC
        )
        SELECT l.thread_id, l.etapa, l.bitrix_lead_id, l.customer_phone, e.creado_el
        FROM latest l
        JOIN earliest e ON l.thread_id = e.thread_id
        WHERE e.creado_el > NOW() - INTERVAL '30 days'
        ORDER BY e.creado_el DESC
        LIMIT 500
        """,
    )
    return [dict(r) for r in rows]


async def _get_message_counts(phone: str) -> dict:
    """Cuenta mensajes por actor (cliente/bot) usando graph.aget_state()."""
    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from agents.portabilidad.graph import get_agent_graph

        snapshot = await get_agent_graph().aget_state(
            {"configurable": {"thread_id": phone}}
        )
        if not snapshot or not snapshot.values:
            return {}

        messages = snapshot.values.get("messages") or []
        primer_msg = next((m.content for m in messages if isinstance(m, HumanMessage)), "")
        return {
            "mensajes_cliente": sum(1 for m in messages if isinstance(m, HumanMessage)),
            "mensajes_bot": sum(1 for m in messages if isinstance(m, AIMessage)),
            "primer_mensaje": primer_msg[:500],
        }
    except Exception as exc:
        logger.warning("kpi_msg_count_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return {}


async def _get_deal_data(deal_id: str) -> dict:
    """Consulta crm.deal.get para metadatos del deal en Bitrix."""
    if not deal_id:
        return {}
    try:
        from integrations.bitrix.client import BitrixClient
        deal = await BitrixClient().get_deal(deal_id)
        if not deal:
            return {}

        cerrado_el = None
        close_str = deal.get("CLOSEDATE", "")
        if close_str:
            try:
                cerrado_el = datetime.fromisoformat(
                    close_str.replace("T", " ").split("+")[0]
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        return {
            "id_contacto": str(deal.get("CONTACT_ID") or ""),
            "pipeline": str(deal.get("CATEGORY_ID") or ""),
            "origen": str(deal.get("SOURCE_ID") or ""),
            "estado_actual": str(deal.get("STAGE_ID") or ""),
            "empleado": str(deal.get("ASSIGNED_BY_ID") or ""),
            "cerrado_el": cerrado_el,
        }
    except Exception as exc:
        logger.warning("kpi_deal_error", extra={"deal_id": deal_id, "error": str(exc)})
        return {}


async def _get_chat_data(phone: str) -> dict:
    """Lee mensajes de Open Lines para KPIs de tiempo y conteo humano."""
    try:
        from integrations.redis_client import get_redis
        from integrations.bitrix.connector import _call_poll

        redis = await get_redis()
        chat_id = await redis.get(f"connector_chat:{phone}")
        if not chat_id:
            return {}

        result = await _call_poll("im.dialog.messages.get", {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": 50,
        })
        messages = sorted(
            result.get("result", {}).get("messages", []),
            key=lambda m: int(m.get("id", 0)),
        )
        if not messages:
            return {}

        primera_respuesta = None
        el_bot_respondio_el = None
        el_agente_respondio_el = None
        mensajes_humano = 0
        timestamps: list[datetime] = []

        for msg in messages:
            ts_raw = msg.get("date")
            if not ts_raw:
                continue
            dt = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
            timestamps.append(dt)

            params = msg.get("params") or {}
            text = (msg.get("text") or "").strip()
            author_id = msg.get("author_id", 0)
            is_client = bool(isinstance(params, dict) and params.get("CONNECTOR_MID"))
            is_bot = text.startswith("🤖 Vera |")

            if not is_client:
                if primera_respuesta is None:
                    primera_respuesta = dt
                if is_bot and el_bot_respondio_el is None:
                    el_bot_respondio_el = dt
                if not is_bot and author_id:
                    mensajes_humano += 1
                    if el_agente_respondio_el is None:
                        el_agente_respondio_el = dt

        gaps = [
            (timestamps[i] - timestamps[i - 1]).total_seconds()
            for i in range(1, len(timestamps))
            if 0 < (timestamps[i] - timestamps[i - 1]).total_seconds() < 3600
        ]

        return {
            "primera_respuesta": primera_respuesta,
            "el_bot_respondio_el": el_bot_respondio_el,
            "el_agente_respondio_el": el_agente_respondio_el,
            "mensajes_humano": mensajes_humano,
            "tiempo_promedio_respuestas_segs": round(sum(gaps) / len(gaps), 1) if gaps else None,
            "tiempo_maximo_respuesta_segs": round(max(gaps), 1) if gaps else None,
        }
    except Exception as exc:
        logger.warning("kpi_chat_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return {}


async def _upsert(thread: dict) -> None:
    phone = thread["thread_id"]
    creado_el = thread.get("creado_el")
    deal_id = thread.get("bitrix_lead_id") or ""
    etapa = thread.get("etapa") or ""

    msg_data, deal, chat = await asyncio.gather(
        _get_message_counts(phone),
        _get_deal_data(deal_id),
        _get_chat_data(phone),
        return_exceptions=True,
    )
    if isinstance(msg_data, Exception):
        msg_data = {}
    if isinstance(deal, Exception):
        deal = {}
    if isinstance(chat, Exception):
        chat = {}

    primera_respuesta = chat.get("primera_respuesta")
    cerrado_el = deal.get("cerrado_el")

    tiempo_primera = (
        round((primera_respuesta - creado_el).total_seconds(), 1)
        if creado_el and primera_respuesta else None
    )
    tiempo_cierre = (
        round((cerrado_el - creado_el).total_seconds(), 1)
        if creado_el and cerrado_el else None
    )

    msgs_cliente = msg_data.get("mensajes_cliente", 0)
    msgs_bot = msg_data.get("mensajes_bot", 0)
    msgs_humano = chat.get("mensajes_humano", 0)

    await db.execute(
        """
        INSERT INTO kpi_conversaciones (
            id_conversacion, id_contacto, id_negociacion, telefono,
            pipeline, origen, primer_mensaje, tipo_mensaje,
            estado_actual, etapa, empleado,
            mensajes_totales, mensajes_cliente, mensajes_bot, mensajes_humano,
            creado_el, primera_respuesta, el_bot_respondio_el,
            solicitud_enviada_al_agente_el, el_agente_respondio_el, cerrado_el,
            tiempo_primera_respuesta_segs, tiempo_promedio_respuestas_segs,
            tiempo_maximo_respuesta_segs, tiempo_cierre_segs,
            fecha_extraccion
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8,
            $9, $10, $11,
            $12, $13, $14, $15,
            $16, $17, $18,
            $19, $20, $21,
            $22, $23, $24, $25,
            NOW()
        )
        ON CONFLICT (id_conversacion) DO UPDATE SET
            id_contacto                    = EXCLUDED.id_contacto,
            id_negociacion                 = EXCLUDED.id_negociacion,
            pipeline                       = EXCLUDED.pipeline,
            origen                         = EXCLUDED.origen,
            primer_mensaje                 = EXCLUDED.primer_mensaje,
            estado_actual                  = EXCLUDED.estado_actual,
            etapa                          = EXCLUDED.etapa,
            empleado                       = EXCLUDED.empleado,
            mensajes_totales               = EXCLUDED.mensajes_totales,
            mensajes_cliente               = EXCLUDED.mensajes_cliente,
            mensajes_bot                   = EXCLUDED.mensajes_bot,
            mensajes_humano                = EXCLUDED.mensajes_humano,
            primera_respuesta              = EXCLUDED.primera_respuesta,
            el_bot_respondio_el            = EXCLUDED.el_bot_respondio_el,
            solicitud_enviada_al_agente_el = EXCLUDED.solicitud_enviada_al_agente_el,
            el_agente_respondio_el         = EXCLUDED.el_agente_respondio_el,
            cerrado_el                     = EXCLUDED.cerrado_el,
            tiempo_primera_respuesta_segs  = EXCLUDED.tiempo_primera_respuesta_segs,
            tiempo_promedio_respuestas_segs = EXCLUDED.tiempo_promedio_respuestas_segs,
            tiempo_maximo_respuesta_segs   = EXCLUDED.tiempo_maximo_respuesta_segs,
            tiempo_cierre_segs             = EXCLUDED.tiempo_cierre_segs,
            fecha_extraccion               = NOW()
        """,
        phone, deal.get("id_contacto", ""), deal_id, phone,
        deal.get("pipeline", ""), deal.get("origen", ""),
        msg_data.get("primer_mensaje", ""), "Entrante",
        deal.get("estado_actual", etapa),
        etapa,
        deal.get("empleado", ""),
        msgs_cliente + msgs_bot + msgs_humano,
        msgs_cliente, msgs_bot, msgs_humano,
        creado_el, primera_respuesta, chat.get("el_bot_respondio_el"),
        None,  # solicitud_enviada_al_agente_el — pendiente v2
        chat.get("el_agente_respondio_el"), cerrado_el,
        tiempo_primera,
        chat.get("tiempo_promedio_respuestas_segs"),
        chat.get("tiempo_maximo_respuesta_segs"),
        tiempo_cierre,
    )


async def job_kpi_export() -> None:
    """Extrae KPIs de todas las conversaciones de los últimos 30 días y hace upsert."""
    await _ensure_graph_initialized()

    inicio = datetime.now(tz=TZ)
    logger.info("job_kpi_export_start", extra={"hora": inicio.isoformat()})

    try:
        threads = await _list_threads()
    except Exception as exc:
        logger.error("job_kpi_export_db_error", extra={"error": str(exc)})
        return

    procesados = 0
    errores = 0

    for i in range(0, len(threads), _BATCH_SIZE):
        batch = threads[i : i + _BATCH_SIZE]
        for thread in batch:
            try:
                await _upsert(thread)
                procesados += 1
            except Exception as exc:
                errores += 1
                logger.error("kpi_upsert_error", extra={"thread_id": thread["thread_id"], "error": str(exc)})
        await asyncio.sleep(_BATCH_SLEEP)

    duracion = round((datetime.now(tz=TZ) - inicio).total_seconds(), 1)
    logger.info(
        "job_kpi_export_done",
        extra={"total": len(threads), "procesados": procesados, "errores": errores, "duracion_s": duracion},
    )


async def export_to_csv(filepath: str | None = None) -> str:
    """Vuelca kpi_conversaciones a CSV. Retorna la ruta del archivo generado."""
    if not filepath:
        ts = datetime.now(tz=TZ).strftime("%Y%m%d_%H%M")
        filepath = f"/app/exports/kpi_conversaciones_{ts}.csv"

    rows = await db.fetch("SELECT * FROM kpi_conversaciones ORDER BY creado_el DESC NULLS LAST")
    if not rows:
        logger.warning("kpi_export_csv_empty")
        return filepath

    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    logger.info("kpi_export_csv_done", extra={"filepath": filepath, "rows": len(rows)})
    return filepath

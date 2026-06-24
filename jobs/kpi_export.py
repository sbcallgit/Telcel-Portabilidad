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
    """Retorna threads a procesar: nuevos (no están en kpi_conversaciones) o con actividad
    en las últimas 24h (para refrescar stage de Bitrix y mensajes del asesor).
    """
    rows = await db.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (thread_id)
                thread_id,
                checkpoint->'channel_values'->>'etapa'          AS etapa,
                checkpoint->'channel_values'->>'bitrix_lead_id' AS bitrix_lead_id,
                checkpoint->'channel_values'->>'customer_phone' AS customer_phone,
                (checkpoint->>'ts')::timestamptz                AS ultimo_checkpoint
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
        SELECT l.thread_id, l.etapa, l.bitrix_lead_id, l.customer_phone,
               e.creado_el, l.ultimo_checkpoint
        FROM latest l
        JOIN earliest e ON l.thread_id = e.thread_id
        WHERE e.creado_el > NOW() - INTERVAL '30 days'
          AND (
            l.thread_id NOT IN (SELECT id_conversacion FROM kpi_conversaciones)
            OR l.ultimo_checkpoint > NOW() - INTERVAL '24 hours'
          )
        ORDER BY e.creado_el DESC
        LIMIT 500
        """,
    )
    return [dict(r) for r in rows]


async def _get_message_counts(phone: str) -> dict:
    """Cuenta mensajes y extrae texto por actor (cliente/bot) usando graph.aget_state()."""
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

        texto_usuario_parts: list[str] = []
        texto_agente_parts: list[str] = []
        for m in messages:
            content = str(m.content).strip()
            if not content:
                continue
            if isinstance(m, HumanMessage):
                texto_usuario_parts.append(content)
            elif isinstance(m, AIMessage):
                texto_agente_parts.append(content)

        return {
            "mensajes_cliente": len(texto_usuario_parts),
            "mensajes_bot": len(texto_agente_parts),
            "primer_mensaje": primer_msg[:500],
            "texto_usuario": "\n---\n".join(texto_usuario_parts),
            "texto_agente": "\n---\n".join(texto_agente_parts),
            "motivo_escalacion": snapshot.values.get("motivo_escalacion") or "",
        }
    except Exception as exc:
        logger.warning("kpi_msg_count_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return {}


_STAGE_FECHA_MAP = {
    "C90:NEW":        "fecha_nuevo",
    "C90:PROSPECTO":  "fecha_prospecto",
    "C90:UC_8WB2DT":  "fecha_escalamiento",
    "C90:SEGUIMIENTO":"fecha_seguimiento",
    "C90:1":          "fecha_rescate1",
    "C90:2":          "fecha_rescate2",
    "C90:3":          "fecha_rescate3",
    "C90:WON":        "fecha_won",
    "C90:LOSE":       "fecha_lose",
}


def _parse_bitrix_ts(ts_raw: str | None) -> datetime | None:
    """Convierte timestamp de Bitrix (ISO 8601 con offset) a datetime UTC."""
    if not ts_raw:
        return None
    try:
        return datetime.fromisoformat(str(ts_raw)).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


async def _get_deal_data(deal_id: str) -> dict:
    """Consulta crm.deal.get y crm.stagehistory.list para metadatos y trazabilidad del deal."""
    if not deal_id:
        return {}
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        deal, history = await asyncio.gather(
            bx.get_deal(deal_id),
            bx.get_stage_history(deal_id),
        )
        if not deal:
            return {}

        # CLOSEDATE en Bitrix es fecha estimada — solo es cierre real en WON/LOSE
        cerrado_el = None
        stage = deal.get("STAGE_ID", "")
        close_str = deal.get("CLOSEDATE", "")
        if close_str and stage in ("C90:WON", "C90:LOSE"):
            cerrado_el = _parse_bitrix_ts(close_str)

        # Historial de etapas: primera vez que el deal llegó a cada stage
        stage_fechas: dict[str, datetime] = {}
        for entry in history:
            s = entry.get("STAGE_ID", "")
            campo = _STAGE_FECHA_MAP.get(s)
            if campo and campo not in stage_fechas:
                dt = _parse_bitrix_ts(entry.get("CREATED_TIME"))
                if dt:
                    stage_fechas[campo] = dt

        # Tiempos derivados del historial
        tiempo_bot_a_prospecto = None
        if "fecha_nuevo" in stage_fechas and "fecha_prospecto" in stage_fechas:
            delta = (stage_fechas["fecha_prospecto"] - stage_fechas["fecha_nuevo"]).total_seconds()
            tiempo_bot_a_prospecto = round(max(0.0, delta), 1)

        tiempo_prospecto_a_won = None
        if "fecha_prospecto" in stage_fechas and "fecha_won" in stage_fechas:
            delta = (stage_fechas["fecha_won"] - stage_fechas["fecha_prospecto"]).total_seconds()
            tiempo_prospecto_a_won = round(max(0.0, delta), 1)

        return {
            "id_contacto": str(deal.get("CONTACT_ID") or ""),
            "pipeline": str(deal.get("CATEGORY_ID") or ""),
            "origen": str(deal.get("SOURCE_ID") or ""),
            "estado_actual": str(deal.get("STAGE_ID") or ""),
            "empleado": str(deal.get("ASSIGNED_BY_ID") or ""),
            "tipificacion": str(deal.get("COMMENTS") or ""),
            "cerrado_el": cerrado_el,
            "tiempo_bot_a_prospecto_segs": tiempo_bot_a_prospecto,
            "tiempo_prospecto_a_won_segs": tiempo_prospecto_a_won,
            "_raw_history": history,  # historial raw para bitrix_eventos
            **{k: v for k, v in stage_fechas.items()},
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
        chat_id    = await redis.get(f"connector_chat:{phone}")
        bitrix_conversation_id = (await redis.get(f"connector_session:{phone}")) or ""
        if not chat_id:
            return {"_chat_id": "", "_conversation_id": "", "_raw_messages": []}

        result = await _call_poll("im.dialog.messages.get", {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": 200,
        })
        messages = sorted(
            result.get("result", {}).get("messages", []),
            key=lambda m: int(m.get("id", 0)),
        )
        if not messages:
            return {"_chat_id": chat_id, "_raw_messages": []}

        primer_msg_cliente_ts: datetime | None = None
        primera_respuesta: datetime | None = None
        el_bot_respondio_el: datetime | None = None
        el_agente_respondio_el: datetime | None = None
        mensajes_humano = 0
        timestamps: list[datetime] = []

        for msg in messages:
            ts_raw = msg.get("date")
            if not ts_raw:
                continue
            try:
                dt = datetime.fromisoformat(str(ts_raw))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            timestamps.append(dt)

            params = msg.get("params") or {}
            text = (msg.get("text") or "").strip()
            author_id = msg.get("author_id", 0)
            is_bot = text.startswith("🤖 Vera |")
            # Mensajes del bot se envían via imconnector (tienen CONNECTOR_MID)
            # pero NO son mensajes del cliente — se distinguen por el prefijo del texto.
            is_client = bool(isinstance(params, dict) and params.get("CONNECTOR_MID")) and not is_bot

            if is_client and primer_msg_cliente_ts is None:
                primer_msg_cliente_ts = dt

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

        texto_humano_parts: list[str] = []
        for msg in messages:
            params = msg.get("params") or {}
            text = (msg.get("text") or "").strip()
            is_bot = text.startswith("🤖 Vera |")
            is_client = bool(isinstance(params, dict) and params.get("CONNECTOR_MID")) and not is_bot
            author_id = msg.get("author_id", 0)
            if not is_client and not is_bot and author_id and text:
                texto_humano_parts.append(text)

        return {
            "_chat_id": chat_id,
            "_conversation_id": bitrix_conversation_id,
            "_raw_messages": messages,
            "primer_msg_cliente_ts": primer_msg_cliente_ts,
            "primera_respuesta": primera_respuesta,
            "el_bot_respondio_el": el_bot_respondio_el,
            "el_agente_respondio_el": el_agente_respondio_el,
            "mensajes_humano": mensajes_humano,
            "texto_humano": "\n---\n".join(texto_humano_parts),
            "tiempo_promedio_respuestas_segs": round(sum(gaps) / len(gaps), 1) if gaps else None,
            "tiempo_maximo_respuesta_segs": round(max(gaps), 1) if gaps else None,
        }
    except Exception as exc:
        logger.warning("kpi_chat_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return {}


async def _generate_summary(
    texto_usuario: str,
    texto_agente: str,
    texto_humano: str,
    etapa: str,
) -> str:
    """Genera un resumen de la conversación usando el LLM del proyecto."""
    if not texto_usuario:
        return ""
    try:
        from agents.llm import get_llm

        partes = [f"Cliente:\n{texto_usuario[:800]}"]
        if texto_agente:
            partes.append(f"Vera (bot):\n{texto_agente[:800]}")
        if texto_humano:
            partes.append(f"Asesor humano:\n{texto_humano[:400]}")

        conversacion = "\n\n".join(partes)
        prompt = (
            "Eres un analista de ventas de portabilidad Telcel. "
            "Resume en máximo 3 oraciones cortas esta conversación. "
            f"La etapa final fue: {etapa or 'desconocida'}. "
            "Incluye: qué quería el cliente, cómo respondió el agente y el resultado. "
            "Responde solo el resumen, sin encabezados ni viñetas.\n\n"
            f"{conversacion}"
        )
        llm = get_llm(temperature=0.1)
        response = await llm.ainvoke(prompt)
        return str(response.content).strip()[:600]
    except Exception as exc:
        logger.warning("kpi_summary_error", extra={"error": str(exc)})
        return ""


async def _get_rescates_enviados(phone: str) -> int:
    """Lee leads.seguimientos_enviados para el teléfono dado."""
    try:
        row = await db.fetchrow(
            "SELECT seguimientos_enviados FROM leads WHERE telefono = $1", phone
        )
        return int(row["seguimientos_enviados"]) if row else 0
    except Exception:
        return 0


async def _upsert(thread: dict) -> None:
    phone = thread["thread_id"]
    creado_el = thread.get("creado_el")
    deal_id = thread.get("bitrix_lead_id") or ""
    etapa = thread.get("etapa") or ""

    msg_data, deal, chat, rescates = await asyncio.gather(
        _get_message_counts(phone),
        _get_deal_data(deal_id),
        _get_chat_data(phone),
        _get_rescates_enviados(phone),
        return_exceptions=True,
    )
    if isinstance(msg_data, Exception):
        msg_data = {}
    if isinstance(deal, Exception):
        deal = {}
    if isinstance(chat, Exception):
        chat = {}
    if isinstance(rescates, Exception):
        rescates = 0

    primera_respuesta = chat.get("primera_respuesta")
    primer_msg_cliente_ts = chat.get("primer_msg_cliente_ts")
    cerrado_el = deal.get("cerrado_el")

    tiempo_primera = (
        max(0.0, round((primera_respuesta - primer_msg_cliente_ts).total_seconds(), 1))
        if primer_msg_cliente_ts and primera_respuesta else None
    )
    tiempo_cierre = (
        round((cerrado_el - creado_el).total_seconds(), 1)
        if creado_el and cerrado_el else None
    )

    msgs_cliente = msg_data.get("mensajes_cliente", 0)
    msgs_bot = msg_data.get("mensajes_bot", 0)
    msgs_humano = chat.get("mensajes_humano", 0)

    texto_usuario = msg_data.get("texto_usuario", "")
    texto_agente = msg_data.get("texto_agente", "")
    texto_humano = chat.get("texto_humano", "")

    existing = await db.fetchrow(
        "SELECT resumen FROM kpi_conversaciones WHERE id_conversacion = $1", phone
    )
    resumen_existente = existing["resumen"] if existing else ""
    resumen = resumen_existente or await _generate_summary(texto_usuario, texto_agente, texto_humano, etapa)

    await db.execute(
        """
        INSERT INTO kpi_conversaciones (
            id_conversacion, id_contacto, id_negociacion, telefono,
            pipeline, origen, primer_mensaje, tipo_mensaje,
            estado_actual, etapa, empleado, tipificacion,
            mensajes_totales, mensajes_cliente, mensajes_bot, mensajes_humano,
            creado_el, primera_respuesta, el_bot_respondio_el,
            solicitud_enviada_al_agente_el, el_agente_respondio_el, cerrado_el,
            tiempo_primera_respuesta_segs, tiempo_promedio_respuestas_segs,
            tiempo_maximo_respuesta_segs, tiempo_cierre_segs,
            fecha_nuevo, fecha_prospecto, fecha_escalamiento, fecha_seguimiento,
            fecha_rescate1, fecha_rescate2, fecha_rescate3,
            fecha_won, fecha_lose,
            tiempo_bot_a_prospecto_segs, tiempo_prospecto_a_won_segs,
            rescates_enviados,
            texto_usuario, texto_agente, texto_humano, resumen,
            motivo_escalacion,
            fecha_extraccion
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8,
            $9, $10, $11, $12,
            $13, $14, $15, $16,
            $17, $18, $19,
            $20, $21, $22,
            $23, $24, $25, $26,
            $27, $28, $29, $30,
            $31, $32, $33,
            $34, $35,
            $36, $37,
            $38,
            $39, $40, $41, $42,
            $43,
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
            tipificacion                   = EXCLUDED.tipificacion,
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
            fecha_nuevo                    = EXCLUDED.fecha_nuevo,
            fecha_prospecto                = EXCLUDED.fecha_prospecto,
            fecha_escalamiento             = EXCLUDED.fecha_escalamiento,
            fecha_seguimiento              = EXCLUDED.fecha_seguimiento,
            fecha_rescate1                 = EXCLUDED.fecha_rescate1,
            fecha_rescate2                 = EXCLUDED.fecha_rescate2,
            fecha_rescate3                 = EXCLUDED.fecha_rescate3,
            fecha_won                      = EXCLUDED.fecha_won,
            fecha_lose                     = EXCLUDED.fecha_lose,
            tiempo_bot_a_prospecto_segs    = EXCLUDED.tiempo_bot_a_prospecto_segs,
            tiempo_prospecto_a_won_segs    = EXCLUDED.tiempo_prospecto_a_won_segs,
            rescates_enviados              = EXCLUDED.rescates_enviados,
            texto_usuario                  = EXCLUDED.texto_usuario,
            texto_agente                   = EXCLUDED.texto_agente,
            texto_humano                   = EXCLUDED.texto_humano,
            resumen                        = EXCLUDED.resumen,
            motivo_escalacion              = EXCLUDED.motivo_escalacion,
            fecha_extraccion               = NOW()
        """,
        phone, deal.get("id_contacto", ""), deal_id, phone,
        deal.get("pipeline", ""), deal.get("origen", ""),
        msg_data.get("primer_mensaje", ""), "Entrante",
        deal.get("estado_actual", etapa), etapa, deal.get("empleado", ""),
        deal.get("tipificacion", ""),
        msgs_cliente + msgs_bot + msgs_humano,
        msgs_cliente, msgs_bot, msgs_humano,
        creado_el, primera_respuesta, chat.get("el_bot_respondio_el"),
        None,  # solicitud_enviada_al_agente_el — pendiente v2
        chat.get("el_agente_respondio_el"), cerrado_el,
        tiempo_primera,
        chat.get("tiempo_promedio_respuestas_segs"),
        chat.get("tiempo_maximo_respuesta_segs"),
        tiempo_cierre,
        deal.get("fecha_nuevo"), deal.get("fecha_prospecto"),
        deal.get("fecha_escalamiento"), deal.get("fecha_seguimiento"),
        deal.get("fecha_rescate1"), deal.get("fecha_rescate2"), deal.get("fecha_rescate3"),
        deal.get("fecha_won"), deal.get("fecha_lose"),
        deal.get("tiempo_bot_a_prospecto_segs"), deal.get("tiempo_prospecto_a_won_segs"),
        rescates,
        texto_usuario, texto_agente, texto_humano, resumen,
        msg_data.get("motivo_escalacion", ""),
    )

    # Poblar bitrix_eventos con mensajes e historial real de Bitrix
    raw_history  = deal.get("_raw_history", [])
    raw_messages = chat.get("_raw_messages", [])
    chat_id_val  = chat.get("_chat_id", "")
    conversation_id_val = chat.get("_conversation_id", "")
    if raw_history or raw_messages:
        from jobs.kpi_eventos import upsert_eventos_from_bitrix
        await upsert_eventos_from_bitrix(
            id_conversacion=phone,
            deal_id=deal_id,
            chat_id=chat_id_val,
            bitrix_conversation_id=conversation_id_val,
            telefono=phone,
            raw_messages=raw_messages,
            raw_history=raw_history,
            empleado_id=deal.get("empleado", ""),
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
        filepath = f"/app/reporteskpi/kpi_conversaciones_{ts}.csv"

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

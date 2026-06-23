"""Eventos granulares del canal Bitrix Open Lines.

Tabla bitrix_eventos: una fila por mensaje (usuario / bot / humano)
o por cambio de etapa (tipo_actor = 'sistema'). Permite reconstruir
el timeline completo de cada conversación con el stage vigente en
cada momento.

Funciones principales:
- upsert_eventos_from_bitrix(): llamada desde kpi_export._upsert() para
  mantener la tabla actualizada con datos frescos de Bitrix.
- seed_from_kpi_conversaciones(): migración inicial que llama a Bitrix
  por cada conversación registrada en kpi_conversaciones.
"""

import asyncio
import logging
from datetime import datetime, timezone

from integrations.postgres import client as db
from integrations.postgres.client import get_connection

logger = logging.getLogger(__name__)

_STAGE_NOMBRES: dict[str, str] = {
    "C90:NEW":         "Lead Nuevo / IA Porta",
    "C90:PROSPECTO":   "Prospecto",
    "C90:UC_8WB2DT":   "Escalamiento Humano",
    "C90:SEGUIMIENTO": "Seguimiento",
    "C90:1":           "Rescate 1",
    "C90:2":           "Rescate 2",
    "C90:3":           "Rescate 3",
    "C90:WON":         "Venta",
    "C90:LOSE":        "Caído",
    "C90:8":                 "Recuperación",
    "C90:PREPAYMENT_INVOIC": "Recuperación",
}

_INSERT_SQL = """
    INSERT INTO bitrix_eventos (
        id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
        message_id, fecha_evento, tipo_actor, texto,
        stage_id, stage_nombre, empleado_id,
        stage_anterior, stage_anterior_nombre,
        duracion_en_stage_segs, duracion_formateada
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
    ON CONFLICT (id_conversacion, message_id, tipo_actor) DO UPDATE SET
        bitrix_conversation_id  = EXCLUDED.bitrix_conversation_id,
        fecha_evento            = EXCLUDED.fecha_evento,
        texto                   = EXCLUDED.texto,
        stage_id                = EXCLUDED.stage_id,
        stage_nombre            = EXCLUDED.stage_nombre,
        empleado_id             = EXCLUDED.empleado_id,
        stage_anterior          = EXCLUDED.stage_anterior,
        stage_anterior_nombre   = EXCLUDED.stage_anterior_nombre,
        duracion_en_stage_segs  = EXCLUDED.duracion_en_stage_segs,
        duracion_formateada     = EXCLUDED.duracion_formateada
"""


def _fmt_duracion(segs: float) -> str:
    """Convierte segundos a 'HHh MMm SSs' legible (ej. '2h 15m 30s')."""
    segs = int(segs)
    h, rem = divmod(segs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _to_utc(raw) -> datetime | None:
    if not raw:
        return None
    try:
        if isinstance(raw, datetime):
            return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(str(raw)).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _stage_at(fecha: datetime, history: list[tuple[str, datetime]]) -> tuple[str, str]:
    """Devuelve (stage_id, stage_nombre) vigente en el momento del evento.

    history debe estar ordenado cronológicamente: [(stage_id, datetime), ...].
    """
    stage_id = ""
    for sid, sdt in history:
        if sdt <= fecha:
            stage_id = sid
        else:
            break
    return stage_id, _STAGE_NOMBRES.get(stage_id, stage_id)


def _parse_stage_history(raw_history: list[dict]) -> list[tuple[str, datetime]]:
    """Convierte la respuesta de crm.stagehistory.list a lista (stage_id, datetime) UTC."""
    result: list[tuple[str, datetime]] = []
    for entry in raw_history:
        dt = _to_utc(entry.get("CREATED_TIME"))
        if dt:
            result.append((entry.get("STAGE_ID", ""), dt))
    result.sort(key=lambda x: x[1])
    return result


def _parse_messages(
    messages: list[dict],
) -> list[tuple[str, datetime, str, str]]:
    """Parsea mensajes de im.dialog.messages.get.

    Retorna lista de (message_id, fecha, tipo_actor, texto).
    tipo_actor: 'usuario' | 'bot' | 'humano'
    """
    resultado: list[tuple[str, datetime, str, str]] = []
    for msg in messages:
        ts_raw = msg.get("date")
        fecha = _to_utc(ts_raw)
        if not fecha:
            continue

        text = (msg.get("text") or "").strip()
        params = msg.get("params") or {}
        author_id = msg.get("author_id", 0)
        msg_id = str(msg.get("id", ""))

        is_bot = text.startswith("🤖 Vera |")
        # Mensajes del cliente vienen con CONNECTOR_MID en params (vía imconnector)
        is_client = bool(isinstance(params, dict) and params.get("CONNECTOR_MID")) and not is_bot

        if is_bot:
            tipo_actor = "bot"
        elif is_client:
            tipo_actor = "usuario"
        elif author_id:
            tipo_actor = "humano"
        else:
            continue  # mensaje de sistema interno, ignorar

        resultado.append((msg_id, fecha, tipo_actor, text))
    return resultado


def _build_rows(
    id_conversacion: str,
    deal_id: str,
    chat_id: str,
    bitrix_conversation_id: str,
    telefono: str,
    empleado_id: str,
    parsed_messages: list[tuple[str, datetime, str, str]],
    stage_history: list[tuple[str, datetime]],
    raw_history: list[dict],
) -> list[tuple]:
    """Construye las filas para bitrix_eventos.

    Incluye:
    - Un row por mensaje (usuario / bot / humano) con el stage vigente en ese momento.
    - Un row por cambio de etapa (tipo_actor = 'sistema').
    """
    rows: list[tuple] = []

    # Mensajes del canal Open Lines (sin campos de trazabilidad de stage)
    for msg_id, fecha, tipo_actor, texto in parsed_messages:
        sid, sname = _stage_at(fecha, stage_history)
        rows.append((
            id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
            msg_id, fecha, tipo_actor, texto,
            sid, sname, empleado_id,
            "", "", None, "",  # stage_anterior, stage_anterior_nombre, duracion, fmt
        ))

    # Cambios de etapa como eventos 'sistema' con trazabilidad completa
    stage_entries: list[tuple[str, datetime]] = []
    for entry in raw_history:
        dt = _to_utc(entry.get("CREATED_TIME"))
        stage_id = entry.get("STAGE_ID", "")
        if dt and stage_id:
            stage_entries.append((stage_id, dt))

    for i, (stage_id, dt) in enumerate(stage_entries):
        # Stage anterior y duración desde la transición previa
        if i > 0:
            prev_stage_id, prev_dt = stage_entries[i - 1]
            stage_ant = prev_stage_id
            stage_ant_nombre = _STAGE_NOMBRES.get(prev_stage_id, prev_stage_id)
            delta_segs = round((dt - prev_dt).total_seconds(), 1)
            duracion_fmt = _fmt_duracion(delta_segs) if delta_segs >= 0 else ""
        else:
            stage_ant, stage_ant_nombre = "", ""
            delta_segs, duracion_fmt = None, ""

        rows.append((
            id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
            f"stage_{stage_id}_{int(dt.timestamp())}",
            dt, "sistema", f"Etapa → {_STAGE_NOMBRES.get(stage_id, stage_id)}",
            stage_id, _STAGE_NOMBRES.get(stage_id, stage_id), empleado_id,
            stage_ant, stage_ant_nombre, delta_segs, duracion_fmt,
        ))

    return rows


async def upsert_eventos_from_bitrix(
    id_conversacion: str,
    deal_id: str,
    chat_id: str,
    bitrix_conversation_id: str,
    telefono: str,
    raw_messages: list[dict],
    raw_history: list[dict],
    empleado_id: str = "",
) -> None:
    """Inserta/actualiza eventos de mensajes y cambios de etapa para una conversación.

    Llamado desde kpi_export._upsert() con datos frescos de Bitrix.

    raw_messages: respuesta de im.dialog.messages.get → result → messages
    raw_history: respuesta de crm.stagehistory.list → result → items
    """
    if not raw_messages and not raw_history:
        return

    stage_history = _parse_stage_history(raw_history)
    parsed_messages = _parse_messages(raw_messages)
    rows = _build_rows(
        id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
        empleado_id, parsed_messages, stage_history, raw_history,
    )
    if not rows:
        return

    async with get_connection() as conn:
        await conn.executemany(_INSERT_SQL, rows)

    logger.info(
        "bitrix_eventos_upserted",
        extra={
            "id_conversacion": id_conversacion,
            "mensajes": len(parsed_messages),
            "etapas": len(raw_history),
        },
    )


async def _fetch_bitrix_data(
    deal_id: str,
    phone: str,
) -> tuple[str, str, list[dict], list[dict]]:
    """Obtiene bitrix_conversation_id, chat_id, mensajes y historial de etapas desde Bitrix/Redis."""
    from integrations.bitrix.client import BitrixClient
    from integrations.bitrix.connector import _call_poll
    from integrations.redis_client import get_redis

    redis = await get_redis()
    chat_id    = (await redis.get(f"connector_chat:{phone}"))    or ""
    bitrix_conversation_id = (await redis.get(f"connector_session:{phone}")) or ""

    raw_messages: list[dict] = []
    if chat_id:
        try:
            result = await _call_poll("im.dialog.messages.get", {
                "DIALOG_ID": f"chat{chat_id}",
                "LIMIT": 200,
            })
            raw_messages = sorted(
                result.get("result", {}).get("messages", []),
                key=lambda m: int(m.get("id", 0)),
            )
        except Exception as exc:
            logger.warning("bitrix_eventos_chat_error", extra={"phone_tail": phone[-4:], "error": str(exc)})

    raw_history: list[dict] = []
    if deal_id:
        try:
            bx = BitrixClient()
            raw_history = await bx.get_stage_history(deal_id)
        except Exception as exc:
            logger.warning("bitrix_eventos_history_error", extra={"deal_id": deal_id, "error": str(exc)})

    return bitrix_conversation_id, chat_id, raw_messages, raw_history


async def seed_from_kpi_conversaciones() -> dict:
    """Migración inicial: puebla bitrix_eventos desde kpi_conversaciones existente.

    Por cada conversación llama a Bitrix para obtener mensajes e historial de etapas.
    Seguro re-ejecutar — usa ON CONFLICT DO UPDATE.

    Retorna {"conversaciones": N, "eventos": M}.
    """
    kpi_rows = await db.fetch(
        "SELECT id_conversacion, id_negociacion, telefono, empleado FROM kpi_conversaciones"
    )

    total_conversaciones = 0
    total_eventos = 0

    for kpi in kpi_rows:
        phone = kpi["telefono"] or kpi["id_conversacion"]
        deal_id = kpi.get("id_negociacion") or ""
        empleado_id = str(kpi.get("empleado") or "")

        try:
            bitrix_conversation_id, chat_id, raw_messages, raw_history = await _fetch_bitrix_data(deal_id, phone)
            stage_history = _parse_stage_history(raw_history)
            parsed_messages = _parse_messages(raw_messages)
            rows = _build_rows(
                kpi["id_conversacion"], deal_id, chat_id, bitrix_conversation_id, phone,
                empleado_id, parsed_messages, stage_history, raw_history,
            )
            if rows:
                async with get_connection() as conn:
                    await conn.executemany(_INSERT_SQL, rows)
                total_conversaciones += 1
                total_eventos += len(rows)
        except Exception as exc:
            logger.warning(
                "bitrix_eventos_seed_error",
                extra={"id_conversacion": kpi["id_conversacion"], "error": str(exc)},
            )

        await asyncio.sleep(0.2)  # respeta rate limit de Bitrix entre conversaciones

    logger.info(
        "bitrix_eventos_seed_done",
        extra={"conversaciones": total_conversaciones, "eventos": total_eventos},
    )
    return {"conversaciones": total_conversaciones, "eventos": total_eventos}

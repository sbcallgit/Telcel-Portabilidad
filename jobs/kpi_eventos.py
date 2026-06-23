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

_STAGE_COLUMN: dict[str, str] = {
    "C90:NEW":               "new",
    "C90:PROSPECTO":         "prospecto",
    "C90:UC_8WB2DT":         "escalamiento",
    "C90:SEGUIMIENTO":       "seguimiento",
    "C90:1":                 "rescate1",
    "C90:2":                 "rescate2",
    "C90:3":                 "rescate3",
    "C90:WON":               "won",
    "C90:LOSE":              "lose",
    "C90:8":                 "recuperacion",
    "C90:PREPAYMENT_INVOIC": "recuperacion",
}

_STAGE_COLS = ["new", "prospecto", "escalamiento", "seguimiento",
               "rescate1", "rescate2", "rescate3", "won", "lose", "recuperacion"]

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
        duracion_en_stage_segs, duracion_formateada,
        canal, wa_message_id, autor_bitrix_id
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
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
        duracion_formateada     = EXCLUDED.duracion_formateada,
        canal                   = EXCLUDED.canal,
        wa_message_id           = CASE
                                      WHEN EXCLUDED.wa_message_id <> '' THEN EXCLUDED.wa_message_id
                                      ELSE bitrix_eventos.wa_message_id
                                  END,
        autor_bitrix_id         = EXCLUDED.autor_bitrix_id
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
) -> list[tuple[str, datetime, str, str, str, str]]:
    """Parsea mensajes de im.dialog.messages.get.

    Retorna lista de (message_id, fecha, tipo_actor, texto, wa_message_id, autor_bitrix_id).

    message_id: CONNECTOR_MID cuando está disponible (WA/Telegram/bot sintético), si no el
                ID entero de Bitrix. Esto hace que el ID sea estable entre el insert
                real-time y el job nocturno, evitando duplicados sin índice parcial.
    wa_message_id: igual a message_id para mensajes de usuario/bot (ID de origen WA/Telegram).
                   Vacío para mensajes del asesor humano (solo tienen ID Bitrix).
    """
    resultado: list[tuple[str, datetime, str, str, str, str]] = []
    for msg in messages:
        ts_raw = msg.get("date")
        fecha = _to_utc(ts_raw)
        if not fecha:
            continue

        text = (msg.get("text") or "").strip()
        params = msg.get("params") or {}
        author_id = msg.get("author_id", 0)
        bitrix_msg_id = str(msg.get("id", ""))
        connector_mid = str(params.get("CONNECTOR_MID", "")) if isinstance(params, dict) else ""

        is_bot = text.startswith("🤖 Vera |")
        is_client = bool(connector_mid) and not is_bot

        if is_bot:
            tipo_actor = "bot"
            # CONNECTOR_MID = el ID sintético "bot_{phone}_{ts}" que enviamos a imconnector
            msg_id = connector_mid or bitrix_msg_id
            wa_msg_id = connector_mid
        elif is_client:
            tipo_actor = "usuario"
            # CONNECTOR_MID = WA message ID original (wamid.xxx)
            msg_id = connector_mid or bitrix_msg_id
            wa_msg_id = connector_mid
        elif author_id:
            tipo_actor = "humano"
            msg_id = bitrix_msg_id
            wa_msg_id = ""
        else:
            continue  # mensaje de sistema interno, ignorar

        autor_bitrix_id = str(author_id) if author_id else ""
        resultado.append((msg_id, fecha, tipo_actor, text, wa_msg_id, autor_bitrix_id))
    return resultado


def _build_rows(
    id_conversacion: str,
    deal_id: str,
    chat_id: str,
    bitrix_conversation_id: str,
    telefono: str,
    empleado_id: str,
    parsed_messages: list[tuple[str, datetime, str, str, str, str]],
    stage_history: list[tuple[str, datetime]],
    raw_history: list[dict],
) -> list[tuple]:
    """Construye las filas para bitrix_eventos.

    Incluye:
    - Un row por mensaje (usuario / bot / humano) con el stage vigente en ese momento.
    - Un row por cambio de etapa (tipo_actor = 'sistema').
    """
    rows: list[tuple] = []
    canal = "telegram" if id_conversacion.startswith("tg_") else "whatsapp"

    # Mensajes del canal Open Lines (sin campos de trazabilidad de stage)
    for msg_id, fecha, tipo_actor, texto, wa_message_id, autor_bitrix_id in parsed_messages:
        sid, sname = _stage_at(fecha, stage_history)
        rows.append((
            id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
            msg_id, fecha, tipo_actor, texto,
            sid, sname, empleado_id,
            "", "", None, "",  # stage_anterior, stage_anterior_nombre, duracion, fmt
            canal, wa_message_id, autor_bitrix_id,
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
            canal, "", empleado_id,
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


_TIMELINE_INSERT = """
    INSERT INTO bitrix_deal_timeline (
        deal_id, id_conversacion, telefono,
        fecha_new,          duracion_new_segs,
        fecha_prospecto,    duracion_prospecto_segs,
        fecha_escalamiento, duracion_escalamiento_segs,
        fecha_seguimiento,  duracion_seguimiento_segs,
        fecha_rescate1,     duracion_rescate1_segs,
        fecha_rescate2,     duracion_rescate2_segs,
        fecha_rescate3,     duracion_rescate3_segs,
        fecha_won,          duracion_won_segs,
        fecha_lose,         duracion_lose_segs,
        fecha_recuperacion, duracion_recuperacion_segs,
        empleado_id
    ) VALUES (
        $1, $2, $3,
        $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
        $14, $15, $16, $17, $18, $19, $20, $21, $22, $23,
        $24
    )
    ON CONFLICT (deal_id) DO UPDATE SET
        id_conversacion    = EXCLUDED.id_conversacion,
        telefono           = EXCLUDED.telefono,
        -- fecha_*: preservar la primera vez que el deal entró a cada stage
        fecha_new          = COALESCE(bitrix_deal_timeline.fecha_new,          EXCLUDED.fecha_new),
        fecha_prospecto    = COALESCE(bitrix_deal_timeline.fecha_prospecto,    EXCLUDED.fecha_prospecto),
        fecha_escalamiento = COALESCE(bitrix_deal_timeline.fecha_escalamiento, EXCLUDED.fecha_escalamiento),
        fecha_seguimiento  = COALESCE(bitrix_deal_timeline.fecha_seguimiento,  EXCLUDED.fecha_seguimiento),
        fecha_rescate1     = COALESCE(bitrix_deal_timeline.fecha_rescate1,     EXCLUDED.fecha_rescate1),
        fecha_rescate2     = COALESCE(bitrix_deal_timeline.fecha_rescate2,     EXCLUDED.fecha_rescate2),
        fecha_rescate3     = COALESCE(bitrix_deal_timeline.fecha_rescate3,     EXCLUDED.fecha_rescate3),
        fecha_won          = COALESCE(bitrix_deal_timeline.fecha_won,          EXCLUDED.fecha_won),
        fecha_lose         = COALESCE(bitrix_deal_timeline.fecha_lose,         EXCLUDED.fecha_lose),
        fecha_recuperacion = COALESCE(bitrix_deal_timeline.fecha_recuperacion, EXCLUDED.fecha_recuperacion),
        -- duracion_*: tomar el nuevo valor si llega (puede actualizarse si el deal re-entra)
        duracion_new_segs          = COALESCE(EXCLUDED.duracion_new_segs,          bitrix_deal_timeline.duracion_new_segs),
        duracion_prospecto_segs    = COALESCE(EXCLUDED.duracion_prospecto_segs,    bitrix_deal_timeline.duracion_prospecto_segs),
        duracion_escalamiento_segs = COALESCE(EXCLUDED.duracion_escalamiento_segs, bitrix_deal_timeline.duracion_escalamiento_segs),
        duracion_seguimiento_segs  = COALESCE(EXCLUDED.duracion_seguimiento_segs,  bitrix_deal_timeline.duracion_seguimiento_segs),
        duracion_rescate1_segs     = COALESCE(EXCLUDED.duracion_rescate1_segs,     bitrix_deal_timeline.duracion_rescate1_segs),
        duracion_rescate2_segs     = COALESCE(EXCLUDED.duracion_rescate2_segs,     bitrix_deal_timeline.duracion_rescate2_segs),
        duracion_rescate3_segs     = COALESCE(EXCLUDED.duracion_rescate3_segs,     bitrix_deal_timeline.duracion_rescate3_segs),
        duracion_won_segs          = COALESCE(EXCLUDED.duracion_won_segs,          bitrix_deal_timeline.duracion_won_segs),
        duracion_lose_segs         = COALESCE(EXCLUDED.duracion_lose_segs,         bitrix_deal_timeline.duracion_lose_segs),
        duracion_recuperacion_segs = COALESCE(EXCLUDED.duracion_recuperacion_segs, bitrix_deal_timeline.duracion_recuperacion_segs),
        -- empleado_id: siempre actualizar al asesor asignado más reciente
        empleado_id = EXCLUDED.empleado_id,
        updated_at = NOW()
"""


async def upsert_deal_timeline(
    deal_id: str,
    id_conversacion: str,
    telefono: str,
    stage_id: str,
    fecha_entrada: datetime,
    prev_stage: str,
    duracion_prev_segs: float | None,
    empleado_id: str = "",
) -> None:
    """Upsert en bitrix_deal_timeline con el stage actual y duración del stage anterior.

    Llamado desde el webhook stage-event en cada cambio de etapa.
    - fecha_{stage}: primera vez que el deal entró a ese stage (preservada con COALESCE)
    - duracion_{prev_stage}_segs: tiempo que pasó en el stage anterior antes de esta transición
    """
    if not deal_id:
        return

    # Inicializar todos los valores de fecha y duración a None
    fechas: dict[str, datetime | None] = {c: None for c in _STAGE_COLS}
    duraciones: dict[str, float | None] = {c: None for c in _STAGE_COLS}

    col = _STAGE_COLUMN.get(stage_id)
    if col:
        fechas[col] = fecha_entrada

    prev_col = _STAGE_COLUMN.get(prev_stage) if prev_stage else None
    if prev_col and duracion_prev_segs is not None:
        duraciones[prev_col] = duracion_prev_segs

    values: list = [deal_id, id_conversacion, telefono]
    for c in _STAGE_COLS:
        values.append(fechas[c])
        values.append(duraciones[c])
    values.append(empleado_id)

    try:
        async with get_connection() as conn:
            await conn.execute(_TIMELINE_INSERT, *values)
        logger.info(
            "deal_timeline_upserted",
            extra={"deal_id": deal_id, "stage_id": stage_id, "prev_stage": prev_stage},
        )
    except Exception as exc:
        logger.warning("deal_timeline_error", extra={"deal_id": deal_id, "error": str(exc)})


async def log_mensaje_evento(
    phone: str,
    text: str,
    tipo_actor: str,
    message_id: str,
    wa_message_id: str = "",
    autor_bitrix_id: str = "",
) -> None:
    """Registra un mensaje individual en bitrix_eventos en tiempo real.

    Llamar con asyncio.create_task() para no bloquear el path crítico.

    message_id: WA message ID para usuario, ID sintético "bot_{phone}_{ts}" para bot,
                ID entero de Bitrix para mensajes del asesor humano.
    wa_message_id: igual a message_id para usuario/bot; vacío para humano.
    """
    from integrations.redis_client import get_redis

    try:
        redis = await get_redis()
        deal_id = (await redis.get(f"connector_deal:{phone}")) or ""
        chat_id = (await redis.get(f"connector_chat:{phone}")) or ""
        bitrix_conversation_id = (await redis.get(f"connector_session:{phone}")) or ""

        row = await db.fetchrow(
            "SELECT bitrix_stage FROM leads WHERE telefono = $1", phone
        )
        stage_id = (row["bitrix_stage"] if row else "") or ""

        # Fallback 1: último evento de sistema registrado para esta conversación
        if not stage_id:
            sys_row = await db.fetchrow(
                """
                SELECT stage_id FROM bitrix_eventos
                WHERE id_conversacion = $1 AND tipo_actor = 'sistema'
                ORDER BY fecha_evento DESC LIMIT 1
                """,
                phone,
            )
            stage_id = (sys_row["stage_id"] if sys_row else "") or ""

        # Fallback 2: todos los deals nuevos arrancan en C90:NEW
        if not stage_id:
            stage_id = "C90:NEW"

        stage_nombre = _STAGE_NOMBRES.get(stage_id, stage_id)

        canal = "telegram" if phone.startswith("tg_") else "whatsapp"
        now = datetime.now(timezone.utc)

        await db.execute(
            """
            INSERT INTO bitrix_eventos (
                id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
                message_id, fecha_evento, tipo_actor, texto,
                stage_id, stage_nombre, empleado_id,
                stage_anterior, stage_anterior_nombre,
                duracion_en_stage_segs, duracion_formateada,
                canal, wa_message_id, autor_bitrix_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
            ON CONFLICT (id_conversacion, message_id, tipo_actor) DO UPDATE SET
                texto           = EXCLUDED.texto,
                stage_id        = EXCLUDED.stage_id,
                stage_nombre    = EXCLUDED.stage_nombre,
                deal_id         = CASE WHEN EXCLUDED.deal_id <> '' THEN EXCLUDED.deal_id
                                       ELSE bitrix_eventos.deal_id END,
                wa_message_id   = CASE WHEN EXCLUDED.wa_message_id <> '' THEN EXCLUDED.wa_message_id
                                       ELSE bitrix_eventos.wa_message_id END
            """,
            phone, deal_id, chat_id, bitrix_conversation_id, phone,
            message_id, now, tipo_actor, text,
            stage_id, stage_nombre, "",
            "", "", None, "",
            canal, wa_message_id, autor_bitrix_id,
        )
    except Exception as exc:
        logger.warning(
            "log_mensaje_evento_error",
            extra={"phone_tail": phone[-4:], "tipo_actor": tipo_actor, "error": str(exc)},
        )


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

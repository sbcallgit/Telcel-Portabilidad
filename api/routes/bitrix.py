"""Endpoints para el flujo OAuth de Bitrix24 y webhooks de automatización.

GET  /bitrix/app         → recibe el ?code= del redirect OAuth y guarda tokens
POST /bitrix/install     → hook de instalación de la app (requerido por Bitrix24)
POST /bitrix/stage-event → webhook de regla de automatización: registra cambio de stage
                           en bitrix_eventos con trazabilidad de duración entre stages.

Configuración de la regla de automatización en Bitrix24:
  - Disparador: "Al mover el deal a esta etapa" (en cada stage del pipeline 90)
  - Acción: "Webhook saliente" → POST https://portabilidad.callcomcc.io/bitrix/stage-event
  - Campos a enviar (form-encoded):
      deal_id   = {=Document:ID}
      stage_id  = {=Document:STAGE_ID}
      prev_stage= {=Document:PREVIOUS_STAGE_ID}
      phone     = {=Document:UF_CRM_PHONE}   (opcional — mejora lookup de Redis)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from integrations.bitrix.oauth import exchange_code
from integrations.postgres import client as db

router = APIRouter()
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
    "C90:8":                  "Recuperación",
    "C90:PREPAYMENT_INVOIC":  "Recuperación",
}


def _fmt_duracion(segs: float) -> str:
    segs = int(max(0, segs))
    h, rem = divmod(segs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


@router.get("/bitrix/app", response_class=HTMLResponse)
async def bitrix_oauth_callback(code: str = Query(default="")) -> str:
    """Recibe el código de autorización OAuth y lo intercambia por tokens."""
    if not code:
        logger.warning("bitrix_oauth_no_code")
        return "<h3>Error: no se recibió código de autorización.</h3>"

    try:
        await exchange_code(code)
        logger.info("bitrix_oauth_callback_ok")
        return (
            "<h3>✅ Autorización exitosa.</h3>"
            "<p>Los tokens de Bitrix24 se guardaron correctamente.</p>"
            "<p>Puedes cerrar esta ventana.</p>"
        )
    except Exception as exc:
        logger.error("bitrix_oauth_callback_error", extra={"error": str(exc)})
        return f"<h3>❌ Error al autorizar:</h3><pre>{exc}</pre>"


@router.post("/bitrix/install")
async def bitrix_install_hook() -> dict:
    """Hook requerido por Bitrix24 al instalar la app local."""
    logger.info("bitrix_app_install_hook")
    return {"status": "ok"}


@router.post("/bitrix/stage-event")
async def bitrix_stage_event(request: Request) -> dict:
    """Recibe el webhook de la regla de automatización de Bitrix cuando un deal cambia de stage.

    Registra el evento en bitrix_eventos con:
    - Stage anterior y nuevo
    - Duración exacta en el stage anterior (segundos + formato HH:MM:SS)
    - chat_id y bitrix_conversation_id desde Redis
    - empleado_id desde el deal en Bitrix
    """
    # Bitrix automation envía form-encoded; aceptamos también JSON
    from urllib.parse import parse_qs
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        body = await request.body()
        raw = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
        # parse_qs devuelve listas; tomamos el primer valor de cada clave
        payload = {k: v[0] for k, v in raw.items()}

    # Bitrix automation envía document_id[2]=DEAL_12345; también aceptamos deal_id directo
    raw_doc = str(payload.get("document_id[2]") or "").strip()
    deal_id = raw_doc.replace("DEAL_", "") if raw_doc.startswith("DEAL_") else raw_doc
    deal_id = deal_id or str(payload.get("deal_id") or payload.get("DEAL_ID") or "").strip()

    stage_id   = str(payload.get("stage_id")  or payload.get("STAGE_ID")  or "").strip()
    prev_stage = str(payload.get("prev_stage") or payload.get("PREV_STAGE") or "").strip()
    phone_hint = str(payload.get("phone") or "").strip()

    if not deal_id:
        logger.warning("bitrix_stage_event_no_deal_id", extra={"payload": str(payload)[:200]})
        return {"status": "ignored", "reason": "no deal_id"}

    logger.info("bitrix_stage_event_received", extra={"deal_id": deal_id, "stage_id": stage_id})

    # Si Bitrix no envió el stage, lo consultamos directamente
    empleado_id = ""
    if not stage_id or not prev_stage:
        try:
            from integrations.bitrix.client import BitrixClient
            bx = BitrixClient()
            deal = await bx.get_deal(deal_id)
            stage_id   = stage_id  or deal.get("STAGE_ID", "")
            prev_stage = prev_stage or deal.get("PREVIOUS_STAGE_ID", "")
            empleado_id = str(deal.get("ASSIGNED_BY_ID") or "")
        except Exception as exc:
            logger.warning("bitrix_stage_event_deal_fetch_error", extra={"deal_id": deal_id, "error": str(exc)})

    if not stage_id:
        return {"status": "ignored", "reason": "no stage_id"}

    # Buscar el teléfono del lead (para Redis lookup)
    phone = phone_hint
    if not phone:
        row = await db.fetchrow(
            "SELECT telefono FROM leads WHERE bitrix_lead_id = $1", deal_id
        )
        phone = row["telefono"] if row else ""

    # chat_id y conversation_id desde Redis
    chat_id = ""
    bitrix_conversation_id = ""
    if phone:
        try:
            from integrations.redis_client import get_redis
            redis = await get_redis()
            chat_id = (await redis.get(f"connector_chat:{phone}")) or ""
            bitrix_conversation_id = (await redis.get(f"connector_session:{phone}")) or ""
        except Exception as exc:
            logger.warning("bitrix_stage_event_redis_error", extra={"error": str(exc)})

    # Evento anterior para calcular duración en el stage previo
    now = datetime.now(tz=timezone.utc)
    duracion_segs: float | None = None
    duracion_fmt = ""

    prev_evento = await db.fetchrow(
        """
        SELECT stage_id, fecha_evento
        FROM bitrix_eventos
        WHERE deal_id = $1 AND tipo_actor = 'sistema'
        ORDER BY fecha_evento DESC
        LIMIT 1
        """,
        deal_id,
    )

    if prev_evento:
        # Hay evento previo en nuestra tabla — calcular desde ahí
        if not prev_stage:
            prev_stage = prev_evento["stage_id"]
        delta = (now - prev_evento["fecha_evento"]).total_seconds()
        if delta >= 0:
            duracion_segs = round(delta, 1)
            duracion_fmt = _fmt_duracion(delta)
    elif prev_stage:
        # Primer evento del deal — consultar crm.stagehistory.list para saber
        # cuándo entró al stage anterior y calcular duración real
        try:
            from integrations.bitrix.client import BitrixClient
            bx = BitrixClient()
            history = await bx.get_stage_history(deal_id)
            # Buscar la última vez que el deal llegó a prev_stage
            entrada_prev: datetime | None = None
            for entry in reversed(history):
                if entry.get("STAGE_ID") == prev_stage:
                    ts_raw = entry.get("CREATED_TIME")
                    if ts_raw:
                        try:
                            entrada_prev = datetime.fromisoformat(str(ts_raw)).astimezone(timezone.utc)
                        except (ValueError, TypeError):
                            pass
                    break
            if entrada_prev:
                delta = (now - entrada_prev).total_seconds()
                if delta >= 0:
                    duracion_segs = round(delta, 1)
                    duracion_fmt = _fmt_duracion(delta)
        except Exception as exc:
            logger.warning("bitrix_stage_event_history_error", extra={"deal_id": deal_id, "error": str(exc)})

    stage_nombre      = _STAGE_NOMBRES.get(stage_id, stage_id)
    prev_stage_nombre = _STAGE_NOMBRES.get(prev_stage, prev_stage) if prev_stage else ""
    id_conversacion   = phone or deal_id
    message_id        = f"stage_{stage_id}_{int(now.timestamp())}"
    texto             = f"Etapa → {stage_nombre}"

    # Obtener últimos mensajes por actor desde el chat de Bitrix Open Lines
    ult_msg_usuario = ""
    fecha_ult_usuario: datetime | None = None
    ult_msg_bot = ""
    fecha_ult_bot: datetime | None = None
    ult_msg_humano = ""
    fecha_ult_humano: datetime | None = None

    if chat_id:
        try:
            from integrations.bitrix.connector import _call_poll
            from jobs.kpi_eventos import _parse_messages, _to_utc as _kpi_to_utc
            result = await _call_poll("im.dialog.messages.get", {
                "DIALOG_ID": f"chat{chat_id}",
                "LIMIT": 200,
            })
            msgs_raw = sorted(
                result.get("result", {}).get("messages", []),
                key=lambda m: int(m.get("id", 0)),
            )
            for msg_id_m, fecha_m, tipo_m, texto_m in _parse_messages(msgs_raw):
                if tipo_m == "usuario":
                    ult_msg_usuario = texto_m
                    fecha_ult_usuario = fecha_m
                elif tipo_m == "bot":
                    ult_msg_bot = texto_m.replace("🤖 Vera | ", "", 1)
                    fecha_ult_bot = fecha_m
                elif tipo_m == "humano":
                    ult_msg_humano = texto_m
                    fecha_ult_humano = fecha_m
        except Exception as exc:
            logger.warning("bitrix_stage_event_msgs_error", extra={"deal_id": deal_id, "error": str(exc)})

    await db.execute(
        """
        INSERT INTO bitrix_eventos (
            id_conversacion, deal_id, chat_id, bitrix_conversation_id, telefono,
            message_id, fecha_evento, tipo_actor, texto,
            stage_id, stage_nombre, empleado_id,
            stage_anterior, stage_anterior_nombre,
            duracion_en_stage_segs, duracion_formateada,
            ultimo_mensaje_usuario, fecha_ultimo_usuario,
            ultimo_mensaje_bot,     fecha_ultimo_bot,
            ultimo_mensaje_humano,  fecha_ultimo_humano
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
        ON CONFLICT (id_conversacion, message_id, tipo_actor) DO NOTHING
        """,
        id_conversacion, deal_id, chat_id, bitrix_conversation_id, phone,
        message_id, now, "sistema", texto,
        stage_id, stage_nombre, empleado_id,
        prev_stage, prev_stage_nombre,
        duracion_segs, duracion_fmt,
        ult_msg_usuario, fecha_ult_usuario,
        ult_msg_bot,     fecha_ult_bot,
        ult_msg_humano,  fecha_ult_humano,
    )

    logger.info(
        "bitrix_stage_event_registered",
        extra={
            "deal_id": deal_id,
            "stage_anterior": prev_stage,
            "stage_nuevo": stage_id,
            "duracion_formateada": duracion_fmt or "—",
        },
    )
    return {"status": "ok", "deal_id": deal_id, "stage": stage_id, "duracion": duracion_fmt or None}

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

from config.settings import settings
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


@router.get("/bitrix/auth")
async def bitrix_oauth_start() -> HTMLResponse:
    """Inicia el flujo OAuth — redirige al portal de Bitrix24 para autorización."""
    from fastapi.responses import RedirectResponse
    domain = settings.bitrix_webhook_url.split("/rest/")[0].replace("https://", "")
    redirect_uri = f"{settings.bitrix_public_url}/bitrix/app"
    url = (
        f"https://{domain}/oauth/authorize/"
        f"?client_id={settings.bitrix_client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url)


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
    canal             = "telegram" if id_conversacion.startswith("tg_") else "whatsapp"
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
            from jobs.kpi_eventos import _parse_messages
            result = await _call_poll("im.dialog.messages.get", {
                "DIALOG_ID": f"chat{chat_id}",
                "LIMIT": 200,
            })
            msgs_raw = sorted(
                result.get("result", {}).get("messages", []),
                key=lambda m: int(m.get("id", 0)),
            )
            for _mid, fecha_m, tipo_m, texto_m, _wa_mid, _autor in _parse_messages(msgs_raw):
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

    # Fallback: si no hay chat_id en Redis, usar los mensajes ya registrados en bitrix_eventos
    if not chat_id and deal_id and not (ult_msg_usuario or ult_msg_bot or ult_msg_humano):
        try:
            rows_local = await db.fetch(
                """
                SELECT tipo_actor, texto, fecha_evento
                FROM bitrix_eventos
                WHERE deal_id = $1 AND tipo_actor IN ('usuario', 'bot', 'humano')
                ORDER BY fecha_evento DESC
                LIMIT 60
                """,
                deal_id,
            )
            for r in rows_local:
                actor = r["tipo_actor"]
                if actor == "usuario" and not ult_msg_usuario:
                    ult_msg_usuario = r["texto"]
                    fecha_ult_usuario = r["fecha_evento"]
                elif actor == "bot" and not ult_msg_bot:
                    ult_msg_bot = r["texto"].replace("🤖 Vera | ", "", 1)
                    fecha_ult_bot = r["fecha_evento"]
                elif actor == "humano" and not ult_msg_humano:
                    ult_msg_humano = r["texto"]
                    fecha_ult_humano = r["fecha_evento"]
        except Exception as exc:
            logger.warning("bitrix_stage_event_local_fallback_error", extra={"deal_id": deal_id, "error": str(exc)})

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
            ultimo_mensaje_humano,  fecha_ultimo_humano,
            canal, wa_message_id, autor_bitrix_id
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25)
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
        canal, "", empleado_id,
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

    # Actualizar timeline pivoteado por deal
    from jobs.kpi_eventos import upsert_deal_timeline
    import asyncio as _asyncio
    _asyncio.create_task(upsert_deal_timeline(
        deal_id=deal_id,
        id_conversacion=id_conversacion,
        telefono=phone,
        stage_id=stage_id,
        fecha_entrada=now,
        prev_stage=prev_stage,
        duracion_prev_segs=duracion_segs,
        empleado_id=empleado_id,
    ))

    return {"status": "ok", "deal_id": deal_id, "stage": stage_id, "duracion": duracion_fmt or None}


# ---------------------------------------------------------------------------
# Embed CRM — pestaña del deal
# ---------------------------------------------------------------------------

def _html_embed(deal_id: str, summary: dict | None, totales: dict, eventos: list[dict], is_pausado: bool = False) -> str:
    """Genera HTML self-contained para incrustar en la pestaña del deal de Bitrix24."""
    from datetime import timezone as _tz

    def _fmt_dt(iso: str | None) -> str:
        if not iso:
            return "—"
        try:
            from datetime import datetime as _dt
            d = _dt.fromisoformat(iso.replace("Z", "+00:00"))
            d = d.astimezone(_tz.utc)
            return d.strftime("%d/%m %H:%M:%S")
        except Exception:
            return iso[:16]

    def _fmt_secs(s) -> str:
        if s is None:
            return "—"
        try:
            s = int(s)
        except Exception:
            return "—"
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"

    actor_badge = {
        "usuario": ('<span style="background:#dbeafe;color:#1e40af;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600">Usuario</span>'),
        "bot":     ('<span style="background:#fee2e2;color:#991b1b;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600">Bot</span>'),
        "humano":  ('<span style="background:#fef3c7;color:#92400e;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600">Asesor</span>'),
        "sistema": ('<span style="background:#f1f5f9;color:#475569;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600">Sistema</span>'),
    }

    mensajes = [e for e in eventos if e.get("tipo_actor") != "sistema"]
    transiciones = [e for e in eventos if e.get("tipo_actor") == "sistema"]

    # ── Cards HTML ────────────────────────────────────────────────────────
    cards_html = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">
      <div style="background:#fff;border-radius:10px;padding:12px 14px;border-top:3px solid #e8001d;box-shadow:0 1px 3px rgba(0,0,0,.07)">
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">Mensajes Bot</div>
        <div style="font-size:22px;font-weight:700">{totales.get('mensajes_bot', 0)}</div>
      </div>
      <div style="background:#fff;border-radius:10px;padding:12px 14px;border-top:3px solid #3b82f6;box-shadow:0 1px 3px rgba(0,0,0,.07)">
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">Mensajes Usuario</div>
        <div style="font-size:22px;font-weight:700">{totales.get('mensajes_usuario', 0)}</div>
      </div>
      <div style="background:#fff;border-radius:10px;padding:12px 14px;border-top:3px solid #f59e0b;box-shadow:0 1px 3px rgba(0,0,0,.07)">
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">Mensajes Asesor</div>
        <div style="font-size:22px;font-weight:700">{totales.get('mensajes_humano', 0)}</div>
      </div>
      <div style="background:#fff;border-radius:10px;padding:12px 14px;border-top:3px solid #10b981;box-shadow:0 1px 3px rgba(0,0,0,.07)">
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">Costo Total (USD)</div>
        <div style="font-size:22px;font-weight:700">${totales.get('costo_total_usd', 0):.4f}</div>
        <div style="font-size:10px;color:#94a3b8;margin-top:2px">{totales.get('tokens_entrada_total',0):,}↑ {totales.get('tokens_salida_total',0):,}↓ tokens</div>
      </div>
    </div>"""

    # ── Resumen ───────────────────────────────────────────────────────────
    resumen_html = ""
    if summary and summary.get("resumen"):
        motivo = f'<span style="font-size:11px;color:#94a3b8;margin-top:4px;display:block">Motivo escalamiento: <strong style="color:#64748b">{summary["motivo_escalacion"]}</strong></span>' if summary.get("motivo_escalacion") else ""
        resumen_html = f"""
    <div style="background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.07)">
      <div style="font-size:13px;font-weight:600;margin-bottom:8px">Resumen</div>
      <p style="color:#475569;line-height:1.6;margin:0;font-size:13px">{summary['resumen']}</p>
      {motivo}
    </div>"""

    # ── Tabla de mensajes ─────────────────────────────────────────────────
    rows = ""
    for e in mensajes:
        actor = e.get("tipo_actor", "")
        badge = actor_badge.get(actor, actor)
        costo = f'<span style="color:#10b981;font-size:11px;font-weight:600">${e["costo_usd"]:.4f}</span>' if e.get("costo_usd") is not None else ""
        tokens = f'<span style="color:#94a3b8;font-size:10px">{e.get("tokens_entrada",0):,}↑ {e.get("tokens_salida",0):,}↓</span>' if e.get("tokens_entrada") is not None else ""
        texto = str(e.get("texto") or "").replace("<", "&lt;").replace(">", "&gt;")
        rows += f"""<tr>
          <td style="padding:5px 8px;color:#64748b;font-size:11px;white-space:nowrap">{_fmt_dt(e.get('fecha_evento'))}</td>
          <td style="padding:5px 8px">{badge}</td>
          <td style="padding:5px 8px;font-size:12px;line-height:1.5;max-width:480px;word-break:break-word">{texto}</td>
          <td style="padding:5px 8px;white-space:nowrap">{costo}</td>
          <td style="padding:5px 8px;white-space:nowrap">{tokens}</td>
        </tr>"""

    msgs_count = len(mensajes)
    msgs_html = f"""
    <div style="background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.07)">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Mensajes ({msgs_count})</div>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:1px solid #e2e8f0">
              <th style="text-align:left;font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;padding:5px 8px;white-space:nowrap">Hora</th>
              <th style="text-align:left;font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;padding:5px 8px">Actor</th>
              <th style="text-align:left;font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;padding:5px 8px">Mensaje</th>
              <th style="text-align:left;font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;padding:5px 8px">Costo</th>
              <th style="text-align:left;font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;padding:5px 8px">Tokens</th>
            </tr>
          </thead>
          <tbody>{rows or '<tr><td colspan="5" style="text-align:center;padding:16px;color:#94a3b8;font-style:italic">Sin mensajes registrados</td></tr>'}</tbody>
        </table>
      </div>
    </div>"""

    # ── Pipeline ──────────────────────────────────────────────────────────
    pipeline_html = ""
    if transiciones:
        cards_pip = ""
        for i, t in enumerate(transiciones):
            if i == 0 and t.get("stage_anterior"):
                cards_pip += f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;min-width:110px"><div style="font-size:11px;font-weight:700">{_STAGE_NOMBRES.get(t["stage_anterior"], t.get("stage_anterior_nombre") or t["stage_anterior"])}</div><div style="font-size:10px;color:#94a3b8">Inicio</div></div><div style="padding:0 6px;color:#94a3b8;font-size:16px;line-height:38px">→</div>'
            dur_html = f'<div style="font-size:10px;color:#94a3b8;margin-top:2px">← {t["duracion_formateada"]}</div>' if t.get("duracion_formateada") else ""
            stage_label = _STAGE_NOMBRES.get(t.get("stage_id", ""), t.get("stage_nombre") or t.get("stage_id", ""))
            cards_pip += f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;min-width:110px"><div style="font-size:11px;font-weight:700">{stage_label}</div><div style="font-size:10px;color:#64748b">{_fmt_dt(t.get("fecha_evento"))}</div>{dur_html}</div>'
            if i < len(transiciones) - 1:
                cards_pip += '<div style="padding:0 6px;color:#94a3b8;font-size:16px;line-height:38px">→</div>'
        pipeline_html = f"""
    <div style="background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.07)">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Pipeline ({len(transiciones)} transiciones)</div>
      <div style="display:flex;flex-wrap:nowrap;overflow-x:auto;gap:0;align-items:flex-start;padding-bottom:6px">{cards_pip}</div>
    </div>"""

    telefono = (summary or {}).get("telefono") or deal_id
    stage_actual = _STAGE_NOMBRES.get((summary or {}).get("estado_actual", ""), (summary or {}).get("estado_actual") or "")
    primer_msg = _fmt_dt((summary or {}).get("creado_el"))
    t1r = _fmt_secs((summary or {}).get("tiempo_primera_respuesta_segs"))
    asesor = (summary or {}).get("empleado") or "—"

    btn_bg      = "#dc2626" if not is_pausado else "#16a34a"
    btn_label   = "⏸ Pausar Bot" if not is_pausado else "▶ Activar Bot"
    btn_action  = "pause" if not is_pausado else "resume"
    status_dot  = ("#16a34a", "Activo") if not is_pausado else ("#dc2626", "Pausado")
    api_base    = settings.bitrix_public_url
    admin_tok   = settings.admin_token

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conversación {telefono}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:Inter,system-ui,sans-serif;background:#f4f6f9;color:#1a202c;font-size:13px;padding:14px}}</style>
</head><body>
<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;flex-wrap:wrap">
  <div>
    <h1 style="font-size:16px;font-weight:700">{telefono}</h1>
    <p style="font-size:12px;color:#64748b">
      Etapa: <strong>{stage_actual}</strong>
      · Asesor: <strong>{asesor}</strong>
      · Primer mensaje: {primer_msg}
      · 1ª respuesta bot: {t1r}
    </p>
  </div>
  <div style="display:flex;align-items:center;gap:10px;flex-shrink:0">
    <span id="bot-status" style="display:flex;align-items:center;gap:5px;font-size:12px;font-weight:600;color:{status_dot[0]}">
      <span style="width:8px;height:8px;border-radius:50%;background:{status_dot[0]};display:inline-block"></span>
      Bot {status_dot[1]}
    </span>
    <button id="bot-toggle-btn"
      onclick="toggleBot()"
      style="background:{btn_bg};color:#fff;border:none;border-radius:8px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s"
    >{btn_label}</button>
  </div>
</div>
<script>
  var _dealId  = "{deal_id}";
  var _action  = "{btn_action}";
  var _apiBase = "{api_base}";
  var _tok     = "{admin_tok}";

  function toggleBot() {{
    var btn = document.getElementById('bot-toggle-btn');
    btn.disabled = true;
    btn.style.opacity = '0.6';

    fetch(_apiBase + '/bitrix/bot-toggle', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json', 'X-Admin-Token': _tok}},
      body: JSON.stringify({{deal_id: _dealId, action: _action}})
    }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.status === 'ok') {{
        var nowPausado = (_action === 'pause');
        _action = nowPausado ? 'resume' : 'pause';
        btn.textContent  = nowPausado ? '▶ Activar Bot' : '⏸ Pausar Bot';
        btn.style.background = nowPausado ? '#16a34a' : '#dc2626';
        var dot   = document.getElementById('bot-status');
        var color = nowPausado ? '#dc2626' : '#16a34a';
        dot.style.color = color;
        dot.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:' + color + ';display:inline-block"></span> Bot ' + (nowPausado ? 'Pausado' : 'Activo');
      }} else {{
        alert('Error: ' + (data.detail || data.status));
      }}
    }})
    .catch(function(e) {{ alert('Error de red: ' + e); }})
    .finally(function() {{
      btn.disabled = false;
      btn.style.opacity = '1';
    }});
  }}
</script>
{cards_html}
{resumen_html}
{msgs_html}
{pipeline_html}
</body></html>"""


@router.post("/bitrix/deal-embed", response_class=HTMLResponse)
async def bitrix_deal_embed(request: Request) -> str:
    """Placement handler para la pestaña del deal en Bitrix24.

    Bitrix POST fields:
      AUTH_ID           → access token del usuario que abre la pestaña
      DOMAIN            → dominio del portal (b24-ahyle8.bitrix24.mx)
      PLACEMENT_OPTIONS → JSON: {"ID": "<deal_id>"}
    """
    import json as _json
    from urllib.parse import parse_qs

    body = await request.body()
    raw = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    def _f(key: str, default: str = "") -> str:
        vals = raw.get(key, [])
        return vals[0] if vals else default

    auth_id  = _f("AUTH_ID")
    domain   = _f("DOMAIN")
    opts_raw = _f("PLACEMENT_OPTIONS", "{}")

    try:
        opts = _json.loads(opts_raw) if isinstance(opts_raw, str) else {}
    except Exception:
        opts = {}

    deal_id = str(opts.get("ID", "")).strip()

    if not deal_id:
        return "<body style='font-family:sans-serif;padding:20px'><p style='color:#991b1b'>No se recibió deal_id en PLACEMENT_OPTIONS.</p></body>"

    # Validar el token de Bitrix (llamada ligera a profile)
    if auth_id and domain:
        try:
            async with __import__("httpx").AsyncClient(timeout=5) as hx:
                r = await hx.get(f"https://{domain}/rest/profile.json", params={"auth": auth_id})
                if r.status_code != 200 or r.json().get("error"):
                    logger.warning("bitrix_embed_auth_invalid", extra={"deal_id": deal_id})
                    return "<body style='font-family:sans-serif;padding:20px'><p style='color:#991b1b'>Token de Bitrix inválido o expirado.</p></body>"
        except Exception as exc:
            logger.warning("bitrix_embed_auth_check_failed", extra={"error": str(exc)})
            # Si la validación falla por red, continuamos (mejor mostrar datos que bloquear)

    # Buscar id_conversacion desde leads (más confiable: teléfono → id_conversacion)
    lead_row = await db.fetchrow(
        "SELECT telefono FROM leads WHERE bitrix_lead_id = $1",
        deal_id,
    )
    id_conversacion: str | None = None
    if lead_row:
        id_conversacion = lead_row["telefono"]
    else:
        # Fallback: buscar directo en bitrix_eventos
        ev_row = await db.fetchrow(
            "SELECT id_conversacion FROM bitrix_eventos WHERE deal_id = $1 AND id_conversacion != deal_id LIMIT 1",
            deal_id,
        )
        if ev_row:
            id_conversacion = ev_row["id_conversacion"]
        else:
            id_conversacion = deal_id  # último fallback: deal_id = id_conversacion (Open Lines)

    # Resumen desde kpi_conversaciones
    summary_row = await db.fetchrow(
        """SELECT id_conversacion, telefono, estado_actual, etapa, empleado,
                  creado_el, cerrado_el, resumen, motivo_escalacion,
                  tiempo_primera_respuesta_segs, tiempo_cierre_segs
           FROM kpi_conversaciones WHERE id_conversacion = $1""",
        id_conversacion,
    )

    # Totales + eventos desde bitrix_eventos
    totales_row = await db.fetchrow(
        """SELECT
               COALESCE(SUM(costo_usd) FILTER (WHERE tipo_actor = 'bot'), 0)     AS costo_total_usd,
               COALESCE(SUM(tokens_entrada) FILTER (WHERE tipo_actor = 'bot'), 0) AS tokens_entrada_total,
               COALESCE(SUM(tokens_salida)  FILTER (WHERE tipo_actor = 'bot'), 0) AS tokens_salida_total,
               COUNT(*) FILTER (WHERE tipo_actor = 'bot')                         AS mensajes_bot,
               COUNT(*) FILTER (WHERE tipo_actor = 'usuario')                     AS mensajes_usuario,
               COUNT(*) FILTER (WHERE tipo_actor = 'humano')                      AS mensajes_humano
           FROM bitrix_eventos WHERE id_conversacion = $1""",
        id_conversacion,
    )

    evento_rows = await db.fetch(
        """SELECT fecha_evento, tipo_actor, texto, stage_id, stage_nombre,
                  tokens_entrada, tokens_salida, costo_usd,
                  stage_anterior, stage_anterior_nombre,
                  duracion_en_stage_segs, duracion_formateada
           FROM bitrix_eventos WHERE id_conversacion = $1
           ORDER BY fecha_evento ASC NULLS LAST""",
        id_conversacion,
    )

    summary = None
    if summary_row:
        summary = {
            "id_conversacion":              summary_row["id_conversacion"],
            "telefono":                     summary_row["telefono"],
            "estado_actual":                summary_row["estado_actual"] or "",
            "empleado":                     summary_row["empleado"] or "",
            "creado_el":                    summary_row["creado_el"].isoformat() if summary_row["creado_el"] else None,
            "resumen":                      summary_row["resumen"] or "",
            "motivo_escalacion":            summary_row["motivo_escalacion"] or "",
            "tiempo_primera_respuesta_segs": float(summary_row["tiempo_primera_respuesta_segs"]) if summary_row["tiempo_primera_respuesta_segs"] else None,
        }

    totales = {
        "costo_total_usd":      float(totales_row["costo_total_usd"] or 0),
        "tokens_entrada_total": int(totales_row["tokens_entrada_total"] or 0),
        "tokens_salida_total":  int(totales_row["tokens_salida_total"] or 0),
        "mensajes_bot":         int(totales_row["mensajes_bot"] or 0),
        "mensajes_usuario":     int(totales_row["mensajes_usuario"] or 0),
        "mensajes_humano":      int(totales_row["mensajes_humano"] or 0),
    }

    eventos = [
        {
            "fecha_evento":           r["fecha_evento"].isoformat() if r["fecha_evento"] else None,
            "tipo_actor":             r["tipo_actor"],
            "texto":                  r["texto"] or "",
            "stage_id":               r["stage_id"] or "",
            "stage_nombre":           _STAGE_NOMBRES.get(r["stage_id"] or "", r["stage_nombre"] or ""),
            "tokens_entrada":         int(r["tokens_entrada"]) if r["tokens_entrada"] is not None else None,
            "tokens_salida":          int(r["tokens_salida"]) if r["tokens_salida"] is not None else None,
            "costo_usd":              float(r["costo_usd"]) if r["costo_usd"] is not None else None,
            "stage_anterior":         r["stage_anterior"] or None,
            "stage_anterior_nombre":  _STAGE_NOMBRES.get(r["stage_anterior"] or "", r["stage_anterior_nombre"] or "") if r["stage_anterior"] else None,
            "duracion_formateada":    r["duracion_formateada"] or None,
        }
        for r in evento_rows
    ]

    from integrations.redis_client import get_redis
    redis = await get_redis()
    is_pausado = bool(await redis.get(f"bot_pausado:{id_conversacion}"))

    logger.info("bitrix_embed_served", extra={"deal_id": deal_id, "id_conversacion": id_conversacion, "is_pausado": is_pausado})
    return _html_embed(deal_id, summary, totales, eventos, is_pausado=is_pausado)


# ---------------------------------------------------------------------------
# Bot toggle desde el iframe del deal
# ---------------------------------------------------------------------------

@router.post("/bitrix/bot-toggle")
async def bitrix_bot_toggle(request: Request) -> dict:
    """Pausa o reactiva el bot para el número vinculado al deal.

    Llamado desde el botón JS del iframe de /bitrix/deal-embed.
    Body JSON: {"deal_id": "...", "action": "pause"|"resume"}
    Auth: header X-Admin-Token.
    """
    import json as _json
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from integrations.postgres.client import fetchval
    from integrations.bitrix.client import BitrixClient
    from integrations.redis_client import get_redis

    # Validar token
    token = request.headers.get("X-Admin-Token", "")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Body JSON inválido")

    deal_id = str(body.get("deal_id", "")).strip()
    action  = str(body.get("action", "")).strip()

    if not deal_id:
        raise HTTPException(status_code=422, detail="deal_id requerido")
    if action not in ("pause", "resume"):
        raise HTTPException(status_code=422, detail="action debe ser 'pause' o 'resume'")

    # Buscar teléfono desde deal_id
    phone = await fetchval("SELECT telefono FROM leads WHERE bitrix_lead_id = $1 LIMIT 1", deal_id)
    if not phone:
        # Fallback: buscar en bitrix_eventos
        phone = await fetchval("SELECT id_conversacion FROM bitrix_eventos WHERE deal_id = $1 LIMIT 1", deal_id)
    if not phone:
        raise HTTPException(status_code=404, detail=f"No se encontró teléfono para deal_id={deal_id}")

    phone = str(phone)
    redis = await get_redis()
    redis_key = f"bot_pausado:{phone}"

    if action == "pause":
        await redis.set(redis_key, "1")
    else:
        await redis.delete(redis_key)

    logger.info("bitrix_embed_bot_toggle", extra={"deal_id": deal_id, "action": action, "phone_tail": phone[-4:]})
    return {"status": "ok", "action": action, "deal_id": deal_id}


# ---------------------------------------------------------------------------
# Pestaña "Control Bot" — solo el botón, sin datos sensibles (para asesores)
# ---------------------------------------------------------------------------

def _html_bot_control(deal_id: str, is_pausado: bool) -> str:
    """HTML minimalista con únicamente el botón de pausa/reactivación del bot."""
    btn_bg     = "#dc2626" if not is_pausado else "#16a34a"
    btn_label  = "⏸ Pausar Bot" if not is_pausado else "▶ Activar Bot"
    btn_action = "pause" if not is_pausado else "resume"
    dot_color  = "#16a34a" if not is_pausado else "#dc2626"
    status_txt = "Activo" if not is_pausado else "Pausado"
    api_base   = settings.bitrix_public_url
    admin_tok  = settings.admin_token

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Control Bot</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;background:#f4f6f9;color:#1a202c;
     display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:#fff;border-radius:14px;padding:32px 40px;box-shadow:0 2px 8px rgba(0,0,0,.1);
       text-align:center;max-width:340px;width:100%}}
.status{{display:inline-flex;align-items:center;gap:8px;font-size:14px;font-weight:600;margin-bottom:24px}}
.dot{{width:12px;height:12px;border-radius:50%}}
.btn{{width:100%;padding:12px 0;border:none;border-radius:10px;font-size:15px;
      font-weight:700;color:#fff;cursor:pointer;transition:opacity .15s,transform .1s}}
.btn:active{{transform:scale(.97)}}
.btn:disabled{{opacity:.6;cursor:not-allowed}}
.msg{{margin-top:16px;font-size:12px;color:#64748b;min-height:18px}}
</style>
</head><body>
<div class="card">
  <div style="font-size:13px;color:#94a3b8;margin-bottom:6px">Deal #{deal_id}</div>
  <h2 style="font-size:17px;font-weight:700;margin-bottom:20px">Control del Bot Vera</h2>

  <div class="status">
    <span id="dot" class="dot" style="background:{dot_color}"></span>
    <span id="status-txt">Bot <strong>{status_txt}</strong></span>
  </div>

  <button id="btn" class="btn" style="background:{btn_bg}" onclick="toggle()">
    {btn_label}
  </button>
  <div id="msg" class="msg"></div>
</div>

<script>
  var _dealId  = "{deal_id}";
  var _action  = "{btn_action}";
  var _apiBase = "{api_base}";
  var _tok     = "{admin_tok}";

  function toggle() {{
    var btn = document.getElementById('btn');
    var msg = document.getElementById('msg');
    btn.disabled = true;
    msg.textContent = 'Aplicando cambio...';

    fetch(_apiBase + '/bitrix/bot-toggle', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json', 'X-Admin-Token': _tok}},
      body: JSON.stringify({{deal_id: _dealId, action: _action}})
    }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.status === 'ok') {{
        var nowPausado = (_action === 'pause');
        _action = nowPausado ? 'resume' : 'pause';

        var color = nowPausado ? '#dc2626' : '#16a34a';
        document.getElementById('dot').style.background = color;
        document.getElementById('status-txt').innerHTML =
          'Bot <strong>' + (nowPausado ? 'Pausado' : 'Activo') + '</strong>';

        btn.style.background = nowPausado ? '#16a34a' : '#dc2626';
        btn.textContent = nowPausado ? '▶ Activar Bot' : '⏸ Pausar Bot';
        msg.style.color = '#10b981';
        msg.textContent = nowPausado ? 'Bot pausado correctamente.' : 'Bot reactivado correctamente.';
      }} else {{
        msg.style.color = '#dc2626';
        msg.textContent = 'Error: ' + (data.detail || data.status);
      }}
    }})
    .catch(function(e) {{
      msg.style.color = '#dc2626';
      msg.textContent = 'Error de red. Intenta de nuevo.';
    }})
    .finally(function() {{ btn.disabled = false; }});
  }}
</script>
</body></html>"""


@router.post("/bitrix/bot-control", response_class=HTMLResponse)
async def bitrix_bot_control_embed(request: Request) -> str:
    """Placement handler de la pestaña 'Control Bot' — solo el botón toggle.

    Accesible para asesores sin exponer datos sensibles de la conversación.
    Misma mecánica de autenticación que /bitrix/deal-embed.
    """
    import json as _json
    from urllib.parse import parse_qs
    from integrations.redis_client import get_redis

    body = await request.body()
    raw = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)

    def _f(key: str, default: str = "") -> str:
        vals = raw.get(key, [])
        return vals[0] if vals else default

    auth_id  = _f("AUTH_ID")
    domain   = _f("DOMAIN")
    opts_raw = _f("PLACEMENT_OPTIONS", "{}")

    try:
        opts = _json.loads(opts_raw) if isinstance(opts_raw, str) else {}
    except Exception:
        opts = {}

    deal_id = str(opts.get("ID", "")).strip()
    if not deal_id:
        return "<body style='font-family:sans-serif;padding:20px'><p style='color:#991b1b'>No se recibió deal_id.</p></body>"

    # Validar token del asesor contra el portal
    if auth_id and domain:
        try:
            async with __import__("httpx").AsyncClient(timeout=5) as hx:
                r = await hx.get(f"https://{domain}/rest/profile.json", params={"auth": auth_id})
                if r.status_code != 200 or r.json().get("error"):
                    return "<body style='font-family:sans-serif;padding:20px'><p style='color:#991b1b'>Token de Bitrix inválido o expirado.</p></body>"
        except Exception as exc:
            logger.warning("bitrix_bot_control_auth_check_failed", extra={"error": str(exc)})

    # Buscar teléfono para leer estado del bot en Redis
    from integrations.postgres.client import fetchval
    phone = await fetchval("SELECT telefono FROM leads WHERE bitrix_lead_id = $1 LIMIT 1", deal_id)
    if not phone:
        phone = await fetchval("SELECT id_conversacion FROM bitrix_eventos WHERE deal_id = $1 LIMIT 1", deal_id)
    if not phone:
        phone = deal_id

    phone = str(phone)
    redis = await get_redis()
    is_pausado = bool(await redis.get(f"bot_pausado:{phone}"))

    logger.info("bitrix_bot_control_served", extra={"deal_id": deal_id, "is_pausado": is_pausado})
    return _html_bot_control(deal_id, is_pausado)


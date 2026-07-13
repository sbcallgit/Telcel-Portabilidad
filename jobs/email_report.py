"""Envío del reporte diario de KPIs por correo electrónico.

Se llama al final de job_kpi_export() — no es un job independiente.
Usa smtplib estándar (SSL puerto 465) en un executor para no bloquear el event loop.
"""

import asyncio
import csv
import io
import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz

from config.settings import settings
from integrations.postgres import client as db

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Monterrey")


def _mes_actual_range() -> tuple[datetime, datetime]:
    """Retorna (inicio_del_mes, fin_de_ayer) en UTC.

    El reporte corre a las 00:01 del día N — captura el cierre del día N-1.
    Ejemplo: 00:01 del 23 → rango 1 jun 00:00 ... 22 jun 23:59:59.
    """
    from datetime import timedelta
    ahora = datetime.now(tz=TZ)
    ayer = (ahora - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    inicio = ayer.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return inicio.astimezone(timezone.utc), ayer.astimezone(timezone.utc)


async def _get_daily_stats() -> dict:
    """KPIs agregados del 1° del mes hasta hoy desde kpi_conversaciones."""
    inicio_mes, ahora = _mes_actual_range()
    rows = await db.fetch(
        """
        SELECT
            COUNT(*)                                                      AS total,
            COUNT(*) FILTER (WHERE mensajes_humano > 0)                   AS con_asesor,
            COUNT(*) FILTER (WHERE estado_actual IN ('C90:WON'))          AS ganadas,
            COUNT(*) FILTER (WHERE estado_actual IN ('C90:LOSE'))         AS perdidas,
            ROUND(AVG(tiempo_primera_respuesta_segs)::numeric, 1)         AS tpr_prom,
            ROUND(AVG(tiempo_cierre_segs)::numeric, 1)                    AS cierre_prom,
            ROUND(AVG(mensajes_bot::numeric / NULLIF(mensajes_totales,0) * 100), 1) AS pct_bot,
            ROUND(AVG(mensajes_cliente)::numeric, 1)                      AS msgs_cliente_prom
        FROM kpi_conversaciones
        WHERE creado_el >= $1 AND creado_el <= $2
        """,
        inicio_mes, ahora,
    )
    return dict(rows[0]) if rows else {}


async def _get_meta_data(inicio: datetime, fin: datetime) -> dict:
    """Datos de Meta Ads para el periodo al nivel campaña. Retorna {} si no hay config o error."""
    from config.settings import settings
    if not settings.meta_access_token or not settings.meta_ad_account_id:
        return {}
    try:
        from integrations.meta.insights import get_insights
        rows = await get_insights(
            date_preset=None,
            since=str(inicio.date()),
            until=str(fin.date()),
            level="campaign",
        )
        return {
            "total_spend":      round(sum(r["spend"] for r in rows), 2),
            "total_leads_meta": sum(r["wa_conversaciones"] for r in rows),
            "rows":             sorted(rows, key=lambda r: r["spend"], reverse=True),
        }
    except Exception as exc:
        logger.warning("kpi_email_meta_error", extra={"error": str(exc)})
        return {}


async def _get_ai_cost(inicio: datetime, fin: datetime) -> float:
    """Costo total LLM del periodo desde bitrix_eventos (USD)."""
    row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(costo_usd), 0) AS total
        FROM bitrix_eventos
        WHERE tipo_actor = 'bot'
          AND costo_usd IS NOT NULL
          AND fecha_evento >= $1 AND fecha_evento <= $2
        """,
        inicio, fin,
    )
    return float(row["total"]) if row else 0.0


async def _get_utm_conversion(inicio: datetime, fin: datetime) -> list[dict]:
    """Ventas por campaña UTM — JOIN kpi_conversaciones (estado_actual) + leads (UTM)."""
    rows = await db.fetch(
        """
        SELECT
            COALESCE(NULLIF(l.utm_campaign,''), '(sin campaña)') AS campana,
            COUNT(*)                                              AS leads,
            COUNT(*) FILTER (WHERE k.estado_actual = 'C90:WON') AS ventas
        FROM kpi_conversaciones k
        JOIN leads l ON l.telefono = k.id_conversacion
        WHERE k.creado_el >= $1 AND k.creado_el <= $2
          AND l.utm_source != ''
        GROUP BY campana
        ORDER BY leads DESC
        LIMIT 15
        """,
        inicio, fin,
    )
    return [dict(r) for r in rows]


async def _get_leads_reales(inicio: datetime, fin: datetime) -> int:
    """Conteo real de leads (tabla leads) — denominador real del % de conversión.

    total_leads_wa (métrica de Meta) cuenta aperturas de chat que nunca llegan
    a nuestro webhook (número inválido, no llega a escribir, etc.), infla el
    denominador y hace ver la conversión artificialmente baja.
    """
    row = await db.fetchrow(
        """
        SELECT COUNT(*) AS total
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
        """,
        inicio, fin,
    )
    return int(row["total"]) if row else 0


async def _get_conversion_by_day(dias: int = 14) -> list[dict]:
    """% conversión por día de creación del lead (cohorte) — refuerza el acumulado mensual
    del reporte con una vista diaria que expone variaciones día a día.

    Cuenta ventas sobre leads.bitrix_stage (sincronizado cada 30 min por job_bitrix_sync)
    en vez de kpi_conversaciones.estado_actual (solo se actualiza una vez al día, a las
    3am por job_kpi_export) — con kpi_conversaciones, los últimos 1-2 días del reporte
    mostraban 0% de conversión aunque ya hubiera ventas reales en Bitrix, simplemente
    porque esos leads todavía no habían sido procesados por el export nocturno.
    """
    desde = datetime.now(tz=timezone.utc) - timedelta(days=dias)
    rows = await db.fetch(
        """
        SELECT
            date_trunc('day', created_at)::date              AS dia,
            COUNT(*)                                          AS leads,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON')  AS ventas
        FROM leads
        WHERE created_at >= $1
        GROUP BY 1
        ORDER BY 1 DESC
        """,
        desde,
    )
    return [
        {
            "dia":      r["dia"].strftime("%d/%m"),
            "leads":    r["leads"],
            "ventas":   r["ventas"],
            "pct_conv": round(r["ventas"] / r["leads"] * 100, 1) if r["leads"] else 0.0,
        }
        for r in rows
    ]


def _merge_campaign_data(meta: dict, utm_conv: list[dict]) -> list[dict]:
    """Fusiona datos de Meta (spend, leads WA) con conversión UTM (ventas) por campaign_id.

    Se agrupa por campaign_id (no por nombre) porque dos campañas pueden compartir
    el mismo nombre — agrupar por nombre las colapsaba y perdía el spend de una de
    las dos.
    """
    meta_by_id  = {r["campaign_id"]: r for r in meta.get("rows", [])}
    utm_by_name = {r["campana"]: r for r in utm_conv}
    nombres_con_meta = {m.get("campaign_name") for m in meta_by_id.values()}

    merged = []
    for cid, m in meta_by_id.items():
        name   = m.get("campaign_name") or cid
        u      = utm_by_name.get(name, {})
        spend  = float(m.get("spend", 0) or 0)
        leads  = int(m.get("wa_conversaciones", 0) or u.get("leads", 0) or 0)
        ventas = int(u.get("ventas", 0) or 0)
        merged.append({
            "campaign_id": cid,
            "name":     name,
            "spend":    round(spend, 2),
            "leads":    leads,
            "ventas":   ventas,
            "cpl":      round(spend / leads, 2)  if leads  else None,
            "cpa":      round(spend / ventas, 2) if ventas else None,
            "pct_conv": round(ventas / leads * 100, 1) if leads else 0.0,
        })

    # Campañas presentes solo en el UTM (sin match en Meta Ads)
    for name, u in utm_by_name.items():
        if name in nombres_con_meta:
            continue
        leads  = int(u.get("leads", 0) or 0)
        ventas = int(u.get("ventas", 0) or 0)
        merged.append({
            "campaign_id": None,
            "name":     name,
            "spend":    0.0,
            "leads":    leads,
            "ventas":   ventas,
            "cpl":      None,
            "cpa":      None,
            "pct_conv": round(ventas / leads * 100, 1) if leads else 0.0,
        })

    return sorted(merged, key=lambda x: x["spend"], reverse=True)


async def _build_csv() -> bytes:
    """CSV del mes actual (del día 1 hasta hoy) de kpi_conversaciones como bytes."""
    inicio_mes, ahora = _mes_actual_range()
    rows = await db.fetch(
        """
        SELECT * FROM kpi_conversaciones
        WHERE creado_el >= $1 AND creado_el <= $2
        ORDER BY creado_el ASC
        """,
        inicio_mes, ahora,
    )
    if not rows:
        return b""

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))

    return buf.getvalue().encode("utf-8-sig")


def _build_html(stats: dict, rango: str, meta: dict | None = None, ai_cost_usd: float = 0.0, campanas: list[dict] | None = None, conversion_diaria: list[dict] | None = None, total_leads_reales: int = 0) -> str:
    total = stats.get("total") or 0
    con_asesor = stats.get("con_asesor") or 0
    ganadas = stats.get("ganadas") or 0
    perdidas = stats.get("perdidas") or 0
    tpr = stats.get("tpr_prom")
    cierre = stats.get("cierre_prom")
    pct_bot = stats.get("pct_bot")
    msgs_prom = stats.get("msgs_cliente_prom")

    def fmt_segs(v) -> str:
        if v is None:
            return "—"
        v = float(v)
        if v < 60:
            return f"{v:.0f}s"
        return f"{v/60:.1f}min"

    def fmt_pct(v) -> str:
        return f"{float(v):.1f}%" if v is not None else "—"

    def fmt_num(v) -> str:
        return f"{float(v):.1f}" if v is not None else "—"

    escalamiento_pct = round(con_asesor / total * 100, 1) if total else 0

    # ── Conversión por día (refuerza el acumulado con la variación diaria) ──
    conversion_html = ""
    if conversion_diaria:
        filas_dia = ""
        for d in conversion_diaria:
            filas_dia += (
                f"<tr>"
                f"<td>{d['dia']}</td>"
                f"<td style='text-align:right'>{d['leads']}</td>"
                f"<td style='text-align:right'>{d['ventas']}</td>"
                f"<td style='text-align:right'>{d['pct_conv']:.1f}%</td>"
                f"</tr>"
            )
        conversion_html = f"""
    <h3 style="font-size:14px;margin:24px 0 10px;color:#333">Conversión por día (últimos {len(conversion_diaria)} días)</h3>
    <p style="font-size:11px;color:#999;margin:0 0 8px">Cohortes por día de creación del lead — los días más recientes aún pueden sumar ventas.</p>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr><th style="background:#f0f0f0;padding:7px 8px;text-align:left">Día</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">Leads</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">Ventas</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">% Conv.</th></tr></thead>
      <tbody>{filas_dia}</tbody>
    </table>
"""

    # ── Bloque de inversión (opcional) ──────────────────────────────────────
    inversion_html = ""
    if meta:
        total_spend    = meta.get("total_spend", 0) or 0
        total_leads_wa = meta.get("total_leads_meta", 0) or 0
        cpl_global     = round(total_spend / total_leads_wa, 2) if total_leads_wa else None
        cpa_meta       = round(total_spend / ganadas, 2) if ganadas else None
        ai_por_venta   = round(ai_cost_usd / ganadas, 4) if ganadas else None
        # % conversión sobre leads reales (tabla leads), no sobre la métrica de Meta
        # (total_leads_wa cuenta aperturas de chat que nunca llegan al webhook).
        conv_pct       = round(ganadas / total_leads_reales * 100, 1) if total_leads_reales else 0.0

        def _mxn(v) -> str:
            return f"${v:,.2f} MXN" if v is not None else "—"

        def _usd(v) -> str:
            return f"${v:.4f} USD" if v is not None else "—"

        def _pct2(v) -> str:
            return f"{v:.1f}%" if v is not None else "—"

        # Tabla de campañas
        filas_campana = ""
        for c in (campanas or []):
            cpl_s   = _mxn(c["cpl"])
            cpa_s   = _mxn(c["cpa"])
            conv_s  = _pct2(c["pct_conv"])
            filas_campana += (
                f"<tr>"
                f"<td>{c['name']}</td>"
                f"<td style='text-align:right'>${c['spend']:,.2f}</td>"
                f"<td style='text-align:right'>{c['leads']}</td>"
                f"<td style='text-align:right'>{cpl_s}</td>"
                f"<td style='text-align:right'>{c['ventas']}</td>"
                f"<td style='text-align:right'>{conv_s}</td>"
                f"<td style='text-align:right'>{cpa_s}</td>"
                f"</tr>"
            )

        inversion_html = f"""
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <h2 style="font-size:16px;margin:0 0 16px;color:#333">Inversión de campaña & ROI</h2>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px">
    <div style="background:#f8f8f8;border-radius:6px;padding:14px 16px">
      <div style="font-size:22px;font-weight:bold;color:#C8102E">{_mxn(total_spend)}</div>
      <div style="font-size:12px;color:#666;margin-top:2px">Inversión Meta Ads</div>
    </div>
    <div style="background:#f8f8f8;border-radius:6px;padding:14px 16px">
      <div style="font-size:22px;font-weight:bold;color:#C8102E">{_usd(ai_cost_usd)}</div>
      <div style="font-size:12px;color:#666;margin-top:2px">Costo IA (LLM)</div>
    </div>
    <div style="background:#f8f8f8;border-radius:6px;padding:14px 16px">
      <div style="font-size:22px;font-weight:bold;color:#C8102E">{_mxn(cpl_global)}</div>
      <div style="font-size:12px;color:#666;margin-top:2px">CPL (costo por lead)</div>
    </div>
    <div style="background:#f8f8f8;border-radius:6px;padding:14px 16px">
      <div style="font-size:22px;font-weight:bold;color:#C8102E">{_pct2(conv_pct)}</div>
      <div style="font-size:12px;color:#666;margin-top:2px">% Conversión lead → venta</div>
    </div>
  </div>

  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
    <tr><th style="background:#f0f0f0;padding:8px 10px;text-align:left">Indicador</th><th style="background:#f0f0f0;padding:8px 10px;text-align:right">Valor</th></tr>
    <tr><td style="padding:8px 10px;border-bottom:1px solid #eee">CPA Meta (inversión / ventas)</td><td style="padding:8px 10px;border-bottom:1px solid #eee;text-align:right">{_mxn(cpa_meta)}</td></tr>
    <tr><td style="padding:8px 10px;border-bottom:1px solid #eee">Costo IA por venta</td><td style="padding:8px 10px;border-bottom:1px solid #eee;text-align:right">{_usd(ai_por_venta)}</td></tr>
    <tr><td style="padding:8px 10px;border-bottom:1px solid #eee">Leads WhatsApp (Meta)</td><td style="padding:8px 10px;border-bottom:1px solid #eee;text-align:right">{total_leads_wa}</td></tr>
    <tr><td style="padding:8px 10px;border-bottom:1px solid #eee">Leads reales (tabla leads)</td><td style="padding:8px 10px;border-bottom:1px solid #eee;text-align:right">{total_leads_reales}</td></tr>
    <tr><td style="padding:8px 10px">Ventas cerradas</td><td style="padding:8px 10px;text-align:right">{ganadas}</td></tr>
  </table>

  {'<h3 style="font-size:14px;margin:0 0 10px;color:#333">Por campaña</h3><div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr><th style="background:#f0f0f0;padding:7px 8px;text-align:left">Campaña</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">Inversión</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">Leads</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">CPL</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">Ventas</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">% Conv.</th><th style="background:#f0f0f0;padding:7px 8px;text-align:right">CPA</th></tr></thead><tbody>' + filas_campana + '</tbody></table></div>' if filas_campana else ''}
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; color: #333; margin: 0; padding: 20px; background: #f5f5f5; }}
    .container {{ max-width: 640px; margin: 0 auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}
    .header {{ background: #C8102E; color: #fff; padding: 24px 28px; }}
    .header h1 {{ margin: 0; font-size: 20px; }}
    .header p {{ margin: 4px 0 0; font-size: 13px; opacity: .85; }}
    .body {{ padding: 24px 28px; }}
    .kpi-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }}
    .kpi-card {{ background: #f8f8f8; border-radius: 6px; padding: 14px 16px; }}
    .kpi-card .value {{ font-size: 26px; font-weight: bold; color: #C8102E; }}
    .kpi-card .label {{ font-size: 12px; color: #666; margin-top: 2px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background: #f0f0f0; padding: 8px 10px; text-align: left; font-weight: 600; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
    .footer {{ padding: 16px 28px; background: #f8f8f8; font-size: 11px; color: #999; }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Reporte Diario — Bot Vera Portabilidad</h1>
    <p>Muévete Prepago · Región 4 · {rango}</p>
  </div>
  <div class="body">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="value">{total}</div><div class="label">Conversaciones totales</div></div>
      <div class="kpi-card"><div class="value">{ganadas}</div><div class="label">Ventas (WON)</div></div>
      <div class="kpi-card"><div class="value">{fmt_segs(tpr)}</div><div class="label">Tiempo primera respuesta (prom)</div></div>
      <div class="kpi-card"><div class="value">{fmt_pct(pct_bot)}</div><div class="label">Tasa de automatización del bot</div></div>
    </div>

    <table>
      <tr><th>Indicador</th><th>Valor</th></tr>
      <tr><td>Conversaciones con asesor humano</td><td>{con_asesor} ({escalamiento_pct}%)</td></tr>
      <tr><td>Conversaciones perdidas (LOSE)</td><td>{perdidas}</td></tr>
      <tr><td>Tiempo promedio de cierre</td><td>{fmt_segs(cierre)}</td></tr>
      <tr><td>Mensajes promedio por cliente</td><td>{fmt_num(msgs_prom)}</td></tr>
    </table>

    {conversion_html}

    <p style="margin-top:20px; font-size:12px; color:#888;">
      El archivo CSV adjunto contiene el detalle completo de todas las conversaciones registradas.
    </p>
    {inversion_html}
  </div>
  <div class="footer">Generado automáticamente a las 00:00 (America/Monterrey). No responder este correo.</div>
</div>
</body>
</html>"""


def _send_smtp(subject: str, html: str, csv_bytes: bytes, fecha_archivo: str) -> None:
    """Envío sincrónico vía SMTP SSL — se ejecuta en un thread executor."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    recipients = [r.strip() for r in settings.report_email_to.split(",") if r.strip()]
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(html, "html", "utf-8"))

    if csv_bytes:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(csv_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=f"kpi_conversaciones_{fecha_archivo}.csv",
        )
        msg.attach(attachment)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as server:
        server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.smtp_user, recipients, msg.as_bytes())


async def send_kpi_report() -> None:
    """Genera el reporte y lo envía por correo. Se llama desde job_kpi_export()."""
    if not settings.smtp_user or not settings.smtp_pass or not settings.report_email_to:
        logger.warning("kpi_email_skipped_no_config")
        return

    try:
        from datetime import timedelta
        ahora = datetime.now(tz=TZ)
        ayer = ahora - timedelta(days=1)
        fecha = ayer.strftime("%d/%m/%Y")
        fecha_archivo = ayer.strftime("%Y%m%d")
        inicio_mes_str = ayer.replace(day=1).strftime("%d/%m/%Y")
        subject = f"Reporte KPI Vera Portabilidad — Cierre {inicio_mes_str} al {fecha}"

        inicio_mes, fin_ayer = _mes_actual_range()

        stats, csv_bytes, meta, ai_cost, utm_conv, conversion_diaria, total_leads_reales = await asyncio.gather(
            _get_daily_stats(),
            _build_csv(),
            _get_meta_data(inicio_mes, fin_ayer),
            _get_ai_cost(inicio_mes, fin_ayer),
            _get_utm_conversion(inicio_mes, fin_ayer),
            _get_conversion_by_day(),
            _get_leads_reales(inicio_mes, fin_ayer),
        )

        campanas = _merge_campaign_data(meta, utm_conv) if meta else []
        rango = f"{inicio_mes_str} al {fecha}"
        html = _build_html(
            stats, rango, meta=meta or None, ai_cost_usd=ai_cost, campanas=campanas,
            conversion_diaria=conversion_diaria, total_leads_reales=total_leads_reales,
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_smtp, subject, html, csv_bytes, fecha_archivo)

        logger.info(
            "kpi_email_sent",
            extra={
                "to": settings.report_email_to,
                "fecha": fecha,
                "meta_spend": meta.get("total_spend") if meta else None,
                "ai_cost_usd": round(ai_cost, 4),
            },
        )
    except Exception as exc:
        logger.error("kpi_email_error", extra={"error": str(exc)})

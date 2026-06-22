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


def _build_html(stats: dict, rango: str) -> str:
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

    <p style="margin-top:20px; font-size:12px; color:#888;">
      El archivo CSV adjunto contiene el detalle completo de todas las conversaciones registradas.
    </p>
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
        fecha = ayer.strftime("%d/%m/%Y")           # cierre del día anterior
        fecha_archivo = ayer.strftime("%Y%m%d")
        inicio_mes_str = ayer.replace(day=1).strftime("%d/%m/%Y")
        subject = f"Reporte KPI Vera Portabilidad — Cierre {inicio_mes_str} al {fecha}"

        stats, csv_bytes = await asyncio.gather(
            _get_daily_stats(),
            _build_csv(),
        )

        rango = f"{inicio_mes_str} al {fecha}"
        html = _build_html(stats, rango)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_smtp, subject, html, csv_bytes, fecha_archivo)

        logger.info("kpi_email_sent", extra={"to": settings.report_email_to, "fecha": fecha})
    except Exception as exc:
        logger.error("kpi_email_error", extra={"error": str(exc)})

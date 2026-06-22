"""Seguimientos automáticos de leads — APScheduler con zona horaria America/Monterrey.

Fuente de verdad: leads.bitrix_stage (sincronizado desde Bitrix por job_bitrix_sync).
Se envía seguimiento a todos los leads EXCEPTO los que están en C90:WON (venta cerrada).

Cadencias por stage de Bitrix (minutos):
  C90:NEW          30m · 2h · 23h
  C90:PROSPECTO    4h · 23h · 46h
  C90:SEGUIMIENTO  2h · 23h · 46h · 69h
  C90:UC_8WB2DT    4h · 23h · 46h
  C90:8            23h · 46h · 69h
  C90:LOSE         46h · 92h

Ventana: L–S 9:00–21:00 America/Monterrey. Sin domingos.
Límite: máximo 5 seguimientos por lead.
"""

import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from integrations.postgres import client as db
from integrations.telegram.client import TelegramClient
from integrations.whatsapp.client import WhatsAppClient

STAGE_RESCATE1 = "C90:1"
STAGE_RESCATE2 = "C90:2"
STAGE_RESCATE3 = "C90:3"
MIN_SILENCIO = 30        # minutos sin mensaje del usuario antes de enviar seguimiento
MIN_RESCATE2 = 60        # minutos en C90:1 antes de enviar Rescate 2
MIN_RESCATE3 = 120       # minutos en C90:2 antes de disparar llamada Vicidial

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Monterrey")
MAX_SEGUIMIENTOS = 5
VENTANA_INICIO = 9
VENTANA_FIN = 21

_CADENCIAS: dict[str, list[int]] = {
    "C90:NEW":        [30, 120, 1380],
    "C90:PROSPECTO":  [240, 1380, 2760],
    "C90:SEGUIMIENTO":[120, 1380, 2760, 4140],
    "C90:UC_8WB2DT":  [240, 1380, 2760],
    "C90:8":          [1380, 2760, 4140],
    "C90:LOSE":       [2760, 5520],
}
_CADENCIA_DEFAULT = [30, 120, 1380]

_MENSAJES: dict[str, list[str]] = {
    "C90:NEW": [
        "Hola, soy Vera de Telcel 😊 ¿Pudiste pensarlo? La promo de portabilidad sigue vigente.",
        "¿Te quedó alguna duda sobre los beneficios? Aquí estoy para ayudarte con tu portabilidad.",
        "Último recordatorio: la promo está disponible por tiempo limitado. ¿Te ayudo a avanzar? 🙌",
    ],
    "C90:PROSPECTO": [
        "Hola, soy Vera de Telcel 😊 Tienes un asesor asignado que te contactará pronto para coordinar tu portabilidad. ¿Necesitas algo mientras tanto?",
        "¿Ya te contactó tu asesor de Telcel? Si no ha sido así, dime y lo verificamos.",
        "Recuerda que tu promo sigue reservada. ¿Ya avanzaste con el asesor? 🙌",
    ],
    "C90:SEGUIMIENTO": [
        "Hola, soy Vera de Telcel 😊 Quedamos en contactarte más adelante. ¿Ya es buen momento para avanzar con tu portabilidad?",
        "La promo de portabilidad sigue vigente. ¿Hoy puedes avanzar? Solo toma unos minutos 🙌",
        "¿Sigues interesado en portarte a Telcel conservando tu número? La promo sigue disponible.",
        "Última vez que te escribo por ahora — cuando estés listo, aquí estaré 😊",
    ],
    "C90:UC_8WB2DT": [
        "Hola, soy Vera de Telcel 😊 Tienes un asesor asignado que te contactará en breve para seguir con tu portabilidad.",
        "¿Ya te marcó tu asesor de Telcel? Estamos pendientes de ti. Si necesitas algo, aquí estoy.",
        "Recuerda que tu solicitud de portabilidad sigue activa. Tu asesor te contactará pronto 🙌",
    ],
    "C90:8": [
        "Hola, soy Vera de Telcel 😊 ¿Sigues interesado en portarte conservando tu mismo número? La promo sigue disponible.",
        "¿Pudiste pensarlo? Con tu misma recarga tendrías mucho más con Telcel 🙌 ¿Te platico?",
        "Última vez que te escribo — si en algún momento quieres aprovechar la promo, aquí estaré.",
    ],
    "C90:LOSE": [
        "Hola, soy Vera de Telcel 😊 Sé que antes no pudimos avanzar, pero la promo de portabilidad sigue vigente. ¿Hay algo en lo que pueda ayudarte?",
        "Última oportunidad: la promo de portabilidad sigue disponible. Si cambias de opinión, aquí estoy 🙌",
    ],
    # Mensaje Rescate 2 — se envía a leads que ya están en C90:1
    "C90:1": [
        "Hola, soy Vera de Telcel 😊 Solo quería asegurarme de que no te quedaste con ninguna duda sobre tu portabilidad. La promo sigue vigente — ¿te ayudo a avanzar?",
    ],
}

_tg = TelegramClient()
_wa = WhatsAppClient()


def _en_ventana(ahora: datetime) -> bool:
    local = ahora.astimezone(TZ)
    if local.weekday() == 6:
        return False
    return VENTANA_INICIO <= local.hour < VENTANA_FIN


def _cadencia(bitrix_stage: str) -> list[int]:
    return _CADENCIAS.get(bitrix_stage, _CADENCIA_DEFAULT)


def _siguiente_envio(ultimo: datetime, cadencia: list[int], num_enviados: int) -> datetime | None:
    if num_enviados >= len(cadencia) or num_enviados >= MAX_SEGUIMIENTOS:
        return None
    return ultimo + timedelta(minutes=cadencia[num_enviados])


def _mensaje(bitrix_stage: str, numero_seq: int) -> str:
    lista = _MENSAJES.get(bitrix_stage, _MENSAJES["C90:NEW"])
    return lista[min(numero_seq, len(lista) - 1)]


async def minutos_desde_ultimo_mensaje(phone: str) -> float | None:
    """Retorna los minutos transcurridos desde el último checkpoint del usuario.

    Usa la tabla checkpoints de LangGraph con thread_id = phone.
    Retorna None si no hay checkpoints (lead sin conversación previa).
    """
    row = await db.fetchrow(
        "SELECT MAX((checkpoint->>'ts')::timestamptz) AS ts FROM checkpoints WHERE thread_id = $1",
        phone,
    )
    if not row or not row["ts"]:
        return None
    ahora = datetime.now(tz=TZ)
    delta = ahora - row["ts"].astimezone(TZ)
    return delta.total_seconds() / 60


async def _mover_a_rescate1(lead_id: int, deal_id: str) -> None:
    """Mueve el deal a Rescate 1 (C90:1) en Bitrix y actualiza leads.bitrix_stage."""
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        await bx.mover_etapa(deal_id, STAGE_RESCATE1)
        await db.execute(
            "UPDATE leads SET bitrix_stage = $1, updated_at = NOW() WHERE id = $2",
            STAGE_RESCATE1, lead_id,
        )
        logger.info("bitrix_rescate1_actualizado", extra={"lead_id": lead_id, "deal_id": deal_id})
    except Exception as exc:
        logger.warning("bitrix_rescate1_error", extra={"lead_id": lead_id, "error": str(exc)})


async def _mover_a_rescate2(lead_id: int, deal_id: str) -> None:
    """Mueve el deal a Rescate 2 (C90:2) en Bitrix y actualiza leads.bitrix_stage."""
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        await bx.mover_etapa(deal_id, STAGE_RESCATE2)
        await db.execute(
            "UPDATE leads SET bitrix_stage = $1, updated_at = NOW() WHERE id = $2",
            STAGE_RESCATE2, lead_id,
        )
        logger.info("bitrix_rescate2_actualizado", extra={"lead_id": lead_id, "deal_id": deal_id})
    except Exception as exc:
        logger.warning("bitrix_rescate2_error", extra={"lead_id": lead_id, "error": str(exc)})


async def _mover_a_rescate3(lead_id: int, deal_id: str) -> None:
    """Mueve el deal a Rescate 3 (C90:3) en Bitrix y actualiza leads.bitrix_stage."""
    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()
        await bx.mover_etapa(deal_id, STAGE_RESCATE3)
        await db.execute(
            "UPDATE leads SET bitrix_stage = $1, updated_at = NOW() WHERE id = $2",
            STAGE_RESCATE3, lead_id,
        )
        logger.info("bitrix_rescate3_actualizado", extra={"lead_id": lead_id, "deal_id": deal_id})
    except Exception as exc:
        logger.warning("bitrix_rescate3_error", extra={"lead_id": lead_id, "error": str(exc)})


async def _procesar_rescate3(row: dict) -> None:
    """Dispara llamada Vicidial a leads en C90:2 con 60+ min desde el Rescate 2.

    El timer corre desde que se envió el Rescate 2 (entrada a C90:2), no desde el último mensaje.
    """
    lead_id = row["id"]
    phone = row["telefono"]
    deal_id = row.get("bitrix_lead_id") or ""
    ultimo_seguimiento = row.get("ultimo_seguimiento")

    ahora = datetime.now(tz=TZ)
    if not _en_ventana(ahora):
        return

    # Timer: 60 min desde que entró a C90:2 (cuando se envió Rescate 2).
    # Fallback a updated_at si ultimo_seguimiento es NULL (stage llegó vía sync de Bitrix).
    referencia = ultimo_seguimiento or row.get("updated_at")
    if not referencia:
        return
    mins_desde_rescate2 = (ahora - referencia.astimezone(TZ)).total_seconds() / 60
    if mins_desde_rescate2 < MIN_RESCATE3:
        logger.info("rescate3_skip_espera", extra={"lead_id": lead_id, "mins_desde_rescate2": round(mins_desde_rescate2, 1)})
        return

    ya_enviado = await db.fetchval(
        "SELECT COUNT(*) FROM seguimientos_log WHERE lead_id = $1 AND etapa = $2 AND enviado_at > NOW() - INTERVAL '4 minutes'",
        lead_id, STAGE_RESCATE3,
    )
    if ya_enviado:
        return

    from integrations.vicidial.client import agregar_lead
    exito, respuesta = await agregar_lead(phone)

    if exito and deal_id:
        await _mover_a_rescate3(lead_id, deal_id)

    await db.execute(
        "INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at) VALUES ($1, $2, 1, NOW())",
        lead_id, STAGE_RESCATE3,
    )
    await db.execute(
        "UPDATE leads SET seguimientos_enviados = seguimientos_enviados + 1, ultimo_seguimiento = NOW(), updated_at = NOW() WHERE id = $1",
        lead_id,
    )

    if not exito:
        logger.error("rescate3_vicidial_fallido", extra={"lead_id": lead_id, "respuesta": respuesta})


async def _get_historial(phone: str) -> str:
    """Extrae el historial de conversación desde LangGraph checkpoints.

    Retorna un transcript 'Cliente: ...\nVera: ...' listo para inyectar en el prompt.
    Limita a los últimos 20 mensajes para no exceder el contexto.
    """
    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from agents.portabilidad.graph import get_agent_graph

        snapshot = await get_agent_graph().aget_state(
            {"configurable": {"thread_id": phone}}
        )
        if not snapshot or not snapshot.values:
            return ""

        messages = snapshot.values.get("messages") or []
        lineas: list[str] = []
        for m in messages[-20:]:
            content = str(m.content).strip()
            if not content:
                continue
            if isinstance(m, HumanMessage):
                lineas.append(f"Cliente: {content}")
            elif isinstance(m, AIMessage):
                lineas.append(f"Vera: {content}")
        return "\n".join(lineas)
    except Exception as exc:
        logger.warning("historial_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return ""


async def _generar_mensaje_rescate(lead: dict, rescate: int) -> str:
    """Genera un mensaje de seguimiento personalizado con LLM basado en el historial real.

    Lee la conversación desde LangGraph checkpoints; fallback a template estático.
    """
    from agents.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    phone = lead.get("telefono", "")
    historial = await _get_historial(phone)

    if historial:
        contexto = f"Historial de la conversación:\n{historial}"
    else:
        contexto = "No hay historial disponible — el cliente no llegó a iniciar conversación."

    urgencia = (
        "Es el primer recordatorio — tono cálido y cercano, sin presionar."
        if rescate == 1
        else "Es el segundo recordatorio — muestra un poco más de urgencia sin ser agresivo."
    )

    system = (
        "Eres Vera, asesora de ventas de Telcel Región 4. "
        "Escribe un mensaje de seguimiento de WhatsApp para recuperar a este lead de portabilidad. "
        f"{urgencia} "
        "Reglas: máximo 2 oraciones, sin markdown, máximo 1 emoji, "
        "usa el nombre del cliente si aparece en el historial, "
        "haz referencia natural a lo que se habló (promo, recarga, objeción) si hay historial, "
        "no menciones que es un recordatorio automático ni que el lead no respondió. "
        f"\n\n{contexto}"
    )

    try:
        llm = get_llm()
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="Genera el mensaje."),
        ])
        texto = resp.content.strip()
        logger.info("llm_mensaje_generado", extra={"lead_id": lead.get("id"), "rescate": rescate, "con_historial": bool(historial)})
        return texto
    except Exception as exc:
        logger.warning("llm_mensaje_fallback", extra={"lead_id": lead.get("id"), "error": str(exc)})
        return _mensaje(lead.get("bitrix_stage", "C90:NEW"), lead.get("seguimientos_enviados", 0))


async def _enviar_seguimiento(lead_id: int, phone: str, texto: str, bitrix_stage: str = "", numero_seq: int = 0) -> None:
    if not texto:
        texto = _mensaje(bitrix_stage, numero_seq)
    if phone.startswith("tg_"):
        chat_id = phone.replace("tg_", "")
        await _tg.send_message(chat_id, texto)
        logger.info("seguimiento_enviado_telegram", extra={"lead_id": lead_id, "seq": numero_seq, "stage": bitrix_stage})
    else:
        await _wa.send_message(phone, texto)
        logger.info("seguimiento_enviado_whatsapp", extra={"lead_id": lead_id, "seq": numero_seq, "stage": bitrix_stage})
        # Espeja el mensaje en el chat de Open Lines para que el asesor vea el rescate
        try:
            from integrations.bitrix.connector import send_bot_message
            await send_bot_message(phone, texto)
        except Exception as exc:
            logger.warning("seguimiento_bitrix_mirror_error", extra={"lead_id": lead_id, "error": str(exc)})


async def _procesar_lead(row: dict) -> None:
    """Envía Rescate 1 si el usuario lleva 30+ min sin responder.

    Aplica a cualquier stage excepto C90:WON, C90:1, C90:2, C90:3 (filtrados en SQL).
    No usa cadencias por stage — la única condición de tiempo es 30 min de silencio.
    """
    lead_id = row["id"]
    phone = row["telefono"]
    bitrix_stage = row["bitrix_stage"] or ""
    deal_id = row.get("bitrix_lead_id") or ""
    num_enviados = row["seguimientos_enviados"] or 0

    if num_enviados >= MAX_SEGUIMIENTOS:
        logger.info("seguimiento_skip_max", extra={"lead_id": lead_id, "enviados": num_enviados})
        return

    ahora = datetime.now(tz=TZ)
    if not _en_ventana(ahora):
        return

    # Única condición de tiempo: 30+ min sin mensaje del usuario
    minutos = await minutos_desde_ultimo_mensaje(phone)
    if minutos is not None and minutos < MIN_SILENCIO:
        logger.info("seguimiento_skip_reciente", extra={"lead_id": lead_id, "minutos": round(minutos, 1)})
        return

    ya_enviado = await db.fetchval(
        "SELECT COUNT(*) FROM seguimientos_log WHERE lead_id = $1 AND enviado_at > NOW() - INTERVAL '4 minutes'",
        lead_id,
    )
    if ya_enviado:
        logger.info("seguimiento_skip_idempotencia", extra={"lead_id": lead_id})
        return

    try:
        texto = await _generar_mensaje_rescate(row, rescate=1)
        await _enviar_seguimiento(lead_id, phone, texto, bitrix_stage, num_enviados)

        # Primer seguimiento → mover deal a Rescate 1 en Bitrix
        if num_enviados == 0 and deal_id:
            await _mover_a_rescate1(lead_id, deal_id)

        await db.execute(
            """
            INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at)
            VALUES ($1, $2, $3, NOW())
            """,
            lead_id, bitrix_stage, num_enviados + 1,
        )
        await db.execute(
            """
            UPDATE leads
            SET seguimientos_enviados = seguimientos_enviados + 1,
                ultimo_seguimiento = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            lead_id,
        )

    except Exception as exc:
        logger.error("seguimiento_fallido", extra={"lead_id": lead_id, "error": str(exc)})
        await db.execute(
            """
            INSERT INTO seguimientos_fallidos (lead_id, error, intentos, ultimo_intento)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (lead_id) DO UPDATE
              SET intentos = seguimientos_fallidos.intentos + 1,
                  error = EXCLUDED.error,
                  ultimo_intento = NOW(),
                  requiere_revision = (seguimientos_fallidos.intentos + 1 >= 3)
            """,
            lead_id, str(exc),
        )


async def _procesar_rescate2(row: dict) -> None:
    """Envía el mensaje de Rescate 2 a un lead en C90:1 si han pasado 60 min desde el Rescate 1.

    El timer corre desde que se envió el Rescate 1 (entrada a C90:1), no desde el último mensaje.
    """
    lead_id = row["id"]
    phone = row["telefono"]
    deal_id = row.get("bitrix_lead_id") or ""
    ultimo_seguimiento = row.get("ultimo_seguimiento")

    ahora = datetime.now(tz=TZ)
    if not _en_ventana(ahora):
        return

    # Timer: 60 min desde que entró a C90:1 (cuando se envió Rescate 1).
    # Si ultimo_seguimiento es NULL (stage llegó vía sync de Bitrix sin pasar por el job),
    # usar updated_at como referencia para no bloquear el rescate indefinidamente.
    referencia = ultimo_seguimiento or row.get("updated_at")
    if not referencia:
        return
    mins_desde_rescate1 = (ahora - referencia.astimezone(TZ)).total_seconds() / 60
    if mins_desde_rescate1 < MIN_RESCATE2:
        logger.info("rescate2_skip_espera", extra={"lead_id": lead_id, "mins_desde_rescate1": round(mins_desde_rescate1, 1)})
        return

    ya_enviado = await db.fetchval(
        "SELECT COUNT(*) FROM seguimientos_log WHERE lead_id = $1 AND enviado_at > NOW() - INTERVAL '4 minutes'",
        lead_id,
    )
    if ya_enviado:
        return

    try:
        texto = await _generar_mensaje_rescate(row, rescate=2)
        await _enviar_seguimiento(lead_id, phone, texto, STAGE_RESCATE1, 0)

        if deal_id:
            await _mover_a_rescate2(lead_id, deal_id)

        await db.execute(
            "INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at) VALUES ($1, $2, 1, NOW())",
            lead_id, STAGE_RESCATE2,
        )
        await db.execute(
            "UPDATE leads SET seguimientos_enviados = seguimientos_enviados + 1, ultimo_seguimiento = NOW(), updated_at = NOW() WHERE id = $1",
            lead_id,
        )

    except Exception as exc:
        logger.error("rescate2_fallido", extra={"lead_id": lead_id, "error": str(exc)})
        await db.execute(
            """
            INSERT INTO seguimientos_fallidos (lead_id, error, intentos, ultimo_intento)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (lead_id) DO UPDATE
              SET intentos = seguimientos_fallidos.intentos + 1,
                  error = EXCLUDED.error,
                  ultimo_intento = NOW(),
                  requiere_revision = (seguimientos_fallidos.intentos + 1 >= 3)
            """,
            lead_id, str(exc),
        )


async def job_seguimientos() -> None:
    inicio = datetime.now(tz=TZ)
    logger.info("job_seguimientos_start", extra={"hora": inicio.isoformat()})

    if not _en_ventana(inicio):
        logger.info("job_seguimientos_fuera_ventana")
        return

    test_phone = settings.seguimientos_test_phone.strip()
    # $1 en todas las queries cuando hay test_phone (único parámetro)
    filtro_sql = "AND telefono = $1" if test_phone else ""

    # ── Rescate 1: leads fuera de WON y stages de rescate ────────────────────
    try:
        query_r1 = f"""
            SELECT id, telefono, bitrix_stage, bitrix_lead_id,
                   COALESCE(seguimientos_enviados, 0) AS seguimientos_enviados,
                   ultimo_seguimiento, created_at,
                   nombre, compania_donante, recarga_habitual, promo_elegida, temperatura, municipio
            FROM leads
            WHERE bitrix_stage NOT IN ('C90:WON', 'C90:1', 'C90:2', 'C90:3')
              AND bitrix_stage != ''
              AND updated_at > NOW() - INTERVAL '30 days'
              {filtro_sql}
            ORDER BY updated_at DESC
            LIMIT 200
            """
        leads_r1 = await db.fetch(query_r1, *([test_phone] if test_phone else []))
    except Exception as exc:
        logger.error("job_seguimientos_db_error", extra={"error": str(exc)})
        return

    procesados = 0
    errores = 0
    for row in leads_r1:
        try:
            await _procesar_lead(dict(row))
            procesados += 1
        except Exception as exc:
            errores += 1
            logger.error("job_lead_error", extra={"lead_id": row["id"], "error": str(exc)})

    # ── Rescate 2: leads en C90:1 con 60+ min desde el primer rescate ────────
    try:
        query_r2 = f"""
            SELECT id, telefono, bitrix_lead_id, ultimo_seguimiento, updated_at,
                   nombre, compania_donante, recarga_habitual, promo_elegida, temperatura, municipio
            FROM leads
            WHERE bitrix_stage = 'C90:1'
              AND updated_at > NOW() - INTERVAL '30 days'
              {filtro_sql}
            ORDER BY updated_at DESC
            LIMIT 200
            """
        leads_r2 = await db.fetch(query_r2, *([test_phone] if test_phone else []))
    except Exception as exc:
        logger.error("job_rescate2_db_error", extra={"error": str(exc)})
        leads_r2 = []

    for row in leads_r2:
        try:
            await _procesar_rescate2(dict(row))
            procesados += 1
        except Exception as exc:
            errores += 1
            logger.error("job_rescate2_error", extra={"lead_id": row["id"], "error": str(exc)})

    # ── Rescate 3: leads en C90:2 con 60+ min → llamada Vicidial ─────────────
    try:
        query_r3 = f"""
            SELECT id, telefono, bitrix_lead_id, ultimo_seguimiento, updated_at
            FROM leads
            WHERE bitrix_stage = 'C90:2'
              AND updated_at > NOW() - INTERVAL '30 days'
              {filtro_sql}
            ORDER BY updated_at DESC
            LIMIT 200
            """
        leads_r3 = await db.fetch(query_r3, *([test_phone] if test_phone else []))
    except Exception as exc:
        logger.error("job_rescate3_db_error", extra={"error": str(exc)})
        leads_r3 = []

    for row in leads_r3:
        try:
            await _procesar_rescate3(dict(row))
            procesados += 1
        except Exception as exc:
            errores += 1
            logger.error("job_rescate3_error", extra={"lead_id": row["id"], "error": str(exc)})

    duracion_ms = round((datetime.now(tz=TZ) - inicio).total_seconds() * 1000)
    logger.info(
        "job_seguimientos_done",
        extra={"procesados": procesados, "errores": errores, "duracion_ms": duracion_ms},
    )
    if not leads_r1 and not leads_r2 and not leads_r3:
        logger.info("job_seguimientos_sin_leads")


def create_scheduler() -> AsyncIOScheduler:
    from jobs.bitrix_sync import job_bitrix_sync
    from jobs.kpi_export import job_kpi_export
    from jobs.email_report import send_kpi_report

    scheduler = AsyncIOScheduler(timezone=TZ)
    # Modo test: SEGUIMIENTOS_TEST_PHONE en .env limita el job a un solo teléfono.
    # Para producción general: dejar SEGUIMIENTOS_TEST_PHONE vacío.
    scheduler.add_job(
        job_seguimientos,
        trigger="interval",
        minutes=5,
        id="seguimientos",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_bitrix_sync,
        trigger="interval",
        minutes=30,
        id="bitrix_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    # Extracción nocturna de KPIs a las 3am
    scheduler.add_job(
        job_kpi_export,
        trigger="cron",
        hour=3,
        minute=0,
        timezone=TZ,
        id="kpi_export",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    # Reporte diario por correo a las 00:01 — cierre del día anterior (1° al día-1 del mes)
    scheduler.add_job(
        send_kpi_report,
        trigger="cron",
        hour=0,
        minute=1,
        timezone=TZ,
        id="kpi_email_report",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler

"""Seguimientos automáticos de leads — APScheduler con zona horaria America/Monterrey.

Cadencias por etapa:
  - No respondió / en sondeo / recibió oferta / intención alta:  5m · 30m · 2h · antes de 24h
  - "Lo voy a pensar":                                            30m · 2h · antes de 24h · día 2
Límite: máximo 5 seguimientos por lead.
Ventana permitida: L-S 9:00–21:00 America/Monterrey. Sin domingos.
"""

import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from integrations.postgres import client as db
from integrations.telegram.client import TelegramClient

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Monterrey")
MAX_SEGUIMIENTOS = 5
VENTANA_INICIO = 9   # hora local
VENTANA_FIN = 21     # hora local (exclusivo)

# Cadencias en minutos por tipo de etapa
_CADENCIAS: dict[str, list[int]] = {
    "default":   [5, 30, 120, 1380],   # 5m · 30m · 2h · 23h
    "tibio":     [30, 120, 1380, 2880], # 30m · 2h · 23h · 48h
}

_tg = TelegramClient()


def _en_ventana(ahora: datetime) -> bool:
    """Verifica que la hora local esté en la ventana permitida y no sea domingo."""
    local = ahora.astimezone(TZ)
    if local.weekday() == 6:  # domingo
        return False
    return VENTANA_INICIO <= local.hour < VENTANA_FIN


def _cadencia(etapa: str, temperatura: str) -> list[int]:
    if temperatura == "tibio" and etapa in ("oferta", "objecion"):
        return _CADENCIAS["tibio"]
    return _CADENCIAS["default"]


def _siguiente_envio(ultimo: datetime, cadencia: list[int], num_enviados: int) -> datetime | None:
    """Calcula la próxima ventana de envío. Retorna None si ya se agotó la cadencia."""
    if num_enviados >= len(cadencia) or num_enviados >= MAX_SEGUIMIENTOS:
        return None
    delta = timedelta(minutes=cadencia[num_enviados])
    return ultimo + delta


async def _enviar_seguimiento(lead_id: int, phone: str, etapa: str, numero_seq: int) -> None:
    """Genera y envía el mensaje de seguimiento adecuado para la etapa."""
    mensajes: dict[str, list[str]] = {
        "sondeo": [
            "Hola, soy Alejandro de Telcel. ¿Pudiste pensarlo? Tenemos promos vigentes para tu zona.",
            "¿Te quedó alguna duda sobre la portabilidad? Aquí estoy para ayudarte.",
            "Último recordatorio: las promos de portabilidad están disponibles por tiempo limitado. ¿Te platico?",
            "Solo para avisarte que aún puedes aprovechar la promo. ¿Te ayudo a avanzar?",
        ],
        "oferta": [
            "¡Hola! ¿Pudiste pensar la promo que te compartí? Sigue vigente.",
            "¿Te quedó alguna duda sobre los beneficios? Con gusto los repaso contigo.",
            "La promo tiene fecha límite. ¿Seguimos con el proceso?",
            "¿Te ayudo a resolver cualquier duda antes de que expire la oferta?",
        ],
        "objecion": [
            "Hola, ¿ya tuviste oportunidad de pensarlo? La promo sigue disponible.",
            "Si te quedó alguna duda sobre el costo o los beneficios, con gusto te aclaro.",
            "Recuerda: la portabilidad no tiene costo y tu número no cambia. ¿Seguimos?",
            "Última vez que te escribo por esta promo — si te interesa aún está vigente.",
        ],
        "default": [
            "Hola, soy Alejandro de Telcel. ¿Puedo ayudarte con tu portabilidad?",
            "¿Tuviste oportunidad de revisar la promo que te mandé?",
            "La promoción de portabilidad sigue vigente. ¿Te ayudo a avanzar?",
            "¿Tienes alguna duda sobre el proceso? Aquí estoy.",
        ],
    }

    lista = mensajes.get(etapa, mensajes["default"])
    texto = lista[min(numero_seq, len(lista) - 1)]

    # Intentar enviar por Telegram si el phone empieza con tg_
    if phone.startswith("tg_"):
        chat_id = phone.replace("tg_", "")
        try:
            await _tg.send_message(chat_id, texto)
            logger.info("seguimiento_enviado_telegram", extra={"lead_id": lead_id, "seq": numero_seq})
        except Exception as exc:
            logger.error("seguimiento_telegram_error", extra={"lead_id": lead_id, "error": str(exc)})
            raise
    else:
        # WhatsApp — registrar para envío por worker (implementación Día 3 WhatsApp)
        logger.info("seguimiento_queued_whatsapp", extra={"lead_id": lead_id, "seq": numero_seq})


async def _procesar_lead(row: dict) -> None:
    lead_id = row["id"]
    phone = row["telefono"]
    etapa = row["etapa"]
    temperatura = row["temperatura"] or "frio"
    num_enviados = row["seguimientos_enviados"] or 0
    ultimo_raw = row["ultimo_seguimiento"] or row["created_at"]

    ahora = datetime.now(tz=TZ)

    if not _en_ventana(ahora):
        return

    cadencia = _cadencia(etapa, temperatura)
    proximo = _siguiente_envio(ultimo_raw, cadencia, num_enviados)

    if proximo is None or ahora < proximo.astimezone(TZ):
        return

    # Idempotencia: verificar que no se envió ya en los últimos 4 minutos
    ya_enviado = await db.fetchval(
        "SELECT COUNT(*) FROM seguimientos_log WHERE lead_id = $1 AND enviado_at > NOW() - INTERVAL '4 minutes'",
        lead_id,
    )
    if ya_enviado:
        logger.info("seguimiento_skip_idempotencia", extra={"lead_id": lead_id})
        return

    try:
        await _enviar_seguimiento(lead_id, phone, etapa, num_enviados)

        # Registrar en log
        await db.execute(
            """
            INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at)
            VALUES ($1, $2, $3, NOW())
            """,
            lead_id, etapa, num_enviados + 1,
        )

        # Actualizar contador en lead
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


async def job_seguimientos() -> None:
    """Job principal: procesa todos los leads activos que necesitan seguimiento."""
    inicio = datetime.now(tz=TZ)
    logger.info("job_seguimientos_start", extra={"hora": inicio.isoformat()})

    if not _en_ventana(inicio):
        logger.info("job_seguimientos_fuera_ventana")
        return

    try:
        leads = await db.fetch(
            """
            SELECT id, telefono, etapa, temperatura,
                   COALESCE(seguimientos_enviados, 0) AS seguimientos_enviados,
                   ultimo_seguimiento, created_at
            FROM leads
            WHERE etapa NOT IN ('escalado', 'fin')
              AND COALESCE(seguimientos_enviados, 0) < $1
              AND updated_at > NOW() - INTERVAL '3 days'
            ORDER BY updated_at DESC
            LIMIT 200
            """,
            MAX_SEGUIMIENTOS,
        )
    except Exception as exc:
        logger.error("job_seguimientos_db_error", extra={"error": str(exc)})
        return

    procesados = 0
    errores = 0
    for row in leads:
        try:
            await _procesar_lead(dict(row))
            procesados += 1
        except Exception as exc:
            errores += 1
            logger.error("job_lead_error", extra={"lead_id": row["id"], "error": str(exc)})

    duracion_ms = round((datetime.now(tz=TZ) - inicio).total_seconds() * 1000)
    logger.info(
        "job_seguimientos_done",
        extra={"procesados": procesados, "errores": errores, "duracion_ms": duracion_ms},
    )
    if procesados == 0 and not leads:
        logger.warning("job_seguimientos_sin_leads")


def create_scheduler() -> AsyncIOScheduler:
    """Crea y configura el scheduler de seguimientos."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        job_seguimientos,
        trigger="interval",
        minutes=5,
        id="seguimientos",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    return scheduler

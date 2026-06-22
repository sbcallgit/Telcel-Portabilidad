"""Sincroniza el STAGE_ID de Bitrix24 hacia leads.bitrix_stage.

Corre cada 30 minutos vía APScheduler.
Lee todos los leads con bitrix_lead_id, consulta crm.deal.get en paralelo
(concurrencia máx 5) y actualiza bitrix_stage en la BD local.
"""

import asyncio
import logging
from datetime import datetime

import pytz

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Monterrey")
_CONCURRENCIA = 5


async def _sync_deal(bx, lead_id: int, deal_id: str, semaphore: asyncio.Semaphore) -> tuple[int, str]:
    async with semaphore:
        try:
            deal = await bx.get_deal(deal_id)
            stage = deal.get("STAGE_ID", "")
            return lead_id, stage
        except Exception as exc:
            logger.warning("bitrix_sync_deal_error", extra={"lead_id": lead_id, "deal_id": deal_id, "error": str(exc)})
            return lead_id, ""


async def _fire_capi_if_needed(lead_id: int, stage_nuevo: str, stage_anterior: str) -> None:
    """Dispara evento CAPI a Meta cuando el stage cambia a WON o PROSPECTO por primera vez."""
    if stage_nuevo == stage_anterior:
        return
    if stage_nuevo not in ("C90:WON", "C90:PROSPECTO"):
        return

    try:
        row = await db.fetchrow(
            "SELECT telefono, bitrix_lead_id, recarga_habitual, ctwa_clid, nombre, municipio FROM leads WHERE id = $1",
            lead_id,
        )
        if not row:
            return

        from integrations.meta.conversions import send_purchase_event, send_lead_event

        if stage_nuevo == "C90:WON":
            await send_purchase_event(
                phone=row["telefono"],
                deal_id=row["bitrix_lead_id"],
                recarga=float(row["recarga_habitual"] or 0),
                ctwa_clid=row["ctwa_clid"] or "",
                nombre=row["nombre"] or "",
                municipio=row["municipio"] or "",
            )
        elif stage_nuevo == "C90:PROSPECTO":
            await send_lead_event(
                phone=row["telefono"],
                deal_id=row["bitrix_lead_id"],
                ctwa_clid=row["ctwa_clid"] or "",
                nombre=row["nombre"] or "",
                municipio=row["municipio"] or "",
            )
    except Exception as exc:
        logger.warning("capi_dispatch_error", extra={"lead_id": lead_id, "error": str(exc)})


async def job_bitrix_sync() -> None:
    """Actualiza leads.bitrix_stage con el stage real de Bitrix para todos los leads activos."""
    inicio = datetime.now(tz=TZ)
    logger.info("job_bitrix_sync_start", extra={"hora": inicio.isoformat()})

    try:
        rows = await db.fetch(
            """
            SELECT id, bitrix_lead_id, bitrix_stage
            FROM leads
            WHERE bitrix_lead_id != ''
            ORDER BY updated_at DESC
            LIMIT 1000
            """
        )
    except Exception as exc:
        logger.error("job_bitrix_sync_db_error", extra={"error": str(exc)})
        return

    if not rows:
        logger.info("job_bitrix_sync_sin_leads")
        return

    from integrations.bitrix.client import BitrixClient
    bx = BitrixClient()
    semaphore = asyncio.Semaphore(_CONCURRENCIA)

    tareas = [_sync_deal(bx, row["id"], row["bitrix_lead_id"], semaphore) for row in rows]
    resultados = await asyncio.gather(*tareas)

    # Mapa de stage anterior para detectar transiciones a WON/PROSPECTO
    stage_anterior_map = {row["id"]: row.get("bitrix_stage", "") for row in rows}

    actualizados = 0
    errores = 0
    capi_tasks = []
    for lead_id, stage in resultados:
        if not stage:
            errores += 1
            continue
        try:
            await db.execute(
                "UPDATE leads SET bitrix_stage = $1, updated_at = NOW() WHERE id = $2 AND bitrix_stage != $1",
                stage, lead_id,
            )
            actualizados += 1
            # Disparar CAPI en background si el stage cambió a WON o PROSPECTO
            stage_prev = stage_anterior_map.get(lead_id, "")
            if stage != stage_prev and stage in ("C90:WON", "C90:PROSPECTO"):
                capi_tasks.append(_fire_capi_if_needed(lead_id, stage, stage_prev))
        except Exception as exc:
            errores += 1
            logger.warning("bitrix_sync_update_error", extra={"lead_id": lead_id, "error": str(exc)})

    if capi_tasks:
        await asyncio.gather(*capi_tasks, return_exceptions=True)

    duracion_s = round((datetime.now(tz=TZ) - inicio).total_seconds(), 1)
    logger.info(
        "job_bitrix_sync_done",
        extra={"total": len(rows), "actualizados": actualizados, "errores": errores, "duracion_s": duracion_s},
    )

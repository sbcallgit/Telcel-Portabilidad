"""Endpoints de administración — requieren X-Admin-Token."""

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from config.settings import settings

router = APIRouter(prefix="/admin")
logger = logging.getLogger(__name__)


def _check_token(x_admin_token: str) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="forbidden")


@router.post("/kpi-export")
async def trigger_kpi_export(x_admin_token: str = Header(...)) -> JSONResponse:
    """Dispara el job de exportación de KPIs de forma inmediata.

    Corre en el mismo proceso FastAPI, con el checkpointer PostgreSQL y tokens
    OAuth ya activos. Útil para regenerar la tabla sin esperar las 3am.
    """
    _check_token(x_admin_token)

    from jobs.kpi_export import job_kpi_export

    logger.info("admin_kpi_export_triggered")
    asyncio.create_task(job_kpi_export())

    return JSONResponse({"status": "started", "message": "KPI export corriendo en background — revisa logs para progreso"})

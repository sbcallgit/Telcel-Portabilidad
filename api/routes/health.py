import logging
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.settings import settings
from integrations.postgres import client as db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> JSONResponse:
    db_ok = await _check_db()
    status = "ok" if db_ok else "degraded"
    code = 200 if db_ok else 503

    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "version": settings.app_version,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {"database": "ok" if db_ok else "error"},
        },
    )


async def _check_db() -> bool:
    # Usa el pool existente en vez de abrir una conexión nueva por request.
    try:
        return await db.fetchval("SELECT 1") == 1
    except Exception as exc:
        logger.warning("health_check_db_failed", extra={"error": str(exc)})
        return False

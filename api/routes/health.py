import logging
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.settings import settings

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {"database": "ok" if db_ok else "error"},
        },
    )


async def _check_db() -> bool:
    try:
        conn = await asyncpg.connect(settings.database_dsn, timeout=3)
        await conn.fetchval("SELECT 1")
        await conn.close()
        return True
    except Exception as exc:
        logger.warning("health_check_db_failed", extra={"error": str(exc)})
        return False

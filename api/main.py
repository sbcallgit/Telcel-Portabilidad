import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.routes.admin import router as admin_router
from api.routes.bitrix import router as bitrix_router
from api.routes.bitrix_bot_control import router as bitrix_bot_control_router
from api.routes.connector import router as connector_router
from api.routes.health import router as health_router
from api.routes.telegram import router as telegram_router
from api.routes.webhooks import router as webhooks_router
from config.logging import setup_logging
from config.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("app_startup", extra={"version": settings.app_version, "env": settings.environment})
    from integrations.postgres.client import close_pool, create_pool
    from integrations.redis_client import close_redis, get_redis
    from jobs.connector_poll import start_connector_poll, stop_connector_poll
    from jobs.seguimientos import create_scheduler
    from agents.portabilidad.graph import setup_graph

    await create_pool()
    await get_redis()

    # Checkpointer persistente en PostgreSQL (reemplaza MemorySaver en memoria)
    _pg_pool = None
    try:
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _pg_pool = AsyncConnectionPool(
            conninfo=settings.database_dsn,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False,
        )
        await _pg_pool.open()
        checkpointer = AsyncPostgresSaver(_pg_pool)
        await checkpointer.setup()  # Crea tablas de checkpoints si no existen
        await setup_graph(checkpointer)
        logger.info("postgres_checkpointer_ready")
    except Exception as exc:
        logger.warning("postgres_checkpointer_failed", extra={"error": str(exc)})
        await setup_graph()  # Fallback a MemorySaver

    # Crear campos personalizados en Bitrix si no existen
    try:
        from integrations.bitrix.client import BitrixClient
        await BitrixClient().ensure_custom_fields()
    except Exception as exc:
        logger.warning("bitrix_ensure_fields_failed", extra={"error": str(exc)})

    await start_connector_poll()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("scheduler_started")
    yield
    scheduler.shutdown(wait=False)
    await stop_connector_poll()
    await close_redis()
    await close_pool()
    if _pg_pool:
        await _pg_pool.close()
    logger.info("app_shutdown")


app = FastAPI(
    title="Bot Telcel Portabilidad",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-Admin-Token", "Authorization", "Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: object) -> Response:
    start = time.perf_counter()
    response: Response = await call_next(request)  # type: ignore[operator]
    ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": ms,
        },
    )
    return response


app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(telegram_router)
app.include_router(bitrix_router)
app.include_router(bitrix_bot_control_router)
app.include_router(connector_router)
app.include_router(admin_router)

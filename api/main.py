import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response

from api.routes.health import router as health_router
from api.routes.webhooks import router as webhooks_router
from config.logging import setup_logging
from config.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("app_startup", extra={"version": settings.app_version, "env": settings.environment})
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="Bot Telcel Portabilidad",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
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

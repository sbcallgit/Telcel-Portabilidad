import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from config.settings import settings
from integrations.exceptions import DatabaseError

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("db_pool_created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("db_pool_closed")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Context manager que entrega una conexión del pool."""
    if _pool is None:
        raise DatabaseError("Pool no inicializado — llamar create_pool() primero")
    try:
        async with _pool.acquire() as conn:
            yield conn
    except asyncpg.PostgresError as exc:
        raise DatabaseError("Error de base de datos", retriable=False, original=exc) from exc


async def execute(query: str, *args: Any) -> str:
    """Ejecuta una query parametrizada sin retorno de filas.

    NUNCA concatenar datos de usuario en query — usar $1, $2, etc.
    """
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Fetch múltiples filas con query parametrizada."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    """Fetch una sola fila con query parametrizada."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    """Fetch un solo valor con query parametrizada."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)

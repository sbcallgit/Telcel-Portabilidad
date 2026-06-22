"""Conexión de solo lectura a la BD de Megacable (agente externo)."""

import asyncpg
from config.settings import settings


async def fetch_megacable(query: str, *args) -> list[dict]:
    conn = await asyncpg.connect(
        host=settings.megacable_db_host,
        port=settings.megacable_db_port,
        database=settings.megacable_db_name,
        user=settings.megacable_db_user,
        password=settings.megacable_db_password,
        timeout=10,
    )
    try:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

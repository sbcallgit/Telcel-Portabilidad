"""Script principal de carga de la base de conocimiento.

Uso: make seed
     docker compose exec api python -m knowledge.seed
"""

import asyncio
import logging

from db.migrations import CREATE_TABLES_SQL
from integrations.postgres import client as db
from knowledge.loaders import load_cacs, load_equipos, load_ladas, load_objeciones, load_paquetes_asl, load_promos

logger = logging.getLogger(__name__)


async def seed() -> None:
    logger.info("seed_start")

    await db.create_pool()

    logger.info("creating_tables")
    async with db.get_connection() as conn:
        await conn.execute(CREATE_TABLES_SQL)

    await load_ladas.load()
    await load_promos.load()
    await load_paquetes_asl.load()
    await load_cacs.load()
    await load_equipos.load()
    await load_objeciones.load()

    await db.close_pool()
    logger.info("seed_complete")


if __name__ == "__main__":
    import sys

    from config.logging import setup_logging

    setup_logging()
    asyncio.run(seed())
    sys.exit(0)

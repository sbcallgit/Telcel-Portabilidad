"""Carga la tabla de LADAs habilitadas en Región 4.

TODO: reemplazar los datos de ejemplo con el listado real de LADAs R4.
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

# LADAs de ejemplo de Región 4 (NL, Coahuila, Tamaulipas, parte de SLP)
LADAS_R4 = [
    {"lada": "811", "ciudad": "Monterrey", "estado": "Nuevo León", "habilitada": True},
    {"lada": "812", "ciudad": "Monterrey", "estado": "Nuevo León", "habilitada": True},
    {"lada": "818", "ciudad": "Monterrey", "estado": "Nuevo León", "habilitada": True},
    {"lada": "828", "ciudad": "Montemorelos", "estado": "Nuevo León", "habilitada": True},
    {"lada": "844", "ciudad": "Saltillo", "estado": "Coahuila", "habilitada": True},
    {"lada": "861", "ciudad": "Monclova", "estado": "Coahuila", "habilitada": True},
    {"lada": "867", "ciudad": "Nuevo Laredo", "estado": "Tamaulipas", "habilitada": True},
    {"lada": "868", "ciudad": "Piedras Negras", "estado": "Coahuila", "habilitada": True},
    {"lada": "871", "ciudad": "Torreón", "estado": "Coahuila", "habilitada": False},
]


async def load() -> None:
    logger.info("loading_ladas", extra={"count": len(LADAS_R4)})
    for row in LADAS_R4:
        await db.execute(
            """
            INSERT INTO ladas (lada, ciudad, estado, habilitada)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (lada) DO UPDATE SET habilitada = EXCLUDED.habilitada
            """,
            row["lada"],
            row["ciudad"],
            row["estado"],
            row["habilitada"],
        )
    logger.info("ladas_loaded")

"""Carga el listado de equipos y si requieren desbloqueo para portabilidad.

TODO: completar con el catálogo real de equipos de Telcel R4.
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

EQUIPOS = [
    {"marca": "Apple", "modelo": "iPhone 15", "requiere_desbloqueo": False},
    {"marca": "Apple", "modelo": "iPhone 14", "requiere_desbloqueo": False},
    {"marca": "Apple", "modelo": "iPhone 13", "requiere_desbloqueo": False},
    {"marca": "Samsung", "modelo": "Galaxy S24", "requiere_desbloqueo": False},
    {"marca": "Samsung", "modelo": "Galaxy A54", "requiere_desbloqueo": True},
    {"marca": "Motorola", "modelo": "Moto G84", "requiere_desbloqueo": True},
    {"marca": "Xiaomi", "modelo": "Redmi Note 13", "requiere_desbloqueo": True},
]


async def load() -> None:
    logger.info("loading_equipos", extra={"count": len(EQUIPOS)})
    for row in EQUIPOS:
        await db.execute(
            """
            INSERT INTO equipos_desbloqueo (marca, modelo, requiere_desbloqueo)
            VALUES ($1, $2, $3)
            ON CONFLICT (marca, modelo) DO UPDATE SET requiere_desbloqueo = EXCLUDED.requiere_desbloqueo
            """,
            row["marca"],
            row["modelo"],
            row["requiere_desbloqueo"],
        )
    logger.info("equipos_loaded")

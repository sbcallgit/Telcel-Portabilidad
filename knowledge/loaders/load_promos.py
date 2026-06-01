"""Carga las promos vigentes de portabilidad.

Vigencia actual: 31/05/2026. Actualizar cuando Telcel publique nuevas promos.
Las promos son configuración versionada — no hardcodear precios en el código del agente.
"""

import logging
from datetime import date

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

PROMOS = [
    {
        "nombre": "Sin Recarga Inicial $50",
        "recarga": 50,
        "beneficios": "5 GB datos, llamadas y SMS ilimitados a Telcel",
        "vigencia": date(2026, 5, 31),
        "condicion": "Solo portabilidad desde otro operador. Sin recarga inicial.",
    },
    {
        "nombre": "Portabilidad Plus $100",
        "recarga": 100,
        "beneficios": "10 GB datos, llamadas ilimitadas, SMS ilimitados",
        "vigencia": date(2026, 5, 31),
        "condicion": "Solo portabilidad. Primera recarga de $100.",
    },
    {
        "nombre": "Sin Recarga Inicial $100",
        "recarga": 100,
        "beneficios": "8 GB datos, llamadas ilimitadas a Telcel y SMS ilimitados",
        "vigencia": date(2026, 5, 31),
        "condicion": "Solo portabilidad. Sin recarga inicial requerida.",
    },
    {
        "nombre": "Portabilidad Plus Plus $150",
        "recarga": 150,
        "beneficios": "8 GB datos + 4 GB adicionales para redes sociales, llamadas ilimitadas",
        "vigencia": date(2026, 5, 31),
        "condicion": "Solo portabilidad. Primera recarga de $150.",
    },
]


async def load() -> None:
    logger.info("loading_promos", extra={"count": len(PROMOS)})
    await db.execute("UPDATE promos SET activa = false")
    for row in PROMOS:
        await db.execute(
            """
            INSERT INTO promos (nombre, recarga, beneficios, vigencia, condicion, activa)
            VALUES ($1, $2, $3, $4, $5, true)
            ON CONFLICT DO NOTHING
            """,
            row["nombre"],
            row["recarga"],
            row["beneficios"],
            row["vigencia"],
            row["condicion"],
        )
    logger.info("promos_loaded")

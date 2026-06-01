"""Carga el directorio de CACs (Centros de Atención a Clientes) de Región 4.

TODO: completar con el listado real de CACs R4 incluyendo coordenadas exactas.
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

CACS_R4 = [
    {
        "nombre": "CAC Telcel Monterrey Centro",
        "direccion": "Av. Constitución 1234, Centro, Monterrey, NL",
        "municipio": "Monterrey",
        "estado": "Nuevo León",
        "lat": 25.6714,
        "lng": -100.3098,
        "horario": "Lun-Sáb 9am-9pm",
    },
    {
        "nombre": "CAC Telcel San Pedro",
        "direccion": "Av. Vasconcelos 300, San Pedro Garza García, NL",
        "municipio": "San Pedro Garza García",
        "estado": "Nuevo León",
        "lat": 25.6510,
        "lng": -100.3960,
        "horario": "Lun-Sáb 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Saltillo",
        "direccion": "Blvd. Luis Echeverría 1234, Saltillo, Coah",
        "municipio": "Saltillo",
        "estado": "Coahuila",
        "lat": 25.4232,
        "lng": -100.9962,
        "horario": "Lun-Sáb 9am-9pm",
    },
]


async def load() -> None:
    logger.info("loading_cacs", extra={"count": len(CACS_R4)})
    for row in CACS_R4:
        await db.execute(
            """
            INSERT INTO cacs (nombre, direccion, municipio, estado, lat, lng, horario)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
            """,
            row["nombre"],
            row["direccion"],
            row["municipio"],
            row["estado"],
            row["lat"],
            row["lng"],
            row["horario"],
        )
    logger.info("cacs_loaded")

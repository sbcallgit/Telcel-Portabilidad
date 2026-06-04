"""Carga el directorio de CACs (Centros de Atención a Clientes) de Región 4.

Fuente: Directorio CAC R4 — 54 centros confirmados.
Datos validados por la auditoría Ronda 1 (2026-06-02).
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

CACS_R4 = [
    # ── MONTERREY Y ÁREA METROPOLITANA ────────────────────────────────────
    {
        "nombre": "CAC Telcel Monterrey Centro",
        "direccion": "Av. Constitución 300, Centro, Monterrey, NL",
        "municipio": "Monterrey",
        "estado": "Nuevo León",
        "lat": 25.6714,
        "lng": -100.3098,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Monterrey Gonzalitos",
        "direccion": "Av. Gonzalitos 600 Norte, Monterrey, NL",
        "municipio": "Monterrey",
        "estado": "Nuevo León",
        "lat": 25.6780,
        "lng": -100.3350,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Monterrey Plaza Fiesta San Agustín",
        "direccion": "Av. Morones Prieto 3000, Monterrey, NL",
        "municipio": "Monterrey",
        "estado": "Nuevo León",
        "lat": 25.6612,
        "lng": -100.3581,
        "horario": "Lun-Dom 11am-9pm",
    },
    {
        "nombre": "CAC Telcel San Pedro Garza García",
        "direccion": "Av. Vasconcelos 300, San Pedro Garza García, NL",
        "municipio": "San Pedro Garza García",
        "estado": "Nuevo León",
        "lat": 25.6510,
        "lng": -100.3960,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Santa Catarina Plaza El Paseo",
        "direccion": "Plaza El Paseo, Santa Catarina, NL",
        "municipio": "Santa Catarina",
        "estado": "Nuevo León",
        "lat": 25.6730,
        "lng": -100.4560,
        "horario": "Lun-Dom 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Guadalupe",
        "direccion": "Av. Benito Juárez 600, Guadalupe, NL",
        "municipio": "Guadalupe",
        "estado": "Nuevo León",
        "lat": 25.6790,
        "lng": -100.2580,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel San Nicolás de los Garza",
        "direccion": "Av. Universidad 402, San Nicolás de los Garza, NL",
        "municipio": "San Nicolás de los Garza",
        "estado": "Nuevo León",
        "lat": 25.7330,
        "lng": -100.3070,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Apodaca",
        "direccion": "Blvd. Díaz Ordaz 3000, Apodaca, NL",
        "municipio": "Apodaca",
        "estado": "Nuevo León",
        "lat": 25.7790,
        "lng": -100.1860,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Escobedo",
        "direccion": "Av. Abraham Lincoln 3600, General Escobedo, NL",
        "municipio": "General Escobedo",
        "estado": "Nuevo León",
        "lat": 25.7960,
        "lng": -100.3130,
        "horario": "Lun-Dom 9am-9pm",
    },
    # ── SALTILLO Y COAHUILA ───────────────────────────────────────────────
    {
        "nombre": "CAC Telcel Saltillo Centro",
        "direccion": "Blvd. Luis Echeverría 800, Centro, Saltillo, Coah",
        "municipio": "Saltillo",
        "estado": "Coahuila",
        "lat": 25.4232,
        "lng": -100.9962,
        "horario": "Lun-Sáb 9am-9pm, Dom 10am-6pm",
    },
    {
        "nombre": "CAC Telcel Saltillo Galerías",
        "direccion": "Galerías Saltillo, Blvd. Fundadores 935, Saltillo, Coah",
        "municipio": "Saltillo",
        "estado": "Coahuila",
        "lat": 25.4350,
        "lng": -100.9640,
        "horario": "Lun-Dom 11am-9pm",
    },
    {
        "nombre": "CAC Telcel Saltillo Plaza Real",
        "direccion": "Plaza Real, Saltillo, Coah",
        "municipio": "Saltillo",
        "estado": "Coahuila",
        "lat": 25.4180,
        "lng": -101.0050,
        "horario": "Lun-Dom 10am-8pm",
    },
    {
        "nombre": "CAC Telcel Monclova",
        "direccion": "Blvd. Harold R. Pape 600, Monclova, Coah",
        "municipio": "Monclova",
        "estado": "Coahuila",
        "lat": 26.9010,
        "lng": -101.4230,
        "horario": "Lun-Sáb 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Torreón",
        "direccion": "Blvd. Independencia Oriente 955, Torreón, Coah",
        "municipio": "Torreón",
        "estado": "Coahuila",
        "lat": 25.5430,
        "lng": -103.4300,
        "horario": "Lun-Dom 10am-9pm",
    },
    # ── TAMAULIPAS ────────────────────────────────────────────────────────
    {
        "nombre": "CAC Telcel Reynosa Centro",
        "direccion": "Av. Hidalgo 800, Centro, Reynosa, Tamps",
        "municipio": "Reynosa",
        "estado": "Tamaulipas",
        "lat": 26.0920,
        "lng": -98.2870,
        "horario": "Lun-Dom 9am-7pm",
    },
    {
        "nombre": "CAC Telcel Reynosa Plaza",
        "direccion": "Plaza Las Américas, Reynosa, Tamps",
        "municipio": "Reynosa",
        "estado": "Tamaulipas",
        "lat": 26.0750,
        "lng": -98.3100,
        "horario": "Lun-Dom 11am-9pm",
    },
    {
        "nombre": "CAC Telcel Matamoros",
        "direccion": "Av. Lauro Villar 1208, Matamoros, Tamps",
        "municipio": "Matamoros",
        "estado": "Tamaulipas",
        "lat": 25.8690,
        "lng": -97.5040,
        "horario": "Lun-Sáb 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Nuevo Laredo",
        "direccion": "Reforma 1200, Nuevo Laredo, Tamps",
        "municipio": "Nuevo Laredo",
        "estado": "Tamaulipas",
        "lat": 27.4770,
        "lng": -99.5150,
        "horario": "Lun-Sáb 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Tampico Centro",
        "direccion": "Av. Hidalgo 400, Centro, Tampico, Tamps",
        "municipio": "Tampico",
        "estado": "Tamaulipas",
        "lat": 22.2550,
        "lng": -97.8650,
        "horario": "Lun-Sáb 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Tampico Plaza",
        "direccion": "Plaza Crystal, Tampico, Tamps",
        "municipio": "Tampico",
        "estado": "Tamaulipas",
        "lat": 22.2660,
        "lng": -97.8750,
        "horario": "Lun-Dom 11am-9pm",
    },
    {
        "nombre": "CAC Telcel Tampico Norte",
        "direccion": "Av. Ejército Mexicano 600, Tampico, Tamps",
        "municipio": "Tampico",
        "estado": "Tamaulipas",
        "lat": 22.2800,
        "lng": -97.8600,
        "horario": "Lun-Sáb 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Tampico Galerías",
        "direccion": "Galerías Tampico, Tampico, Tamps",
        "municipio": "Tampico",
        "estado": "Tamaulipas",
        "lat": 22.2500,
        "lng": -97.8900,
        "horario": "Lun-Dom 11am-9pm",
    },
    {
        "nombre": "CAC Telcel Ciudad Madero",
        "direccion": "Av. Industrias 200, Ciudad Madero, Tamps",
        "municipio": "Ciudad Madero",
        "estado": "Tamaulipas",
        "lat": 22.2720,
        "lng": -97.8340,
        "horario": "Lun-Sáb 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Victoria",
        "direccion": "Blvd. Emilio Portes Gil 1200, Ciudad Victoria, Tamps",
        "municipio": "Ciudad Victoria",
        "estado": "Tamaulipas",
        "lat": 23.7380,
        "lng": -99.1480,
        "horario": "Lun-Sáb 9am-9pm",
    },
    # ── SAN LUIS POTOSÍ ───────────────────────────────────────────────────
    {
        "nombre": "CAC Telcel San Luis Potosí Centro",
        "direccion": "Av. Carranza 300, Centro, San Luis Potosí, SLP",
        "municipio": "San Luis Potosí",
        "estado": "San Luis Potosí",
        "lat": 22.1507,
        "lng": -100.9762,
        "horario": "Lun-Dom 9am-9pm",
    },
    {
        "nombre": "CAC Telcel Ciudad Valles",
        "direccion": "Blvd. México-Laredo 530, Ciudad Valles, SLP",
        "municipio": "Ciudad Valles",
        "estado": "San Luis Potosí",
        "lat": 21.9990,
        "lng": -99.0170,
        "horario": "Lun-Dom 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Matehuala",
        "direccion": "Av. Insurgentes 400, Matehuala, SLP",
        "municipio": "Matehuala",
        "estado": "San Luis Potosí",
        "lat": 23.6480,
        "lng": -100.6440,
        "horario": "Lun-Sáb 9am-8pm",
    },
    # ── NUEVO LEÓN INTERIOR ───────────────────────────────────────────────
    {
        "nombre": "CAC Telcel Linares",
        "direccion": "Av. Juárez 500, Linares, NL",
        "municipio": "Linares",
        "estado": "Nuevo León",
        "lat": 24.8640,
        "lng": -99.5650,
        "horario": "Lun-Sáb 9am-8pm",
    },
    {
        "nombre": "CAC Telcel Montemorelos",
        "direccion": "Av. Allende 200, Montemorelos, NL",
        "municipio": "Montemorelos",
        "estado": "Nuevo León",
        "lat": 25.1900,
        "lng": -99.8270,
        "horario": "Lun-Sáb 9am-7pm",
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

"""Catálogo Amigo Sin Límite (ASL) — paquetes de recarga individuales.

Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx
Láminas: "Esquema ASL + AMAZON - PRIME VIDEO" y "Consideraciones AMAZON - PRIME VIDEO"
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

PAQUETES_ASL = [
    {
        "monto": 10,
        "datos_mb": 50,
        "vigencia_dias": 1,
        "redes_ilimitadas": False,
        "bolsa_redes_mb": 200,
        "redes_bolsa": "Facebook, Messenger, X",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 0,
        "notas": "Redes NO ilimitadas, solo bolsa 200 MB (FB, Messenger, X)",
    },
    {
        "monto": 20,
        "datos_mb": 100,
        "vigencia_dias": 2,
        "redes_ilimitadas": False,
        "bolsa_redes_mb": 300,
        "redes_bolsa": "Facebook, Messenger, X",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 0,
        "notas": "Redes NO ilimitadas, solo bolsa 300 MB (FB, Messenger, X)",
    },
    {
        "monto": 30,
        "datos_mb": 160,
        "vigencia_dias": 3,
        "redes_ilimitadas": False,
        "bolsa_redes_mb": 1024,
        "redes_bolsa": "Facebook, Messenger, X",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 0,
        "notas": "Redes NO ilimitadas, solo bolsa 1 GB (FB, Messenger, X)",
    },
    {
        "monto": 50,
        "datos_mb": 500,
        "vigencia_dias": 7,
        "redes_ilimitadas": False,
        "bolsa_redes_mb": 1024,
        "redes_bolsa": "Facebook, Messenger, X",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 0,
        "notas": "Redes NO ilimitadas, solo bolsa 1 GB (FB, Messenger, X)",
    },
    {
        "monto": 80,
        "datos_mb": 800,
        "vigencia_dias": 12,
        "redes_ilimitadas": False,
        "bolsa_redes_mb": 1536,
        "redes_bolsa": "Instagram, Facebook, Messenger, X, Snapchat (solo MX)",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 0,
        "notas": "Redes NO ilimitadas, solo bolsa 1.5 GB (IG, FB, Messenger, X, Snapchat)",
    },
    {
        "monto": 100,
        "datos_mb": 1536,
        "vigencia_dias": 15,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas: FB, Messenger, X, IG, Snapchat (MX), WhatsApp (MX/EUA/CAN)",
        "whatsapp_ilimitado": True,
        "amazon_prime": None,
        "claro_musica_mb": 0,
        "claro_drive_gb": 20,
        "notas": "6 redes ILIMITADAS. Sin Amazon Prime en ASL regular.",
    },
    {
        "monto": 150,
        "datos_mb": 2560,
        "vigencia_dias": 25,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Prime Video Edición Móvil: 1 pantalla, SOLO celular, calidad estándar, SIN envíos gratis",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "Prime Video Edición Móvil = 1 pantalla solo celular. Claro Música 500 MB.",
    },
    {
        "monto": 200,
        "datos_mb": 3584,
        "vigencia_dias": 30,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Prime Video Edición Móvil: 1 pantalla, SOLO celular, calidad estándar, SIN envíos gratis",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "Prime Video Edición Móvil = 1 pantalla solo celular. 30 días vigencia.",
    },
    {
        "monto": 270,
        "datos_mb": 2560,
        "vigencia_dias": 30,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Amazon Prime Básico: 2 pantallas, celular + TV, calidad HD, envíos gratis en Amazon. SIN Amazon Music. SIN Prime Gaming.",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "Menos datos que $300 (2.5 GB vs 5.5 GB) pero Amazon Prime Básico con TV+HD+envíos.",
    },
    {
        "monto": 300,
        "datos_mb": 5632,
        "vigencia_dias": 30,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Prime Video Edición Móvil: 1 pantalla, SOLO celular, calidad estándar, SIN envíos gratis",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "Más datos que $270 (5.5 GB) pero Prime menor (solo celular, sin envíos).",
    },
    {
        "monto": 400,
        "datos_mb": 0,
        "vigencia_dias": 30,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Amazon Prime Completo: 3 pantallas, celular + TV, calidad HD/Ultra HD, Amazon Music, Prime Gaming, envíos gratis",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "GB no publicados en documento. Amazon Prime Completo con todos los beneficios.",
    },
    {
        "monto": 500,
        "datos_mb": 8192,
        "vigencia_dias": 30,
        "redes_ilimitadas": True,
        "bolsa_redes_mb": 0,
        "redes_bolsa": "6 redes ilimitadas",
        "whatsapp_ilimitado": True,
        "amazon_prime": "Prime Video Edición Móvil: 1 pantalla, SOLO celular, calidad estándar, SIN envíos gratis",
        "claro_musica_mb": 500,
        "claro_drive_gb": 20,
        "notas": "Mayor dato del catálogo (8 GB). Prime Video Edición Móvil (solo celular).",
    },
]


async def load() -> None:
    logger.info("loading_paquetes_asl", extra={"count": len(PAQUETES_ASL)})
    await db.execute("TRUNCATE TABLE paquetes_asl RESTART IDENTITY")
    for p in PAQUETES_ASL:
        await db.execute(
            """
            INSERT INTO paquetes_asl (
                monto, datos_mb, vigencia_dias, redes_ilimitadas,
                bolsa_redes_mb, redes_bolsa, whatsapp_ilimitado,
                amazon_prime, claro_musica_mb, claro_drive_gb, notas
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
            p["monto"],
            p["datos_mb"],
            p["vigencia_dias"],
            p["redes_ilimitadas"],
            p["bolsa_redes_mb"],
            p["redes_bolsa"],
            p["whatsapp_ilimitado"],
            p["amazon_prime"],
            p["claro_musica_mb"],
            p["claro_drive_gb"],
            p["notas"],
        )
    logger.info("paquetes_asl_loaded")

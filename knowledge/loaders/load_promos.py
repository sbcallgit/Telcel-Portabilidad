"""Promos reales de la campaña Muévete Prepago — vigencia 06/04/2026.

Fuente: Script_Portabilidad_05032026.md
Dos líneas de producto:
  1. Portabilidad Plus       — cliente realiza la recarga
  2. Sin Recarga Inicial     — primera recarga gratis (BASE SEMÁFORO VERDE)
"""

import logging
from datetime import date

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

VIGENCIA = date(2026, 4, 6)

PROMOS = [
    # ── PORTABILIDAD PLUS ──────────────────────────────────────────────────
    {
        "nombre": "Portabilidad Plus $50",
        "recarga": 50,
        "beneficios": (
            "1.5 GB para navegar en internet | "
            "1 GB bolsa para redes sociales (Facebook, Messenger, Instagram, X, Snapchat — solo México; NO son ilimitadas) | "
            "Minutos, mensajes y WhatsApp ilimitados (México, EUA y Canadá) | "
            "Vigencia 7 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. IMPORTANTE: redes sociales NO son ilimitadas, solo incluye bolsa de 1 GB. "
            "Recarga en paquete de $50. "
            "No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $80",
        "recarga": 80,
        "beneficios": (
            "2.4 GB para navegar en internet | "
            "1.5 GB bolsa para redes sociales (Facebook, Messenger, Instagram, X, Snapchat — solo México; NO son ilimitadas) | "
            "Minutos, mensajes y WhatsApp ilimitados (México, EUA y Canadá) | "
            "Vigencia 12 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. IMPORTANTE: redes sociales NO son ilimitadas, solo incluye bolsa de 1.5 GB. "
            "No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $100",
        "recarga": 100,
        "beneficios": (
            "5.5 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X (Twitter), Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime Básico incluido: 1 dispositivo, calidad estándar, envíos gratis en compras (link llega por SMS en 24-36 h tras primera recarga) | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB para fotos y videos | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. Primera recarga de $100 en una sola exhibición para activar la promo. "
            "No aplica en Liverpool, Walmart, MixUP ni bancos. "
            "Puede recargar en CACs Telcel, Mi Telcel, Telcel.com, distribuidores autorizados y cadenas comerciales."
        ),
    },
    {
        "nombre": "Portabilidad Plus $150",
        "recarga": 150,
        "beneficios": (
            "8 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X, Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime Básico incluido: 1 dispositivo, calidad estándar, envíos gratis | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $200",
        "recarga": 200,
        "beneficios": (
            "8 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X, Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime Básico incluido: 1 dispositivo, calidad estándar, envíos gratis | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $270",
        "recarga": 270,
        "beneficios": (
            "2.5 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS — solo México | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime BÁSICO: 2 pantallas (celular + TV), calidad HD, envíos gratis en Amazon (SIN Amazon Music ni Prime Gaming) | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. Amazon Prime Básico (2 pantallas, celular+TV, HD, envíos gratis). "
            "MENOS datos que $300 (2.5 GB vs 5.5 GB) pero MEJOR Amazon Prime (TV + HD + envíos). "
            "Redes sociales SOLO en México (no EUA/Canadá). "
            "No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $300",
        "recarga": 300,
        "beneficios": (
            "8 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X, Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime Básico incluido: 1 dispositivo, calidad estándar, envíos gratis | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Portabilidad Plus $400",
        "recarga": 400,
        "beneficios": (
            "8 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS — solo México | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Amazon Prime COMPLETO: 3 dispositivos, calidad HD/Ultra HD, Amazon Music, Prime Gaming, envíos gratis | "
            "Claro Música 500 MB | "
            "Claro Drive 20 GB | "
            "Vigencia 30 días | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Portabilidad Plus. Amazon Prime completo (3 dispositivos, HD). "
            "Redes sociales SOLO en México (no EUA/Canadá). "
            "No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    # ── SIN RECARGA INICIAL — BASE SEMÁFORO VERDE ─────────────────────────
    {
        "nombre": "Sin Recarga Inicial $50 — Triple Beneficios",
        "recarga": 50,
        "beneficios": (
            "2.5 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X, Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Claro Música 500 MB | "
            "Vigencia 25 días | "
            "PRIMERA RECARGA GRATIS — la primera recarga de $50 corre por cuenta de Telcel | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Sin Recarga Inicial — BASE SEMÁFORO VERDE. "
            "La PRIMERA recarga de $50 es completamente gratis (Telcel la regala). "
            "No incluye Amazon Prime ni Claro Drive. "
            "Recarga en paquete. No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
    },
    {
        "nombre": "Sin Recarga Inicial $100 — Triple Beneficios",
        "recarga": 100,
        "beneficios": (
            "5.5 GB para navegar en internet | "
            "6 redes sociales ILIMITADAS: WhatsApp, Facebook, Messenger, Instagram, X, Snapchat — México, EUA y Canadá | "
            "Llamadas y mensajes ilimitados (México, EUA y Canadá) | "
            "Claro Música 500 MB | "
            "Vigencia 30 días | "
            "PRIMERA RECARGA GRATIS — la primera recarga de $100 corre por cuenta de Telcel | "
            "Promoción válida 12 meses"
        ),
        "condicion": (
            "Sin Recarga Inicial — BASE SEMÁFORO VERDE. "
            "La PRIMERA recarga de $100 es completamente gratis (Telcel la regala). "
            "No incluye Amazon Prime ni Claro Drive. "
            "Recarga en paquete. No aplica en Liverpool, Walmart, MixUP ni bancos."
        ),
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
            VIGENCIA,
            row["condicion"],
        )
    logger.info("promos_loaded")

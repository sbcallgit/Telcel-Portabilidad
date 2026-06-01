"""Carga el banco de objeciones en PostgreSQL.

El agente busca en esta tabla por similitud de texto para rebatir objeciones del cliente.
TODO: completar con el banco real de objeciones validado por el equipo de ventas.
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

OBJECIONES = [
    {
        "texto": "está caro",
        "categoria": "precio",
        "respuesta": (
            "Entiendo que el precio importa. Con esta promo pagas una sola vez y llevas "
            "{beneficios} — muchos clientes nos dicen que al comparar termina siendo más barato "
            "que su plan actual. ¿Cuánto pagas ahorita al mes?"
        ),
    },
    {
        "texto": "lo voy a pensar",
        "categoria": "tiempo",
        "respuesta": (
            "¡Claro! Solo te comento que la promo está vigente hasta el {vigencia} y los lugares "
            "en el CAC se agotan. ¿Qué es lo que quieres pensar? Puedo resolverlo ahorita mismo."
        ),
    },
    {
        "texto": "no confío en Telcel",
        "categoria": "confianza",
        "respuesta": (
            "Te entiendo, esas experiencias importan. Esta campaña es 100% oficial de Telcel "
            "Región 4. El asesor te llama para confirmar todo antes de que vayas al CAC — "
            "nada de pagos por WhatsApp. ¿Te doy los datos del CAC más cercano para que lo veas?"
        ),
    },
    {
        "texto": "acabo de recargar",
        "categoria": "timing",
        "respuesta": (
            "No hay problema — puedes portar tu número cuando quieras. "
            "Tu recarga actual no se pierde, la portabilidad aplica desde que activas en Telcel. "
            "¿Cuánto recargas normalmente?"
        ),
    },
    {
        "texto": "mi señal es mala",
        "categoria": "cobertura",
        "respuesta": (
            "La cobertura depende de la zona. El asesor puede revisar la cobertura exacta "
            "de tu municipio antes de que vayas al CAC. ¿En qué colonia o ciudad estás?"
        ),
    },
    {
        "texto": "no quiero dar mis datos",
        "categoria": "privacidad",
        "respuesta": (
            "Completamente válido. Solo pedimos nombre, el número a portar y compañía actual — "
            "nada de INE, CURP ni datos bancarios por WhatsApp. El trámite formal lo haces "
            "tú en el CAC con tu identificación. ¿Te explico cómo es el proceso?"
        ),
    },
]


async def load() -> None:
    logger.info("loading_objeciones", extra={"count": len(OBJECIONES)})
    for row in OBJECIONES:
        await db.execute(
            """
            INSERT INTO objeciones (texto, categoria, respuesta)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            row["texto"],
            row["categoria"],
            row["respuesta"],
        )
    logger.info("objeciones_loaded")

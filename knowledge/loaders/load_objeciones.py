"""Banco de objeciones completo basado en Script_Portabilidad_05032026.md."""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

OBJECIONES = [
    # ── PRECIO ────────────────────────────────────────────────────────────
    {
        "texto": "está caro / es mucho dinero",
        "categoria": "precio",
        "respuesta": (
            "Entiendo perfectamente, cada peso cuenta. Justo por eso esta promoción es tan especial: "
            "con una sola recarga de ${recarga} usted obtiene {beneficios_cortos} — "
            "muchos clientes que tenían recargas chicas y seguidas terminan gastando menos con Telcel. "
            "¿Cuánto está pagando ahorita al mes con su compañía actual?"
        ),
    },
    {
        "texto": "puedo hacer recargas menores a $100",
        "categoria": "precio",
        "respuesta": (
            "Claro que sí, puede recargar $50 o $80 pesos. En ese caso se activa una bolsa de megas para redes sociales, "
            "pero las redes NO son ilimitadas — solo incluye una bolsa de 1 GB ($50) o 1.5 GB ($80). "
            "Para tener redes sociales completamente ilimitadas y Amazon Prime, la recarga mínima es de $100. "
            "¿Le gustaría saber los beneficios exactos de cada monto?"
        ),
    },
    {
        "texto": "no tengo para $100 ahorita",
        "categoria": "precio",
        "respuesta": (
            "No hay problema, para eso tenemos la opción Sin Recarga Inicial: "
            "la primera recarga de $50 o $100 corre completamente por cuenta de Telcel. "
            "Usted no paga nada el primer mes — Telcel le regala su primera recarga. "
            "¿Le platico cómo funciona esta opción?"
        ),
    },
    # ── TIEMPO / INDECISIÓN ────────────────────────────────────────────────
    {
        "texto": "lo voy a pensar / luego lo veo",
        "categoria": "tiempo",
        "respuesta": (
            "¡Claro! Solo le comento que la promoción está vigente hasta el 6 de abril de 2026 "
            "y los lugares en el CAC se agotan. ¿Qué es lo que quisiera pensar? "
            "Con gusto le resuelvo cualquier duda ahorita mismo."
        ),
    },
    {
        "texto": "espérame / dame tiempo",
        "categoria": "tiempo",
        "respuesta": (
            "Por supuesto, tómese el tiempo que necesite. Solo le recuerdo que la promo vence el 6 de abril. "
            "¿Hay algo específico que le genere duda? Puedo aclararlo en este momento."
        ),
    },
    # ── CONFIANZA ─────────────────────────────────────────────────────────
    {
        "texto": "no confío en Telcel / tuve mala experiencia",
        "categoria": "confianza",
        "respuesta": (
            "Le entiendo, esas experiencias importan. Esta campaña es 100% oficial de Telcel Región 4. "
            "El proceso es presencial en el CAC — usted va con su INE, recoge el chip gratis "
            "y no paga nada por WhatsApp. Un asesor le llama para confirmar todo antes de que vaya. "
            "¿Le doy la dirección del CAC más cercano para que lo vea personalmente?"
        ),
    },
    {
        "texto": "esto parece fraude / no creo que sea real",
        "categoria": "confianza",
        "respuesta": (
            "Completamente válido dudar. Le confirmo que esta es una campaña oficial de Telcel — "
            "el trámite se hace presencialmente en un Centro de Atención a Clientes Telcel con su INE. "
            "Nada de pagos por WhatsApp, nada de datos bancarios. "
            "¿Quiere que le dé la dirección del CAC más cercano para verificar en persona?"
        ),
    },
    # ── TIMING / RECARGA RECIENTE ─────────────────────────────────────────
    {
        "texto": "acabo de recargar / ya recargué",
        "categoria": "timing",
        "respuesta": (
            "No hay problema — puede iniciar el trámite cuando guste. "
            "Importante: el saldo que tiene actualmente no se transfiere, así que le conviene "
            "agotarlo primero. La portabilidad y el chip nuevo se activan al recargar en Telcel. "
            "¿Le platico cómo es el proceso para que lo tenga listo?"
        ),
    },
    {
        "texto": "¿el saldo se transfiere? / ¿me llevo mi saldo?",
        "categoria": "timing",
        "respuesta": (
            "Le informo que el saldo no es transferible — si tiene saldo con su compañía actual, "
            "deberá agotarlo antes de hacer la portabilidad. "
            "¿Tiene saldo disponible en este momento?"
        ),
    },
    # ── COBERTURA / SERVICIO ──────────────────────────────────────────────
    {
        "texto": "la señal de Telcel es mala / no tiene cobertura",
        "categoria": "cobertura",
        "respuesta": (
            "La cobertura depende de la zona específica. Telcel tiene la red más extensa de México. "
            "El asesor puede revisar la cobertura exacta de su colonia antes de que vaya al CAC. "
            "¿En qué municipio o colonia se encuentra para verificarlo?"
        ),
    },
    {
        "texto": "¿tiene 5G? / ¿funciona el 5G?",
        "categoria": "cobertura",
        "respuesta": (
            "Para disfrutar la red 5G de Telcel necesita tres cosas: "
            "un chip versión 6.3 en adelante (se lo dan en el CAC), "
            "un equipo compatible con 5G, y estar en una zona con cobertura 5G. "
            "Si su equipo es compatible, en el CAC le asignan el chip correcto automáticamente."
        ),
    },
    # ── EQUIPO ────────────────────────────────────────────────────────────
    {
        "texto": "no sé si mi equipo está liberado / mi celular no acepta chips",
        "categoria": "equipo",
        "respuesta": (
            "No se preocupe, eso lo validamos fácil. ¿Me dice la marca y modelo de su celular? "
            "Con eso reviso si es compatible con Telcel. "
            "Si viene de Movistar, AT&T o Unefon, en muchos casos podemos conseguirle el código de desbloqueo "
            "para que lo ingresen en el CAC — sin costo adicional."
        ),
    },
    {
        "texto": "tengo eSIM / mi celular usa eSIM",
        "categoria": "equipo",
        "respuesta": (
            "La promoción que le ofrezco incluye un chip físico, pero si su equipo tiene eSIM no hay problema: "
            "el trámite lo completa directamente en el Centro de Atención a Clientes Telcel al recoger su chip. "
            "¿Me dice la marca y modelo de su equipo para verificar que está en la lista de compatibles con eSIM?"
        ),
    },
    # ── PROCESO ───────────────────────────────────────────────────────────
    {
        "texto": "¿debo dar de baja mi línea antes? / ¿cancelo mi línea?",
        "categoria": "proceso",
        "respuesta": (
            "No, no necesita dar de baja su línea actual — la portabilidad la cancela automáticamente. "
            "Usted solo va al CAC con su INE, recoge el chip gratis y recarga en Telcel. "
            "Su número actual se porta solo, sin trámites adicionales con su compañía."
        ),
    },
    {
        "texto": "¿cuánto tarda? / ¿cuándo me llega señal?",
        "categoria": "proceso",
        "respuesta": (
            "Si inicia su trámite entre las 9 am y las 5 pm de lunes a sábado, "
            "su línea queda activa al día siguiente a las 2 am aproximadamente. "
            "El proceso de portabilidad no se puede posponer una vez iniciado — "
            "por eso es importante que haya agotado su saldo previo."
        ),
    },
    {
        "texto": "¿dónde puedo recargar? / ¿en qué tiendas recargo?",
        "categoria": "proceso",
        "respuesta": (
            "Puede recargar en: Centros de Atención Telcel, Centros Comerciales Telcel, Mi Telcel app, "
            "Telcel.com, distribuidores autorizados y cadenas comerciales como OXXO, 7-Eleven, etc. "
            "IMPORTANTE: por el momento NO aplica en Liverpool, Walmart, MixUP ni en bancos."
        ),
    },
    {
        "texto": "¿para qué es el NIP? / ¿qué es el NIP?",
        "categoria": "proceso",
        "respuesta": (
            "El NIP de portabilidad es un código de seguridad que su compañía actual le envía por SMS "
            "cuando usted marca al 051 desde su celular. Ese NIP confirma que usted autoriza el cambio. "
            "El NIP lo gestiona el asesor con usted en llamada — nunca se pide por WhatsApp."
        ),
    },
    # ── PRIVACIDAD ────────────────────────────────────────────────────────
    {
        "texto": "no quiero dar mis datos / para qué necesitan mi información",
        "categoria": "privacidad",
        "respuesta": (
            "Completamente válido. Solo pedimos nombre, número a portar y compañía actual — "
            "nada de INE, CURP ni datos bancarios por WhatsApp. "
            "El trámite formal lo hace usted en el CAC con su identificación. "
            "Cualquier dato que proporcione se trata conforme al Aviso de Privacidad de Telcel (www.telcel.com). "
            "¿Le explico cómo es el proceso paso a paso?"
        ),
    },
    # ── AMAZON PRIME ──────────────────────────────────────────────────────
    {
        "texto": "¿cómo activo el Amazon Prime? / no me llegó el link de Amazon",
        "categoria": "amazon",
        "respuesta": (
            "El link de Amazon Prime Básico le llega por mensaje de texto en un lapso de 24 a 36 horas "
            "después de realizar su primera recarga de $100 en Telcel. "
            "Con ese link registra su cuenta de Amazon Prime en un dispositivo celular. "
            "Si no le llega en ese tiempo, el asesor puede gestionar el reenvío."
        ),
    },
    {
        "texto": "¿el Amazon Prime es completo? / ¿incluye Amazon Video?",
        "categoria": "amazon",
        "respuesta": (
            "Depende del monto de recarga: "
            "con $100, $150, $200 o $300 incluye Amazon Prime Básico (1 dispositivo, calidad estándar, envíos gratis). "
            "Con $270 o $400 incluye Amazon Prime Completo (3 dispositivos, HD/Ultra HD, Amazon Music, Prime Gaming). "
            "¿Con cuánto suele recargar normalmente?"
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

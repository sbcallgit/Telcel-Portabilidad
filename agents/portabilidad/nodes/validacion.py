"""Primer filtro operativo: valida LADA/región antes de continuar el flujo."""

import logging
import re

from langchain_core.messages import AIMessage, SystemMessage

from agents.llm import get_llm
from agents.portabilidad.utils import render_prompt, split_msg
from agents.portabilidad.context import (
    ANTI_RENDICION,
    ASL_CATALOG,
    CHANNEL_RULES,
    CLARO_DRIVE_MUSICA,
    FORMAT_RULES,
    GREETING_VARIANTS,
    HARD_RULES,
    ID_DOCS_INFO,
    PORTABILITY_SCHEDULE,
    SALES_APPROACH,
)
from agents.portabilidad.state import PortabilidadState
from integrations.postgres import client as db

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")
_LADA_RE = re.compile(r"\b(\d{3})\b")
_ESCALATION_WORDS = ["asesor", "humano", "persona real", "agente", "supervisor"]
_SENSITIVE_WORDS = ["murió", "falleció", "muerto", "difunto", "funeral", "accidente", "emergencia"]
_SEGUIMIENTO = [
    "llámame después", "llamame despues", "llámame mañana", "llamame mañana",
    "contáctenme", "contactenme", "me contactan", "me llaman", "llámenme", "llamenme",
    "más adelante", "mas adelante", "en otro momento", "luego te confirmo",
    "mañana te digo", "ahorita no puedo", "ahorita no", "después me comunico",
    "me comunico después", "me comunico despues", "ya me comunico",
    "cuando pueda", "cuando esté listo", "cuando este listo",
]
_POSPAGO = [
    "renta mensual", "plan pospago", "pospago", "postpago", "contrato mensual",
    "plan de renta", "plan con contrato", "factura mensual", "cambiar a pospago",
    "mensualidad",
]
_CAC_Q = ["cac", "centro de atención", "sucursal", "oficina telcel", "donde ir", "dónde ir",
          "donde queda", "dónde queda", "dirección", "horario"]
_HORARIO_Q = ["cuándo", "cuando", "cuanto tarda", "cuánto tarda", "portación", "portacion",
              "se ejecuta", "queda lista", "domingo", "sábado noche", "viernes tarde"]
_CANALES_Q = ["recargar en", "donde recargo", "dónde recargo", "banco", "bancos",
              "walmart", "liverpool", "mixup", "oxxo", "cajero"]
_ID_Q = [
    "identificación", "identificacion", "id oficial", "ine", "pasaporte", "licencia",
    "qué documento", "que documento", "qué necesito", "que necesito llevar",
    "qué papeles", "que papeles", "documentos", "requisitos para portar",
]
_CLARO_DRIVE_Q = ["claro drive", "clarodrive", "almacenamiento en la nube", "guardar fotos",
                  "guardar archivos", "20 gb"]
_CLARO_MUSICA_Q = ["claro música", "claro musica", "app de música", "app de musica"]
_SOCIAL_ENGINEERING = [
    "amigo del dueño", "amigo del director", "amigo del gerente", "conoce al dueño",
    "conozco al dueño", "conozco al director", "trabajo en telcel", "soy empleado",
    "soy trabajador de telcel", "habla con tu jefe", "habla con el gerente",
    "habla con el encargado", "quiero hablar con el director", "hablar con el dueño",
    "el gerente me prometió", "el director me dijo", "el dueño me autorizó",
    "tengo una carta", "traigo una autorización especial", "ya hablé con el director",
    "soy socio de telcel", "soy accionista", "me mandó el corporativo",
]
_FUERA_R4 = ["cancún", "cancun", "mérida", "merida", "guadalajara", "ciudad de méxico",
             "cdmx", "monterrreyyyy"]


def _count_digits(text: str) -> int:
    return sum(c.isdigit() for c in text)


def _extract_phone(text: str) -> str | None:
    """Extrae exactamente un número mexicano de 10 dígitos.

    Reglas estrictas:
    - Acepta exactamente 10 dígitos en el texto (con o sin separadores normales: espacios, guiones, puntos, paréntesis).
    - Acepta 12 dígitos si empiezan con "52" (código de país México).
    - Rechaza (retorna None) cualquier otro conteo de dígitos — el llamador decidirá si es error de formato.
    """
    digits_only = re.sub(r"\D", "", text)

    if len(digits_only) == 12 and digits_only.startswith("52"):
        return digits_only[2:]

    if len(digits_only) == 10:
        return digits_only

    return None


def _is_phone_attempt(text: str) -> bool:
    """True si el mensaje parece un intento de ingresar un número de teléfono pero con formato incorrecto."""
    digit_count = _count_digits(text)
    non_digit = len(text.strip()) - digit_count
    return digit_count >= 7 and non_digit <= 8


async def _query_lada(lada: str) -> dict | None:
    row = await db.fetchrow(
        "SELECT lada, ciudad, estado, habilitada FROM ladas WHERE lada = $1", lada
    )
    return dict(row) if row else None


async def _get_cacs_by_city(city: str) -> list[dict]:
    city_lower = city.lower().strip()
    rows = await db.fetch(
        "SELECT nombre, direccion, municipio, estado, horario FROM cacs "
        "WHERE LOWER(municipio) LIKE $1 OR LOWER(estado) LIKE $1 "
        "ORDER BY municipio LIMIT 5",
        f"%{city_lower}%",
    )
    return [dict(r) for r in rows]


def _format_cacs(cacs: list[dict]) -> str:
    if not cacs:
        return ""
    lines = []
    for c in cacs:
        lines.append(f"📍 *{c['nombre']}*\n   {c['direccion']}\n   🕐 {c['horario']}")
    return "\n\n".join(lines)


async def _upsert_lead(phone: str, deal_id: str) -> None:
    """Crea o actualiza el registro en leads cuando se confirma el teléfono del cliente."""
    try:
        await db.execute(
            """
            INSERT INTO leads (telefono, bitrix_lead_id, etapa)
            VALUES ($1, $2, 'sondeo')
            ON CONFLICT (telefono) DO UPDATE SET
                bitrix_lead_id = CASE
                    WHEN leads.bitrix_lead_id = '' THEN EXCLUDED.bitrix_lead_id
                    ELSE leads.bitrix_lead_id
                END,
                updated_at = NOW()
            """,
            phone, deal_id,
        )
    except Exception as exc:
        logger.warning("upsert_lead_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def _crear_deal_primer_contacto(state: PortabilidadState) -> dict:
    """Asocia el deal de Bitrix al primer mensaje: busca el deal existente (creado por el
    imconnector al abrir el chat) y solo crea uno nuevo si no se encuentra ninguno."""
    from config.settings import settings
    if state.get("bitrix_lead_id") or not settings.bitrix_webhook_url:
        return {}
    phone = state.get("customer_phone", "")
    if not phone:
        return {}
    try:
        from integrations.bitrix.client import BitrixClient
        from integrations.redis_client import get_redis
        bx = BitrixClient()

        # 1. Prioridad: deal vinculado al canal Open Lines activo (guardado por connector.py)
        redis = await get_redis()
        deal_id = await redis.get(f"connector_deal:{phone}") or ""
        if deal_id:
            logger.info("bitrix_deal_desde_redis", extra={"phone_tail": phone[-4:], "deal_id": deal_id})

        # 2. Fallback: buscar por últimos 4 dígitos del teléfono
        if not deal_id:
            deal_id = await bx.buscar_deal_por_telefono(phone)

        if not deal_id:
            # Fallback: crear deal si Bitrix no lo creó automáticamente (también crea/vincula contacto)
            result = await bx.crear_deal(
                telefono=phone,
                datos={"COMMENTS": "Primer contacto vía WhatsApp/Telegram"},
                stage_id=settings.bitrix_stage_ia_porta,
            )
            deal_id = str(result.get("result", ""))
            logger.info("bitrix_deal_creado_fallback", extra={"phone_tail": phone[-4:], "deal_id": deal_id})
        else:
            # Deal existente (Open Lines) — vincular contacto en background si aún no tiene uno
            import asyncio
            asyncio.create_task(bx.link_contact_to_deal(deal_id, phone))

        if deal_id:
            return {"bitrix_lead_id": deal_id, "bitrix_etapa": "ia_porta"}
    except Exception as exc:
        logger.error("bitrix_primer_contacto_error", extra={"error": str(exc)})
    return {}


async def _validacion_logic(state: PortabilidadState, messages: list) -> dict:
    """Lógica principal del nodo de validación. Retorna el patch de estado."""
    user_text = getattr(messages[-1], "content", "").strip()
    lower = user_text.lower()

    # Quiere ser contactado después
    if any(w in lower for w in _SEGUIMIENTO):
        return {
            "messages": [AIMessage(content="Perfecto, queda registrado. Un asesor te contactará cuando estés listo.")],
            "escalate_to_human": True,
            "motivo_escalacion": "seguimiento",
        }

    # Caso sensible
    if any(w in lower for w in _SENSITIVE_WORDS):
        return {
            "messages": [AIMessage(content=(
                "Lamentamos mucho lo que estás pasando. "
                "Te conecto con un asesor para que te oriente con más calma."
            ))],
            "escalate_to_human": True,
            "motivo_escalacion": "caso_sensible",
        }

    # Solicitud directa de asesor
    if any(w in lower for w in _ESCALATION_WORDS):
        return {
            "messages": [AIMessage(content="Claro, ahora mismo te conecto con un asesor. ¿Me dices tu nombre?")],
            "escalate_to_human": True,
            "motivo_escalacion": "solicitud_directa",
        }

    # Pospago → derivar a CAC presencial
    if any(w in lower for w in _POSPAGO):
        return {
            "messages": [AIMessage(content=(
                "Para planes de renta mensual (pospago) le invito a acudir a un CAC Telcel "
                "con su identificación oficial. El trámite es presencial. "
                "¿Le ubico el CAC más cercano a su municipio?"
            ))]
        }

    # Fraude
    _fraud_offer = ["primo", "familiar", "conocido", "compadre"]
    _fraud_claim = ["prometió", "descuento especial", "80%", "90%", "me dijo", "gratis me"]
    if any(w in lower for w in _fraud_offer) and any(w in lower for w in _fraud_claim):
        return {
            "messages": [AIMessage(content=(
                "Solo puedo ofrecerle las promociones del catálogo oficial de Telcel. "
                "No existen descuentos adicionales por conocidos ni empleados. "
                "¿Le platico las promos reales disponibles?"
            ))]
        }

    # Pregunta sobre canales de recarga
    if any(w in lower for w in _CANALES_Q):
        return {
            "messages": [AIMessage(content=(
                "Los canales válidos para recargar con Amigo Sin Límite son:\n"
                "✅ CAC Telcel, Mi Telcel (app), www.Telcel.com, "
                "Distribuidores Autorizados y cadenas comerciales como OXXO y farmacias.\n"
                "❌ NO aplica en Liverpool, Walmart, MixUp ni en bancos (incluyendo apps bancarias y cajeros)."
            ))]
        }

    # Pregunta sobre documentos de identificación
    if any(w in lower for w in _ID_Q):
        return {
            "messages": [AIMessage(content=(
                "Para portarte necesitas una identificación oficial vigente con foto: "
                "INE/IFE, Pasaporte mexicano o Licencia de conducir 😊\n"
                "Si otra persona va al CAC por ti, lleva su propio ID, "
                "carta de autorización simple y copia de tu ID."
            ))]
        }

    # Pregunta sobre Claro Drive
    if any(w in lower for w in _CLARO_DRIVE_Q):
        return {
            "messages": [AIMessage(content=(
                "Claro Drive es almacenamiento en la nube de 20 GB para fotos, "
                "videos, contactos y archivos 📂\n"
                "Se incluye desde $100 y se usa desde la app o en www.clarodrive.com."
            ))]
        }

    # Pregunta sobre Claro Música
    if any(w in lower for w in _CLARO_MUSICA_Q):
        return {
            "messages": [AIMessage(content=(
                "Claro Música es una bolsa de 500 MB para navegar dentro de la app 🎵\n"
                "No es streaming completo tipo Spotify; es una bolsa de datos dedicada. "
                "Incluida desde $150."
            ))]
        }

    # Pregunta sobre horarios de portabilidad
    if any(w in lower for w in _HORARIO_Q):
        llm = get_llm()
        system = render_prompt("horarios", PORTABILITY_SCHEDULE=PORTABILITY_SCHEDULE, FORMAT_RULES=FORMAT_RULES)
        ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages[-4:]))
        return {"messages": split_msg(ai_msg.content)}

    # Pregunta sobre CAC por ciudad
    if any(w in lower for w in _CAC_Q):
        if any(ciudad in lower for ciudad in _FUERA_R4):
            ciudad_mencionada = next((c for c in _FUERA_R4 if c in lower), "esa ciudad")
            return {
                "messages": [AIMessage(content=(
                    f"{ciudad_mencionada.title()} no está en nuestra Región 4. "
                    "Para CACs en esa zona te recomiendo consultar www.telcel.com/donde-comprar. "
                    "¿Puedo ayudarte con algo más sobre tu portabilidad?"
                ))]
            }
        city_match = re.search(
            r"\b(monterrey|saltillo|reynosa|san pedro|santa catarina|tampico|ciudad valles|"
            r"cd\.?\s*valles|guadalupe|san nicolás|apodaca|linares|nuevo laredo|matamoros|victoria)\b",
            lower,
        )
        if city_match:
            city = city_match.group(1).replace("cd.", "ciudad").strip()
            cacs = await _get_cacs_by_city(city)
            if cacs:
                cac_text = _format_cacs(cacs)
                return {
                    "messages": [AIMessage(content=(
                        f"Aquí los CACs de {city.title()} disponibles en Región 4:\n\n{cac_text}\n\n"
                        "Recuerde llevar identificación oficial. "
                        "¿Le ayudo con algo más sobre su portabilidad?"
                    ))]
                }
        return {
            "messages": [AIMessage(content=(
                "Claro. ¿En qué municipio o ciudad se encuentra? "
                "Así le ubico el CAC más cercano de Región 4."
            ))]
        }

    # Extraer número de 10 dígitos
    numero = _extract_phone(user_text)
    if numero:
        lada = numero[:3]
        lada_info = await _query_lada(lada)

        if not lada_info:
            intentos = (state.get("intentos_sin_avance") or 0) + 1
            if intentos >= 2:
                return {
                    "messages": [AIMessage(content=(
                        "No encontré tu zona dentro de Región 4. "
                        "Te conecto con un asesor para verificar tu cobertura 😊"
                    ))],
                    "escalate_to_human": True,
                    "motivo_escalacion": "lada_no_identificada",
                    "intentos_sin_avance": intentos,
                }
            return {
                "messages": [AIMessage(content=(
                    f"El prefijo {lada} no aparece en nuestra Región 4. "
                    "¿Me confirmas en qué ciudad o estado te encuentras? "
                    "Así verifico si tienes cobertura digital."
                ))],
                "intentos_sin_avance": intentos,
            }

        if lada_info["habilitada"]:
            deal_id = state.get("bitrix_lead_id") or ""
            await _upsert_lead(numero, deal_id)
            return {
                "messages": [AIMessage(content=(
                    f"¡Listo! Tu zona ({lada_info['ciudad']}, {lada_info['estado']}) "
                    "sí aplica para portabilidad digital.\n"
                    "Para ofrecerte la mejor promo, ¿cuánto recargas normalmente al mes?"
                ))],
                "customer_phone": numero,
                "lada": lada,
                "ciudad": lada_info["ciudad"],
                "region_habilitada": True,
                "etapa": "sondeo",
                "intentos_sin_avance": 0,
            }

        return {
            "messages": [AIMessage(content=(
                f"Tu zona ({lada_info['ciudad']}) no está habilitada para portabilidad digital todavía, "
                "pero puedes hacer el trámite presencial en el CAC más cercano. "
                "¿Quieres la dirección?"
            ))],
            "customer_phone": numero,
            "lada": lada,
            "ciudad": lada_info["ciudad"],
            "region_habilitada": False,
            "etapa": "fin",
        }

    # Intento de teléfono con formato incorrecto
    digit_count = _count_digits(user_text)
    if _is_phone_attempt(user_text):
        digits_only = re.sub(r"\D", "", user_text)
        if len(digits_only) == 12 and not digits_only.startswith("52"):
            return {
                "messages": [AIMessage(content=(
                    "Ese número parece tener código de país incorrecto. "
                    "Para México solo usamos 10 dígitos (sin código de país). "
                    "¿Me lo compartes de nuevo?"
                ))]
            }
        return {
            "messages": [AIMessage(content=(
                f"El número debe tener exactamente 10 dígitos. "
                f"El que enviaste tiene {digit_count} — por favor compártelo de nuevo."
            ))]
        }

    # Pregunta directa sobre una LADA específica
    lada_match = _LADA_RE.search(user_text)
    is_lada_q = bool(re.search(r"\b(lada|aplica|zona|región|cubre)\b", lower))
    if lada_match and not is_lada_q:
        remaining = user_text.replace(lada_match.group(0), "").strip().replace("¿", "").replace("?", "").replace("y", "").strip()
        is_lada_q = len(remaining) < 8
    if is_lada_q and lada_match:
        lada_info = await _query_lada(lada_match.group(1))
        if lada_info:
            if lada_info["habilitada"]:
                reply = (
                    f"¡Sí! La LADA {lada_match.group(1)} ({lada_info['ciudad']}) sí aplica. "
                    "¿Me das tu número de 10 dígitos para avanzar?"
                )
            else:
                reply = (
                    f"La LADA {lada_match.group(1)} ({lada_info['ciudad']}) no está habilitada para portabilidad digital. "
                    "¿Tienes otro número o quieres info del CAC?"
                )
        else:
            reply = "No tengo registrada esa LADA. ¿Me compartes tu número completo de 10 dígitos?"
        return {"messages": [AIMessage(content=reply)]}

    _INFO_TRIGGERS = ["info", "información", "informacion"]
    _INTERESA_TRIGGERS = ["me interesa", "quiero saber", "me intereso"]
    _PRECIO_TRIGGERS = ["cuánto cuesta", "cuanto cuesta", "precio", "cuánto vale", "cuanto vale"]
    _ROBOT_TRIGGERS = ["eres robot", "eres humano", "eres persona", "eres una persona", "eres ia", "eres inteligencia"]
    _OFRECES_TRIGGERS = ["qué ofreces", "que ofreces", "qué hacen", "que hacen", "qué vendes", "que vendes"]

    if any(t in lower for t in _INFO_TRIGGERS):
        return {
            "messages": [AIMessage(content=(
                "Claro 😊 Te paso la info correcta según tu zona. "
                "¿Me compartes tu número de celular para ver qué promo aplica?"
            ))]
        }

    if any(t in lower for t in _INTERESA_TRIGGERS):
        return {
            "messages": [AIMessage(content=(
                "Perfecto 🙌 Para activarte la promo necesito tu número de celular. ¿Me lo compartes?"
            ))]
        }

    if any(t in lower for t in _PRECIO_TRIGGERS):
        return {
            "messages": [AIMessage(content=(
                "Depende de lo que recargas hoy. Con $50 o $100 puedes tener el triple de beneficios "
                "por 12 meses. ¿Me dices tu número para ver la promo exacta?"
            ))]
        }

    if any(t in lower for t in _ROBOT_TRIGGERS):
        return {
            "messages": [AIMessage(content=(
                "Soy Vera de Telcel, estoy aquí para ayudarte con tu portabilidad 😊 "
                "¿Me compartes tu número para ver qué promo aplica en tu zona?"
            ))]
        }

    if any(t in lower for t in _OFRECES_TRIGGERS):
        return {
            "messages": [AIMessage(content=(
                "Te ayudo a portarte a Telcel conservando tu mismo número y obtener "
                "el triple de beneficios en tus recargas por 12 meses 🎉 ¿Me compartes tu número?"
            ))]
        }

    # Input inválido (emoji, caracteres aleatorios, muy corto sin letras)
    alpha_count = sum(c.isalpha() for c in user_text)
    if len(user_text) < 4 or (alpha_count < 2 and not any(c.isdigit() for c in user_text)):
        return {
            "messages": [AIMessage(content=(
                "¡Hola! 👋 Soy Vera de Telcel. "
                "Para ayudarte con la portabilidad necesito tu número de 10 dígitos. ¿Cuál es?"
            ))]
        }

    # Ingeniería social / reclamo de autoridad falsa
    if any(p in lower for p in _SOCIAL_ENGINEERING):
        return {
            "messages": [AIMessage(content=(
                "Entiendo lo que comentas, pero no puedo procesar ese tipo de solicitudes. "
                "Solo opero con las promociones del catálogo oficial de Telcel. "
                "¿Te gustaría que te mostrara las promos disponibles?"
            ))],
        }

    # Mensaje general o primer contacto — usar Claude con catálogo y reglas
    llm = get_llm()
    is_first = len(messages) == 1

    instruction_saludo = (
        "Primer mensaje: usa el saludo estándar de GREETING_VARIANTS — incluye el hook "
        "'triple de beneficios en tus recargas por 12 meses' y pide el número de 10 dígitos."
        if is_first else
        "Responde al cliente y asegúrate de pedir su número de 10 dígitos al final si aún no lo tienes."
    )
    system = render_prompt(
        "validacion_general",
        SALES_APPROACH=SALES_APPROACH,
        ANTI_RENDICION=ANTI_RENDICION,
        ASL_CATALOG=ASL_CATALOG,
        CHANNEL_RULES=CHANNEL_RULES,
        PORTABILITY_SCHEDULE=PORTABILITY_SCHEDULE,
        CLARO_DRIVE_MUSICA=CLARO_DRIVE_MUSICA,
        ID_DOCS_INFO=ID_DOCS_INFO,
        HARD_RULES=HARD_RULES,
        FORMAT_RULES=FORMAT_RULES,
        GREETING_VARIANTS=GREETING_VARIANTS,
        instruction_saludo=instruction_saludo,
    )

    ai_msg = await llm.ainvoke([SystemMessage(content=system)] + list(messages))
    return {"messages": split_msg(ai_msg.content)}


async def validacion_node(state: PortabilidadState) -> dict:
    messages = state.get("messages") or []
    if not messages:
        return {}

    # Crear deal en Bitrix al primer contacto (no bloquea si falla)
    deal_update = await _crear_deal_primer_contacto(state)

    # Ejecutar lógica de validación y fusionar con el deal_id recién creado
    result = await _validacion_logic(state, messages)
    return {**deal_update, **result}

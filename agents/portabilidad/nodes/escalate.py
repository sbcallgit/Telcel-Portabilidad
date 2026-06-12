"""Nodo de escalamiento: handoff a asesor humano vía Bitrix24 Open Lines."""

import logging

from agents.portabilidad.state import PortabilidadState
from config.settings import settings

logger = logging.getLogger(__name__)


def _build_context(state: PortabilidadState) -> dict:
    datos = state.get("datos_lead") or {}
    return {
        "nombre": datos.get("nombre", ""),
        "numero_a_portar": datos.get("numero_a_portar", ""),
        "compania_donante": datos.get("compania_donante", ""),
        "municipio": datos.get("municipio", ""),
        "recarga_habitual": datos.get("recarga_habitual", "0"),
        "promo_elegida": state.get("promo_elegida", ""),
        "temperatura": state.get("temperatura", ""),
        "motivo_escalacion": state.get("motivo_escalacion", ""),
        "customer_phone": state.get("customer_phone", ""),
        "lada": state.get("lada", ""),
        "ciudad": state.get("ciudad", ""),
    }


_ESCALAMIENTO_MOTIVOS = {
    "solicitud_directa",
    "caso_sensible",
    "solicitud_arco",
    "telcel_a_telcel",
    "cambio_titularidad",
}
_SEGUIMIENTO_MOTIVOS = {
    "seguimiento",
    "max_objeciones_alcanzado",
}


def _resolve_stage(motivo: str) -> str:
    if motivo in _ESCALAMIENTO_MOTIVOS:
        return settings.bitrix_stage_escalamiento
    if motivo in _SEGUIMIENTO_MOTIVOS:
        return settings.bitrix_stage_seguimiento
    return settings.bitrix_stage_prospecto  # "cierre" y cualquier otro


async def _upsert_lead_kpis(context: dict, phone: str, deal_id: str) -> None:
    """Actualiza leads con KPIs completos tras el escalamiento."""
    from integrations.postgres import client as db

    datos = context
    nombre = datos.get("nombre", "")
    numero_a_portar = datos.get("numero_a_portar", "")
    compania_donante = datos.get("compania_donante", "")
    municipio = datos.get("municipio", "")
    promo_elegida = datos.get("promo_elegida", "")
    temperatura = datos.get("temperatura", "")
    recarga_str = str(datos.get("recarga_habitual") or "0")
    try:
        recarga = int(recarga_str) if recarga_str.isdigit() else 0
    except (ValueError, TypeError):
        recarga = 0

    try:
        await db.execute(
            """
            INSERT INTO leads (telefono, nombre, numero_a_portar, compania_donante,
                               municipio, recarga_habitual, temperatura, promo_elegida,
                               bitrix_lead_id, etapa)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'escalado')
            ON CONFLICT (telefono) DO UPDATE SET
                nombre           = EXCLUDED.nombre,
                numero_a_portar  = EXCLUDED.numero_a_portar,
                compania_donante = EXCLUDED.compania_donante,
                municipio        = EXCLUDED.municipio,
                recarga_habitual = EXCLUDED.recarga_habitual,
                temperatura      = EXCLUDED.temperatura,
                promo_elegida    = EXCLUDED.promo_elegida,
                bitrix_lead_id   = EXCLUDED.bitrix_lead_id,
                etapa            = 'escalado',
                updated_at       = NOW()
            """,
            phone, nombre, numero_a_portar, compania_donante,
            municipio, recarga, temperatura, promo_elegida, deal_id,
        )
    except Exception as exc:
        logger.warning("upsert_lead_kpis_error", extra={"phone_tail": phone[-4:], "error": str(exc)})


async def _try_bitrix(context: dict, phone: str, motivo: str, existing_deal_id: str = "") -> str:
    """Actualiza deal existente (o crea si no hay) con KPIs completos. Silencia errores."""
    if not settings.bitrix_webhook_url:
        logger.info("bitrix_skipped_not_configured")
        return existing_deal_id

    nombre = context.get("nombre", "")
    titulo = f"Portabilidad {nombre} *{phone[-4:]}" if nombre else f"Portabilidad *{phone[-4:]}"
    comments = (
        f"Teléfono: {phone}\n"
        f"Promo: {context.get('promo_elegida', '')}\n"
        f"Número a portar: {context.get('numero_a_portar', '')}\n"
        f"Compañía donante: {context.get('compania_donante', '')}\n"
        f"Municipio: {context.get('municipio', '')}\n"
        f"Temperatura: {context.get('temperatura', '')}"
    )

    try:
        from integrations.bitrix.client import BitrixClient
        bx = BitrixClient()

        if existing_deal_id:
            # Actualizar deal creado al primer contacto con KPIs completos
            await bx.actualizar_deal(
                deal_id=existing_deal_id,
                datos={
                    "TITLE": titulo,
                    "STAGE_ID": _resolve_stage(motivo),
                    "COMMENTS": comments,
                },
            )
            return existing_deal_id

        # Fallback: crear deal si no se creó al primer contacto
        result = await bx.crear_deal(
            telefono=phone,
            datos={"NAME": nombre, "COMMENTS": comments},
            stage_id=_resolve_stage(motivo),
        )
        return str(result.get("result", ""))
    except Exception as exc:
        logger.error("bitrix_error", extra={"error": str(exc)})
        return existing_deal_id


async def escalate_node(state: PortabilidadState) -> dict:
    # Evitar doble escalamiento — limpiar flag y dejar que _fin_node maneje el resto
    if state.get("etapa") == "fin":
        return {"escalate_to_human": False}

    context = _build_context(state)
    phone = state.get("customer_phone") or ""
    motivo = state.get("motivo_escalacion") or "cierre"

    # Actualizar deal existente (creado al primer contacto) con stage según motivo
    deal_id = await _try_bitrix(context, phone, motivo=motivo, existing_deal_id=state.get("bitrix_lead_id") or "")

    # Persistir KPIs en leads para el job de seguimientos
    await _upsert_lead_kpis(context, phone, deal_id)

    logger.info(
        "escalation_done",
        extra={
            "phone_tail": phone[-4:] if len(phone) >= 4 else phone,
            "motivo": motivo,
            "deal_id": deal_id,
        },
    )

    # El nodo fuente (sondeo, oferta, cierre, objeciones) ya envió su mensaje al usuario
    # cuando seteó escalate_to_human. escalate_node solo actualiza estado y Bitrix.
    return {
        "bitrix_lead_id": deal_id,
        "bitrix_etapa": "listo_para_portabilidad",
        "etapa": "fin",
        "escalate_to_human": False,
    }

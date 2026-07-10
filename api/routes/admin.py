"""Endpoints de administración — requieren X-Admin-Token."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import require_auth

router = APIRouter(prefix="/admin")
logger = logging.getLogger(__name__)

AuthDep = Annotated[None, Depends(require_auth)]


class SeguimientoTestRequest(BaseModel):
    telefono: str
    force: bool = False  # True = ignora la ventana de 30 min (solo para pruebas)


class VicidialTestRequest(BaseModel):
    telefono: str
    simulate: bool = False  # True = omite llamada real, simula éxito y mueve a C90:3


@router.post("/seguimiento-test")
async def trigger_seguimiento_test(
    body: SeguimientoTestRequest,
    _: AuthDep,
) -> JSONResponse:
    """Envía un seguimiento manual a un teléfono específico para validar antes de habilitar el job.

    Busca el lead en la BD por teléfono y dispara _enviar_seguimiento con el stage actual.
    Si el lead no existe, retorna 404.
    """

    from integrations.postgres import client as db
    from jobs.seguimientos import (
        STAGE_RESCATE1, STAGE_RESCATE2,
        _enviar_seguimiento, _generar_mensaje_rescate, _mover_a_rescate1, _mover_a_rescate2,
        minutos_desde_ultimo_mensaje,
    )

    telefono = body.telefono.strip()
    row = await db.fetchrow(
        """SELECT id, telefono, bitrix_stage, bitrix_lead_id,
                  COALESCE(seguimientos_enviados, 0) AS num,
                  ultimo_seguimiento,
                  nombre, compania_donante, recarga_habitual, promo_elegida, temperatura, municipio
           FROM leads WHERE telefono = $1""",
        telefono,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Lead no encontrado para teléfono {telefono}")

    lead_id = row["id"]
    bitrix_stage = row["bitrix_stage"] or "C90:NEW"
    deal_id = row["bitrix_lead_id"] or ""
    num_enviados = row["num"]
    es_rescate2 = bitrix_stage == STAGE_RESCATE1

    # Verificar ventana de silencio de 30 min
    minutos = await minutos_desde_ultimo_mensaje(telefono)
    minutos_str = round(minutos, 1) if minutos is not None else None

    if not body.force and minutos is not None and minutos < 30:
        return JSONResponse({
            "status": "bloqueado",
            "motivo": "usuario_activo_reciente",
            "minutos_desde_ultimo_mensaje": minutos_str,
            "minutos_requeridos": 30,
            "tip": "Usa force=true para ignorar la ventana en pruebas",
        })

    flujo = "rescate2" if es_rescate2 else "rescate1"
    logger.info("admin_seguimiento_test", extra={"telefono": telefono[-4:], "stage": bitrix_stage, "flujo": flujo, "force": body.force})

    try:
        lead_dict = dict(row)
        if es_rescate2:
            # Flujo Rescate 2: lead ya está en C90:1 → enviar mensaje y mover a C90:2
            texto = await _generar_mensaje_rescate(lead_dict, rescate=2)
            await _enviar_seguimiento(lead_id, telefono, texto, STAGE_RESCATE1, 0)
            if deal_id:
                await _mover_a_rescate2(lead_id, deal_id)
            await db.execute(
                "INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at) VALUES ($1, $2, 1, NOW())",
                lead_id, STAGE_RESCATE2,
            )
            bitrix_movido_a = STAGE_RESCATE2
        else:
            # Flujo Rescate 1: mover a C90:1
            texto = await _generar_mensaje_rescate(lead_dict, rescate=1)
            await _enviar_seguimiento(lead_id, telefono, texto, bitrix_stage, num_enviados)
            if deal_id:
                await _mover_a_rescate1(lead_id, deal_id)
            await db.execute(
                "INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at) VALUES ($1, $2, $3, NOW())",
                lead_id, bitrix_stage, num_enviados + 1,
            )
            bitrix_movido_a = STAGE_RESCATE1

        await db.execute(
            "UPDATE leads SET seguimientos_enviados = seguimientos_enviados + 1, ultimo_seguimiento = NOW(), updated_at = NOW() WHERE id = $1",
            lead_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({
        "status": "enviado",
        "flujo": flujo,
        "telefono": f"***{telefono[-4:]}",
        "bitrix_stage_anterior": bitrix_stage,
        "bitrix_movido_a": bitrix_movido_a if deal_id else "sin_deal_id",
        "mensaje_numero": num_enviados + 1,
        "minutos_desde_ultimo_mensaje": minutos_str,
    })


@router.post("/vicidial-test")
async def trigger_vicidial_test(
    body: VicidialTestRequest,
    _: AuthDep,
) -> JSONResponse:
    """Envía un lead a Vicidial y mueve el deal a C90:3.

    simulate=true: omite la llamada real a Vicidial, simula éxito y ejecuta
    todo el flujo (mover deal a C90:3, actualizar leads y seguimientos_log).
    """

    from integrations.postgres import client as db
    from integrations.vicidial.client import agregar_lead
    from jobs.seguimientos import STAGE_RESCATE3, _mover_a_rescate3

    telefono = body.telefono.strip()
    logger.info("admin_vicidial_test", extra={"phone_tail": telefono[-4:], "simulate": body.simulate})

    if body.simulate:
        exito, respuesta = True, "simulated"
    else:
        exito, respuesta = await agregar_lead(telefono)

    bitrix_movido_a = None
    if exito:
        row = await db.fetchrow(
            "SELECT id, bitrix_lead_id, bitrix_stage FROM leads WHERE telefono = $1",
            telefono,
        )
        if row and row["bitrix_lead_id"]:
            await _mover_a_rescate3(row["id"], row["bitrix_lead_id"])
            await db.execute(
                "INSERT INTO seguimientos_log (lead_id, etapa, numero_seq, enviado_at) VALUES ($1, $2, 1, NOW())",
                row["id"], STAGE_RESCATE3,
            )
            await db.execute(
                "UPDATE leads SET seguimientos_enviados = seguimientos_enviados + 1, ultimo_seguimiento = NOW(), updated_at = NOW() WHERE id = $1",
                row["id"],
            )
            bitrix_movido_a = STAGE_RESCATE3

    return JSONResponse({
        "status": "ok" if exito else "error",
        "telefono": f"***{telefono[-4:]}",
        "simulate": body.simulate,
        "vicidial_response": respuesta,
        "bitrix_movido_a": bitrix_movido_a,
    })


class CapiTestBody(BaseModel):
    telefono: str
    deal_id: str = "test_001"
    evento: str = "Purchase"   # Purchase | Lead
    recarga: float = 0.0
    simulate: bool = False


@router.post("/capi-test")
async def capi_test(_: AuthDep, body: CapiTestBody) -> JSONResponse:
    """Dispara manualmente un evento CAPI a Meta para validación."""
    from integrations.meta.conversions import send_purchase_event, send_lead_event
    from config.settings import settings

    if not settings.meta_pixel_id or not settings.meta_access_token:
        raise HTTPException(status_code=503, detail="Meta CAPI no configurado (falta META_PIXEL_ID o META_ACCESS_TOKEN)")

    if body.simulate:
        return JSONResponse({"status": "simulated", "pixel_id": settings.meta_pixel_id, "evento": body.evento})

    if body.evento == "Purchase":
        ok = await send_purchase_event(body.telefono, body.deal_id, recarga=body.recarga)
    else:
        from integrations.meta.conversions import send_lead_event
        ok = await send_lead_event(body.telefono, body.deal_id)

    return JSONResponse({"status": "ok" if ok else "error", "pixel_id": settings.meta_pixel_id, "evento": body.evento})


# ---------------------------------------------------------------------------
# Bitrix placement bind (one-time setup)
# ---------------------------------------------------------------------------

@router.post("/bitrix-placement-bind")
async def bitrix_placement_bind(_: AuthDep) -> JSONResponse:
    """Registra el placement handler 'Vera · Conversación' en Bitrix24.

    Ejecutar una sola vez tras completar el flujo OAuth (/bitrix/auth).
    Registra CRM_DEAL_DETAIL_TAB → /bitrix/deal-embed.
    """
    import httpx
    from config.settings import settings
    from integrations.bitrix.oauth import get_token

    try:
        token = await get_token()
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": f"No hay OAuth token. Ejecuta primero el flujo /bitrix/auth. ({exc})"},
            status_code=400,
        )

    domain = settings.bitrix_webhook_url.split("/rest/")[0].replace("https://", "")
    handler_url = f"{settings.bitrix_public_url}/bitrix/deal-embed"

    async with httpx.AsyncClient(timeout=10) as hx:
        r = await hx.post(
            f"https://{domain}/rest/placement.bind",
            params={"auth": token},
            json={
                "PLACEMENT": "CRM_DEAL_DETAIL_TAB",
                "HANDLER":   handler_url,
                "LANG_ALL":  {
                    "ru": {"TITLE": "Vera · Conversación"},
                    "en": {"TITLE": "Vera · Conversación"},
                    "es": {"TITLE": "Vera · Conversación"},
                },
            },
        )

    result = r.json()
    logger.info("bitrix_placement_bind", extra={"result": result, "handler": handler_url})
    return JSONResponse({"status": "ok", "handler": handler_url, "bitrix_result": result})


@router.post("/bitrix-bot-control-bind")
async def bitrix_bot_control_bind(_: AuthDep) -> JSONResponse:
    """Registra la pestaña 'Control Bot' en Bitrix24 (solo botón, para asesores).

    Ejecutar una sola vez. Requiere que el flujo OAuth (/bitrix/auth) ya esté completo.
    Registra CRM_DEAL_DETAIL_TAB → /bitrix/bot-control.
    """
    import httpx
    from config.settings import settings
    from integrations.bitrix.oauth import get_token

    try:
        token = await get_token()
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": f"No hay OAuth token. Ejecuta primero /bitrix/auth. ({exc})"},
            status_code=400,
        )

    domain = settings.bitrix_webhook_url.split("/rest/")[0].replace("https://", "")
    handler_url = f"{settings.bitrix_public_url}/bitrix/bot-control"

    async with httpx.AsyncClient(timeout=10) as hx:
        r = await hx.post(
            f"https://{domain}/rest/placement.bind",
            params={"auth": token},
            json={
                "PLACEMENT": "CRM_DEAL_DETAIL_TAB",
                "HANDLER":   handler_url,
                "LANG_ALL":  {
                    "ru": {"TITLE": "Control Bot"},
                    "en": {"TITLE": "Control Bot"},
                    "es": {"TITLE": "Control Bot"},
                },
            },
        )

    result = r.json()
    logger.info("bitrix_bot_control_bind", extra={"result": result, "handler": handler_url})
    return JSONResponse({"status": "ok", "handler": handler_url, "bitrix_result": result})

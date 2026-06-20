"""Endpoints de administración — requieren X-Admin-Token."""

import asyncio
import logging
import math
from decimal import Decimal
from datetime import date
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.settings import settings

router = APIRouter(prefix="/admin")
logger = logging.getLogger(__name__)


def _check_token(x_admin_token: str) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="forbidden")


class SeguimientoTestRequest(BaseModel):
    telefono: str
    force: bool = False  # True = ignora la ventana de 30 min (solo para pruebas)


class VicidialTestRequest(BaseModel):
    telefono: str
    simulate: bool = False  # True = omite llamada real, simula éxito y mueve a C90:3


@router.get("/kpi-data")
async def get_kpi_data(
    x_admin_token: str = Header(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    desde: Optional[date] = Query(None, description="Fecha ISO inicio (YYYY-MM-DD)"),
    hasta: Optional[date] = Query(None, description="Fecha ISO fin (YYYY-MM-DD)"),
    stage: Optional[str] = Query(None, description="Filtrar por estado_actual (ej. C90:WON)"),
    buscar: Optional[str] = Query(None, description="Búsqueda por teléfono o empleado"),
) -> JSONResponse:
    """Expone KPIs de kpi_conversaciones para el dashboard Angular."""
    _check_token(x_admin_token)

    from integrations.postgres import client as db

    filtros = []
    params: list = []
    idx = 1

    if desde:
        filtros.append(f"creado_el >= ${idx}::date")
        params.append(desde)
        idx += 1
    if hasta:
        filtros.append(f"creado_el < ${idx}::date + interval '1 day'")
        params.append(hasta)
        idx += 1
    if stage:
        filtros.append(f"estado_actual = ${idx}")
        params.append(stage)
        idx += 1
    if buscar:
        filtros.append(f"(telefono ILIKE ${idx} OR empleado ILIKE ${idx} OR resumen ILIKE ${idx})")
        params.append(f"%{buscar}%")
        idx += 1

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

    resumen_row = await db.fetchrow(
        f"""
        SELECT
            COUNT(*)                                                  AS total,
            COUNT(*) FILTER (WHERE estado_actual = 'C90:WON')        AS conversiones,
            ROUND(AVG(tiempo_primera_respuesta_segs) FILTER
                  (WHERE tiempo_primera_respuesta_segs IS NOT NULL
                     AND tiempo_primera_respuesta_segs > 0), 1)       AS avg_primera_resp,
            COALESCE(SUM(mensajes_cliente), 0)                        AS total_msgs_cliente,
            COALESCE(SUM(mensajes_bot), 0)                            AS total_msgs_bot,
            COALESCE(SUM(mensajes_humano), 0)                         AS total_msgs_humano,
            COUNT(*) FILTER (WHERE mensajes_humano > 0)               AS escalados
        FROM kpi_conversaciones {where}
        """,
        *params,
    )

    total = resumen_row["total"] or 0
    conversiones = resumen_row["conversiones"] or 0
    tasa = round(conversiones / total * 100, 1) if total > 0 else 0.0

    por_stage = await db.fetch(
        f"""
        SELECT estado_actual AS stage, COUNT(*) AS cantidad
        FROM kpi_conversaciones {where}
        GROUP BY estado_actual
        ORDER BY cantidad DESC
        """,
        *params,
    )

    offset = (page - 1) * page_size
    lista_params = params + [page_size, offset]
    conversaciones = await db.fetch(
        f"""
        SELECT
            id_conversacion, telefono, estado_actual, etapa, empleado,
            creado_el, cerrado_el, mensajes_cliente, mensajes_bot, mensajes_humano,
            tiempo_primera_respuesta_segs, resumen
        FROM kpi_conversaciones {where}
        ORDER BY creado_el DESC NULLS LAST
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *lista_params,
    )

    def _fmt(row: dict) -> dict:
        result = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                result[k] = v.isoformat()
            elif isinstance(v, Decimal):
                result[k] = float(v)
            else:
                result[k] = v
        return result

    return JSONResponse({
        "resumen": {
            "total_conversaciones": total,
            "conversiones": conversiones,
            "tasa_conversion": tasa,
            "avg_primera_respuesta_segs": float(resumen_row["avg_primera_resp"] or 0),
            "total_msgs_cliente": int(resumen_row["total_msgs_cliente"] or 0),
            "total_msgs_bot": int(resumen_row["total_msgs_bot"] or 0),
            "total_msgs_humano": int(resumen_row["total_msgs_humano"] or 0),
            "escalados": int(resumen_row["escalados"] or 0),
        },
        "por_stage": [{"stage": r["stage"] or "Sin stage", "cantidad": r["cantidad"]} for r in por_stage],
        "conversaciones": [_fmt(dict(r)) for r in conversaciones],
        "paginacion": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)),
        },
    })


@router.post("/kpi-export")
async def trigger_kpi_export(x_admin_token: str = Header(...)) -> JSONResponse:
    """Dispara el job de exportación de KPIs de forma inmediata.

    Corre en el mismo proceso FastAPI, con el checkpointer PostgreSQL y tokens
    OAuth ya activos. Útil para regenerar la tabla sin esperar las 3am.
    """
    _check_token(x_admin_token)

    from jobs.kpi_export import job_kpi_export

    logger.info("admin_kpi_export_triggered")
    asyncio.create_task(job_kpi_export())

    return JSONResponse({"status": "started", "message": "KPI export corriendo en background — revisa logs para progreso"})


@router.post("/seguimiento-test")
async def trigger_seguimiento_test(
    body: SeguimientoTestRequest,
    x_admin_token: str = Header(...),
) -> JSONResponse:
    """Envía un seguimiento manual a un teléfono específico para validar antes de habilitar el job.

    Busca el lead en la BD por teléfono y dispara _enviar_seguimiento con el stage actual.
    Si el lead no existe, retorna 404.
    """
    _check_token(x_admin_token)

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
    x_admin_token: str = Header(...),
) -> JSONResponse:
    """Envía un lead a Vicidial y mueve el deal a C90:3.

    simulate=true: omite la llamada real a Vicidial, simula éxito y ejecuta
    todo el flujo (mover deal a C90:3, actualizar leads y seguimientos_log).
    """
    _check_token(x_admin_token)

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

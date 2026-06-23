"""Endpoints de administración — requieren X-Admin-Token."""

import asyncio
import logging
import math
from decimal import Decimal
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Annotated

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


@router.get("/kpi-data")
async def get_kpi_data(
    _: AuthDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    desde: Optional[date] = Query(None, description="Fecha ISO inicio (YYYY-MM-DD)"),
    hasta: Optional[date] = Query(None, description="Fecha ISO fin (YYYY-MM-DD)"),
    stage: Optional[str] = Query(None, description="Filtrar por estado_actual (ej. C90:WON)"),
    buscar: Optional[str] = Query(None, description="Búsqueda por teléfono o empleado"),
) -> JSONResponse:
    """Expone KPIs de kpi_conversaciones para el dashboard Angular."""

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
async def trigger_kpi_export(_: AuthDep) -> JSONResponse:
    """Dispara el job de exportación de KPIs de forma inmediata.

    Corre en el mismo proceso FastAPI, con el checkpointer PostgreSQL y tokens
    OAuth ya activos. Útil para regenerar la tabla sin esperar las 3am.
    """

    from jobs.kpi_export import job_kpi_export

    logger.info("admin_kpi_export_triggered")
    asyncio.create_task(job_kpi_export())

    return JSONResponse({"status": "started", "message": "KPI export corriendo en background — revisa logs para progreso"})


@router.post("/bitrix-eventos-seed")
async def trigger_bitrix_eventos_seed(_: AuthDep) -> JSONResponse:
    """Pobla bitrix_eventos desde kpi_conversaciones existente (migración inicial).

    Seguro re-ejecutar — usa ON CONFLICT DO NOTHING.
    Para datos nuevos el job nocturno kpi_export los agrega automáticamente.
    """
    from jobs.kpi_eventos import seed_from_kpi_conversaciones

    logger.info("admin_bitrix_eventos_seed_triggered")
    asyncio.create_task(seed_from_kpi_conversaciones())

    return JSONResponse({"status": "started", "message": "Seed de bitrix_eventos corriendo en background — revisa logs para progreso"})


@router.post("/kpi-email")
async def trigger_kpi_email(_: AuthDep) -> JSONResponse:
    """Dispara el envío del reporte KPI por correo de forma inmediata."""

    from jobs.email_report import send_kpi_report

    logger.info("admin_kpi_email_triggered")
    asyncio.create_task(send_kpi_report())

    return JSONResponse({"status": "started", "message": "Reporte KPI enviando en background — revisa logs"})


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


@router.get("/meta-insights")
async def get_meta_insights(
    _: AuthDep,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    level: str = Query(default="campaign"),
) -> JSONResponse:
    """Ad Insights de Meta Marketing API — gasto, impresiones, clics, conversaciones WhatsApp."""
    from integrations.meta.insights import get_insights
    from config.settings import settings

    if not settings.meta_access_token or not settings.meta_ad_account_id:
        raise HTTPException(status_code=503, detail="Meta SDK no configurado")

    try:
        if desde and hasta:
            rows = await get_insights(
                date_preset=None,
                since=str(desde),
                until=str(hasta),
                level=level,
            )
        else:
            rows = await get_insights(date_preset="last_30d", level=level)

        total_spend = round(sum(r["spend"] for r in rows), 2)
        total_impressions = sum(r["impressions"] for r in rows)
        total_clicks = sum(r["clicks"] for r in rows)
        total_wa = sum(r["wa_conversaciones"] for r in rows)
        cpl = round(total_spend / total_wa, 2) if total_wa else None

        return JSONResponse({
            "resumen": {
                "total_spend":       total_spend,
                "total_impressions": total_impressions,
                "total_clicks":      total_clicks,
                "total_wa_convs":    total_wa,
                "cpl_wa":            cpl,
                "avg_ctr":           round(total_clicks / total_impressions * 100, 2) if total_impressions else 0,
            },
            "rows": sorted(rows, key=lambda r: r["spend"], reverse=True),
            "level": level,
        })
    except Exception as exc:
        logger.error("meta_insights_error", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail=f"Error Meta API: {exc}")


@router.get("/utm-data")
async def get_utm_data(
    _: AuthDep,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
) -> JSONResponse:
    """Atribución UTM / Click-to-WhatsApp desde la tabla leads."""
    from integrations.postgres import client as db
    from datetime import datetime, timezone as tz

    desde_ts = datetime(desde.year, desde.month, desde.day, 0, 0, 0, tzinfo=tz.utc) if desde \
        else datetime(2000, 1, 1, tzinfo=tz.utc)
    hasta_ts = datetime(hasta.year, hasta.month, hasta.day, 23, 59, 59, tzinfo=tz.utc) if hasta \
        else datetime(2099, 12, 31, 23, 59, 59, tzinfo=tz.utc)

    resumen = await db.fetchrow(
        """
        SELECT
            COUNT(*)                                                       AS total_leads,
            COUNT(*) FILTER (WHERE utm_source != '')                       AS con_utm,
            COUNT(*) FILTER (WHERE ctwa_clid != '')                        AS con_ctwa,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON')              AS total_ventas,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON'
                               AND utm_source != '')                       AS ventas_atribuidas
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
        """,
        desde_ts, hasta_ts,
    )

    por_campana = await db.fetch(
        """
        SELECT
            COALESCE(NULLIF(utm_campaign,''), '(sin campaña)') AS campana,
            COALESCE(NULLIF(utm_source,''),   '(sin fuente)')  AS fuente,
            COALESCE(NULLIF(utm_medium,''),   '(sin medio)')   AS medio,
            COUNT(*)                                           AS total,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON')  AS ventas,
            COUNT(*) FILTER (WHERE bitrix_stage IN ('C90:PROSPECTO','C90:WON')) AS prospectos
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
          AND utm_source != ''
        GROUP BY campana, fuente, medio
        ORDER BY total DESC
        LIMIT 20
        """,
        desde_ts, hasta_ts,
    )

    por_anuncio = await db.fetch(
        """
        SELECT
            ad_id,
            COALESCE(NULLIF(utm_campaign,''), '(sin campaña)') AS campana,
            COUNT(*)                                           AS total,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON')  AS ventas
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
          AND ad_id != ''
        GROUP BY ad_id, campana
        ORDER BY total DESC
        LIMIT 10
        """,
        desde_ts, hasta_ts,
    )

    por_fuente = await db.fetch(
        """
        SELECT
            COALESCE(NULLIF(utm_source,''), '(directo)') AS fuente,
            COUNT(*)                                     AS total,
            COUNT(*) FILTER (WHERE bitrix_stage = 'C90:WON') AS ventas
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
        GROUP BY fuente
        ORDER BY total DESC
        """,
        desde_ts, hasta_ts,
    )

    def _pct(num, den):
        return round(num / den * 100, 1) if den else 0.0

    r = dict(resumen) if resumen else {}
    total = int(r.get("total_leads") or 0)
    con_utm = int(r.get("con_utm") or 0)
    ventas = int(r.get("total_ventas") or 0)
    ventas_atrib = int(r.get("ventas_atribuidas") or 0)

    return JSONResponse({
        "resumen": {
            "total_leads":       total,
            "con_utm":           con_utm,
            "pct_con_utm":       _pct(con_utm, total),
            "total_ventas":      ventas,
            "ventas_atribuidas": ventas_atrib,
            "pct_ventas_atrib":  _pct(ventas_atrib, ventas),
        },
        "por_campana": [
            {
                "campana":    row["campana"],
                "fuente":     row["fuente"],
                "medio":      row["medio"],
                "total":      row["total"],
                "ventas":     row["ventas"],
                "prospectos": row["prospectos"],
                "tasa":       _pct(row["ventas"], row["total"]),
            }
            for row in por_campana
        ],
        "por_anuncio": [
            {
                "ad_id":   row["ad_id"],
                "campana": row["campana"],
                "total":   row["total"],
                "ventas":  row["ventas"],
                "tasa":    _pct(row["ventas"], row["total"]),
            }
            for row in por_anuncio
        ],
        "por_fuente": [
            {
                "fuente": row["fuente"],
                "total":  row["total"],
                "ventas": row["ventas"],
                "tasa":   _pct(row["ventas"], row["total"]),
            }
            for row in por_fuente
        ],
    })


@router.get("/megacable-data")
async def get_megacable_data(
    _: AuthDep,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
) -> JSONResponse:
    """KPIs del agente Megacable desde su BD externa."""
    from integrations.megacable_db import fetch_megacable
    from datetime import datetime, timezone as tz

    desde_ts = datetime(desde.year, desde.month, desde.day, 0, 0, 0, tzinfo=tz.utc) if desde \
        else datetime(2000, 1, 1, tzinfo=tz.utc)
    hasta_ts = datetime(hasta.year, hasta.month, hasta.day, 23, 59, 59, tzinfo=tz.utc) if hasta \
        else datetime(2099, 12, 31, 23, 59, 59, tzinfo=tz.utc)

    try:
        resumen_rows = await fetch_megacable(
            """
            SELECT
                COUNT(*)                                                        AS total,
                COUNT(*) FILTER (WHERE estado = 'cerrada')                      AS cerradas,
                COUNT(*) FILTER (WHERE estado = 'abierta')                      AS abiertas,
                COUNT(*) FILTER (WHERE escalated_at IS NOT NULL)                AS escaladas,
                COUNT(*) FILTER (WHERE agent_replied_at IS NOT NULL)            AS con_agente,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (agent_replied_at - created_at))
                ) FILTER (WHERE agent_replied_at IS NOT NULL)::numeric, 1)      AS avg_primera_resp_segs,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (closed_at - created_at))
                ) FILTER (WHERE closed_at IS NOT NULL)::numeric, 1)             AS avg_cierre_segs
            FROM conversations
            WHERE created_at >= $1 AND created_at <= $2
            """,
            desde_ts, hasta_ts,
        )

        por_estado = await fetch_megacable(
            """
            SELECT estado, COUNT(*) AS cantidad
            FROM conversations
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY estado ORDER BY cantidad DESC
            """,
            desde_ts, hasta_ts,
        )

        por_actor = await fetch_megacable(
            """
            SELECT actor, COUNT(*) AS cantidad
            FROM conversation_history ch
            JOIN conversations c ON c.conversation_id = ch.conversation_id
            WHERE c.created_at >= $1 AND c.created_at <= $2
            GROUP BY actor
            """,
            desde_ts, hasta_ts,
        )

        intents = await fetch_megacable(
            """
            SELECT intent, COUNT(*) AS cantidad
            FROM agent_runs
            WHERE created_at >= $1 AND created_at <= $2
              AND intent != ''
            GROUP BY intent ORDER BY cantidad DESC LIMIT 8
            """,
            desde_ts, hasta_ts,
        )

        conversaciones = await fetch_megacable(
            """
            SELECT
                c.conversation_id, c.phone, c.estado, c.empleado,
                c.created_at, c.closed_at, c.escalated_at,
                COUNT(*) FILTER (WHERE ch.actor = 'cliente') AS msgs_cliente,
                COUNT(*) FILTER (WHERE ch.actor = 'bot')     AS msgs_bot,
                COUNT(*) FILTER (WHERE ch.actor = 'humano')  AS msgs_humano
            FROM conversations c
            LEFT JOIN conversation_history ch ON ch.conversation_id = c.conversation_id
            WHERE c.created_at >= $1 AND c.created_at <= $2
            GROUP BY c.id, c.conversation_id, c.phone, c.estado, c.empleado,
                     c.created_at, c.closed_at, c.escalated_at
            ORDER BY c.created_at DESC
            LIMIT 50
            """,
            desde_ts, hasta_ts,
        )

        def _fmt(row: dict) -> dict:
            return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in row.items()}

        r = resumen_rows[0] if resumen_rows else {}
        return JSONResponse({
            "resumen": {
                "total": int(r.get("total") or 0),
                "cerradas": int(r.get("cerradas") or 0),
                "abiertas": int(r.get("abiertas") or 0),
                "escaladas": int(r.get("escaladas") or 0),
                "con_agente": int(r.get("con_agente") or 0),
                "avg_primera_resp_segs": float(r.get("avg_primera_resp_segs") or 0),
                "avg_cierre_segs": float(r.get("avg_cierre_segs") or 0),
            },
            "por_estado": [{"estado": x["estado"], "cantidad": x["cantidad"]} for x in por_estado],
            "por_actor": [{"actor": x["actor"], "cantidad": x["cantidad"]} for x in por_actor],
            "intents": [{"intent": x["intent"], "cantidad": x["cantidad"]} for x in intents],
            "conversaciones": [_fmt(c) for c in conversaciones],
        })
    except Exception as exc:
        logger.error("megacable_data_error", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail=f"Error conectando a BD Megacable: {exc}")

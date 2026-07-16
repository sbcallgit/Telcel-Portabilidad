"""Script de limpieza completa para un teléfono de prueba.

Uso:
    docker compose exec api python scripts/reset_test_phone.py <telefono>

Ejemplo:
    docker compose exec api python scripts/reset_test_phone.py 5218115131237

Limpia:
  - Redis: todas las llaves relacionadas al teléfono
  - PostgreSQL: checkpoints de LangGraph + leads + bitrix_eventos + bitrix_deal_timeline
    + kpi_conversaciones
  - Bitrix: deals, contacto y sesión de Open Lines
"""

import asyncio
import logging
import sys
from pathlib import Path

# Asegurar que el root del proyecto esté en el path cuando se corre desde /app/scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _variantes(phone: str) -> list[str]:
    """Genera variantes del teléfono para buscar en Bitrix y Redis."""
    phone = phone.strip().lstrip("+")
    variantes = {phone}
    # Con prefijo 52 (México)
    if phone.startswith("521"):
        variantes.add(phone[2:])   # sin 52 → 1XXXXXXXXXX
        variantes.add(phone[3:])   # sin 521 → XXXXXXXXXX
    elif phone.startswith("52"):
        variantes.add(phone[2:])   # sin 52 → XXXXXXXXXX
        variantes.add("1" + phone[2:])
    else:
        variantes.add("52" + phone)
        variantes.add("521" + phone)
    return list(variantes)


async def limpiar_redis(phone: str) -> None:
    import redis.asyncio as aioredis
    from config.settings import settings

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    # Normalizar igual que _variantes para que los patrones coincidan con las llaves reales
    variantes = _variantes(phone)
    total = 0
    prefijos = [
        "debounce:msgs",
        "debounce:token",
        "connector_ext_chat",
        "connector_session",
        "connector_chat",
        "connector_deal",
        "connector_last_msg",
        "bot_pausado",
    ]
    patrones = [f"{p}:{v}" for p in prefijos for v in variantes]
    for patron in patrones:  # los directos los borra sin SCAN
        n = await r.delete(patron)
        if n:
            log.info(f"  Redis DEL {patron}")
            total += n

    # connector_delivered tiene el message_id, no el phone — limpiar todos
    async for key in r.scan_iter("connector_delivered:*"):
        await r.delete(key)
        total += 1

    log.info(f"Redis: {total} llaves eliminadas para {phone}")
    await r.aclose()


async def limpiar_postgres(phone: str) -> None:
    import asyncpg
    from config.settings import settings

    conn = await asyncpg.connect(settings.database_dsn)
    variantes = _variantes(phone)

    # Checkpoints LangGraph — thread_id = phone (cualquier variante)
    cp_total = 0
    for v in variantes:
        for tabla in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            n = await conn.execute(f"DELETE FROM {tabla} WHERE thread_id = $1", v)
            cp_total += int(n.split()[-1])

    log.info(f"PostgreSQL checkpoints: {cp_total} filas eliminadas")

    # Tablas dependientes de leads (foreign keys) y luego leads
    leads_total = 0
    for v in variantes:
        lead_ids = await conn.fetch("SELECT id FROM leads WHERE telefono = $1", v)
        for row in lead_ids:
            lid = row["id"]
            await conn.execute("DELETE FROM seguimientos_log WHERE lead_id = $1", lid)
            await conn.execute("DELETE FROM seguimientos_fallidos WHERE lead_id = $1", lid)
        n = await conn.execute("DELETE FROM leads WHERE telefono = $1", v)
        leads_total += int(n.split()[-1])

    log.info(f"PostgreSQL leads: {leads_total} filas eliminadas")

    # Tablas de trazabilidad de eventos
    ev_total = 0
    tl_total = 0
    for v in variantes:
        n = await conn.execute(
            "DELETE FROM bitrix_eventos WHERE id_conversacion = $1 OR telefono = $1", v
        )
        ev_total += int(n.split()[-1])
        n = await conn.execute(
            "DELETE FROM bitrix_deal_timeline WHERE id_conversacion = $1 OR telefono = $1", v
        )
        tl_total += int(n.split()[-1])

    log.info(f"PostgreSQL bitrix_eventos: {ev_total} filas eliminadas")
    log.info(f"PostgreSQL bitrix_deal_timeline: {tl_total} filas eliminadas")

    # Snapshot de KPIs (job_kpi_export nocturno)
    kpi_total = 0
    for v in variantes:
        n = await conn.execute(
            "DELETE FROM kpi_conversaciones WHERE id_conversacion = $1", v
        )
        kpi_total += int(n.split()[-1])

    log.info(f"PostgreSQL kpi_conversaciones: {kpi_total} filas eliminadas")

    await conn.close()


async def limpiar_bitrix(phone: str) -> None:
    from integrations.bitrix.client import BitrixClient
    from integrations.bitrix.connector import _call as connector_call

    bitrix = BitrixClient()
    variantes = _variantes(phone)

    # 1. Buscar contacto por teléfono (todas las variantes)
    contact_ids: list[str] = []
    for v in variantes:
        try:
            r = await bitrix._call("crm.duplicate.findbycomm", {
                "type": "PHONE",
                "values": [v],
                "entity_type": "CONTACT",
            })
            ids = r.get("result", {})
            if isinstance(ids, dict):
                contact_ids += [str(i) for i in ids.get("CONTACT", [])]
        except Exception as exc:
            log.warning(f"  crm.duplicate.findbycomm({v}): {exc}")

    contact_ids = list(set(contact_ids))
    log.info(f"Bitrix contactos encontrados: {contact_ids}")

    # 2. Buscar deals por contacto y por título (last 4 digits)
    deal_ids: set[str] = set()
    tail = phone[-4:]

    for cid in contact_ids:
        try:
            r = await bitrix._call("crm.deal.list", {
                "filter": {"CONTACT_ID": cid, "CATEGORY_ID": "90"},
                "select": ["ID"],
            })
            for d in r.get("result", []):
                deal_ids.add(str(d["ID"]))
        except Exception as exc:
            log.warning(f"  crm.deal.list(contact={cid}): {exc}")

    # Búsqueda por título como fallback
    try:
        r = await bitrix._call("crm.deal.list", {
            "filter": {"%TITLE": tail, "CATEGORY_ID": "90"},
            "select": ["ID"],
        })
        for d in r.get("result", []):
            deal_ids.add(str(d["ID"]))
    except Exception as exc:
        log.warning(f"  crm.deal.list(title): {exc}")

    log.info(f"Bitrix deals encontrados: {list(deal_ids)}")

    # 3. Cerrar sesión Open Lines antes de borrar el deal
    import redis.asyncio as aioredis
    from config.settings import settings

    r_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    session_id = await r_client.get(f"connector_session:{phone}")
    await r_client.aclose()

    if session_id:
        try:
            await connector_call("imopenlines.session.close", {"SESSION_ID": session_id})
            log.info(f"Open Lines sesión {session_id} cerrada")
        except Exception as exc:
            log.warning(f"  imopenlines.session.close: {exc}")

    # 4. Eliminar deals
    for did in deal_ids:
        try:
            await bitrix._call("crm.deal.delete", {"id": did})
            log.info(f"  Deal {did} eliminado")
        except Exception as exc:
            log.warning(f"  crm.deal.delete({did}): {exc}")

    # 5. Eliminar contactos
    for cid in contact_ids:
        try:
            await bitrix._call("crm.contact.delete", {"id": cid})
            log.info(f"  Contacto {cid} eliminado")
        except Exception as exc:
            log.warning(f"  crm.contact.delete({cid}): {exc}")


async def main(phone: str) -> None:
    log.info(f"=== Reset teléfono: {phone} ===")
    log.info("Variantes: " + ", ".join(_variantes(phone)))

    await limpiar_redis(phone)
    await limpiar_postgres(phone)
    await limpiar_bitrix(phone)

    log.info("=== Limpieza completada ===")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/reset_test_phone.py <telefono>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))

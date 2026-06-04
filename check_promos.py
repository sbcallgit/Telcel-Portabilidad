import asyncio, sys
sys.path.insert(0, "/app")

async def main():
    from integrations.postgres.client import create_pool, close_pool
    await create_pool()
    from integrations.postgres import client as db
    rows = await db.fetch("SELECT nombre, recarga, vigencia FROM promos WHERE activa=true ORDER BY recarga, nombre")
    for r in rows:
        d = dict(r)
        print("  %4s  %s  vence %s" % (d["recarga"], d["nombre"], d["vigencia"]))
    print("\nTotal activas: %d" % len(rows))
    await close_pool()

asyncio.run(main())

#!/usr/bin/env python3
"""Setup único del conector personalizado de WhatsApp en Bitrix24.

Uso:
  python scripts/setup_imconnector.py              # setup completo (4 pasos)
  python scripts/setup_imconnector.py --list-lines # lista Open Channels disponibles
  python scripts/setup_imconnector.py --status     # verifica el estado del conector

Requisito previo: los tokens OAuth deben estar guardados en Redis.
Completar primero el flujo de autorización abriendo en el navegador:
  https://b24-ahyle8.bitrix24.mx/oauth/authorize/?client_id=<CLIENT_ID>&response_type=code&redirect_uri=https://portabilidad.callcomcc.io/bitrix/app
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def list_lines() -> None:
    from integrations.bitrix.connector import list_open_lines
    from integrations.redis_client import get_redis

    await get_redis()
    lines = await list_open_lines()
    if not lines:
        print("No se encontraron Open Channels o hubo un error.")
        return

    print(f"\n=== Open Channels disponibles ({len(lines)}) ===")
    for line in lines:
        line_id = line.get("ID") or line.get("id", "?")
        name = line.get("NAME") or line.get("name", "Sin nombre")
        active = line.get("ACTIVE", line.get("active", "?"))
        print(f"  ID: {line_id} | Nombre: {name} | Activo: {active}")
    print(f"\nCopiar el ID deseado y asignarlo a BITRIX_CONNECTOR_LINE_ID en .env")


async def check_status() -> None:
    from integrations.bitrix.connector import get_connector_status
    from integrations.redis_client import get_redis

    await get_redis()
    status = await get_connector_status()
    print(f"\n=== Estado del conector ===")
    result = status.get("result", status)
    for k, v in (result.items() if isinstance(result, dict) else [("raw", result)]):
        print(f"  {k}: {v}")


async def full_setup() -> None:
    from config.settings import settings
    from integrations.bitrix.connector import (
        activate_line,
        register_connector,
        set_connector_data,
        subscribe_event,
    )
    from integrations.redis_client import get_redis

    await get_redis()

    if not settings.bitrix_client_id:
        print("❌ BITRIX_CLIENT_ID no configurado en .env")
        sys.exit(1)

    if not settings.bitrix_connector_line_id:
        print("❌ BITRIX_CONNECTOR_LINE_ID no configurado en .env")
        print("   Ejecuta primero: python scripts/setup_imconnector.py --list-lines")
        sys.exit(1)

    connector_webhook = f"{settings.bitrix_public_url}/webhooks/connector"

    print(f"\n=== Setup del conector '{settings.bitrix_connector_id}' ===\n")

    print("[1/4] Registrando conector...")
    ok = await register_connector()
    print(f"   Resultado: {ok}")

    print(f"[2/4] Activando en línea {settings.bitrix_connector_line_id}...")
    ok = await activate_line(settings.bitrix_connector_line_id)
    print(f"   Resultado: {ok}")

    print("[3/4] Configurando datos del conector...")
    ok = await set_connector_data()
    print(f"   Resultado: {ok}")

    print(f"[4/4] Suscribiendo ONIMCONNECTORMESSAGEADD → {connector_webhook}...")
    ok = await subscribe_event(connector_webhook)
    print(f"   Resultado: {ok}")

    print(f"\n✅ Setup completo. El conector 'WhatsApp Vera Bot' está activo en Bitrix24.")
    print(f"   Verifica en: Contact Center → Línea {settings.bitrix_connector_line_id} → Cola")


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup del conector WhatsApp en Bitrix24")
    parser.add_argument("--list-lines", action="store_true", help="Lista Open Channels disponibles")
    parser.add_argument("--status", action="store_true", help="Verifica el estado del conector")
    args = parser.parse_args()

    if args.list_lines:
        asyncio.run(list_lines())
    elif args.status:
        asyncio.run(check_status())
    else:
        asyncio.run(full_setup())


if __name__ == "__main__":
    main()

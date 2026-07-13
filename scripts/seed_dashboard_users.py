"""Crea los usuarios iniciales del dashboard KPI.

Uso: docker compose exec api python scripts/seed_dashboard_users.py
"""

import asyncio
import bcrypt

USERS = [
    {"email": "sbecerra@callcom.mx",  "nombre": "Sergio Becerra",  "password": "Callcom.2025"},
    {"email": "passpace04@gmail.com",  "nombre": "L. Salazar",      "password": "Callcom.2025"},
    {"email": "mbecerra@callcom.mx",  "nombre": "M. Becerra",       "password": "Callcom.2025"},
]


async def main() -> None:
    from integrations.postgres.client import create_pool, close_pool
    from integrations.postgres import client as db

    await create_pool()
    for u in USERS:
        h = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
        await db.execute(
            """
            INSERT INTO dashboard_users (email, nombre, password_hash)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO UPDATE
              SET nombre = EXCLUDED.nombre,
                  password_hash = EXCLUDED.password_hash,
                  activo = TRUE
            """,
            u["email"], u["nombre"], h,
        )
        print(f"✓ {u['email']}")
    await close_pool()
    print("Usuarios creados correctamente.")


if __name__ == "__main__":
    asyncio.run(main())

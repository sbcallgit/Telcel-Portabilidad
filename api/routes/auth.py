"""Endpoints de autenticación para el dashboard KPI."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import bcrypt
from jose import jwt
from pydantic import BaseModel

from config.settings import settings
from integrations.postgres import client as db

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    email: str
    password: str


def _create_token(email: str, nombre: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode(
        {"sub": email, "name": nombre, "exp": expire},
        settings.jwt_secret,
        algorithm="HS256",
    )


@router.post("/login")
async def login(body: LoginRequest) -> JSONResponse:
    email = body.email.strip().lower()
    row = await db.fetchrow(
        "SELECT id, email, nombre, password_hash, activo FROM dashboard_users WHERE email = $1",
        email,
    )
    pw_ok = bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()) if row else False
    if not row or not row["activo"] or not pw_ok:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    await db.execute(
        "UPDATE dashboard_users SET last_login = NOW() WHERE id = $1", row["id"]
    )
    token = _create_token(row["email"], row["nombre"])
    logger.info("dashboard_login", extra={"email": email})
    return JSONResponse({"access_token": token, "token_type": "bearer", "nombre": row["nombre"]})


@router.get("/me")
async def me(authorization: str = "") -> JSONResponse:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
        return JSONResponse({"email": payload.get("sub"), "nombre": payload.get("name")})
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

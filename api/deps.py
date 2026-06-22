"""Dependencias compartidas de FastAPI."""

from fastapi import Header, HTTPException


async def require_auth(
    x_admin_token: str = Header(default=""),
    authorization: str = Header(default=""),
) -> None:
    """Acepta X-Admin-Token (acceso programático) o Bearer JWT (dashboard)."""
    from config.settings import settings

    if x_admin_token and x_admin_token == settings.admin_token:
        return

    if authorization.startswith("Bearer "):
        try:
            from jose import jwt, JWTError
            jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
            return
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="forbidden")

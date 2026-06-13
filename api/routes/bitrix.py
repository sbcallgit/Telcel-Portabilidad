"""Endpoints para el flujo OAuth de Bitrix24.

GET  /bitrix/app     → recibe el ?code= del redirect OAuth y guarda tokens
POST /bitrix/install → hook de instalación de la app (requerido por Bitrix24)
"""

import logging

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from integrations.bitrix.oauth import exchange_code

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/bitrix/app", response_class=HTMLResponse)
async def bitrix_oauth_callback(code: str = Query(default="")) -> str:
    """Recibe el código de autorización OAuth y lo intercambia por tokens."""
    if not code:
        logger.warning("bitrix_oauth_no_code")
        return "<h3>Error: no se recibió código de autorización.</h3>"

    try:
        await exchange_code(code)
        logger.info("bitrix_oauth_callback_ok")
        return (
            "<h3>✅ Autorización exitosa.</h3>"
            "<p>Los tokens de Bitrix24 se guardaron correctamente.</p>"
            "<p>Puedes cerrar esta ventana.</p>"
        )
    except Exception as exc:
        # No reflejar la excepción al navegador (puede contener detalles del backend
        # o de la respuesta OAuth). El detalle queda solo en logs server-side.
        logger.error("bitrix_oauth_callback_error", extra={"error": str(exc)})
        return (
            "<h3>❌ Error al autorizar.</h3>"
            "<p>No se pudo completar la autorización. Revisa los logs del servidor.</p>"
        )


@router.post("/bitrix/install")
async def bitrix_install_hook() -> dict:
    """Hook requerido por Bitrix24 al instalar la app local."""
    logger.info("bitrix_app_install_hook")
    return {"status": "ok"}

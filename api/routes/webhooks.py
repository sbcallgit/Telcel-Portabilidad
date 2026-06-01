import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from config.settings import settings
from integrations.whatsapp.handlers import verify_webhook_signature

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/webhooks/telcel", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> str:
    """Verificación del webhook de Meta (handshake inicial)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("webhook_verified")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhooks/telcel", status_code=200)
async def receive_message(request: Request) -> dict:
    """Recibe mensajes de WhatsApp. Valida firma y encola para procesamiento."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if settings.whatsapp_app_secret:
        if not verify_webhook_signature(body, signature, settings.whatsapp_app_secret):
            logger.warning("webhook_signature_invalid")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # TODO Día 3: encolar en Redis con arq para procesamiento por el agente
    logger.info("webhook_message_received", extra={"bytes": len(body)})
    return {"status": "queued"}

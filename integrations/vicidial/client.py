"""Cliente para la API de Vicidial — agrega leads al marcador predictivo."""

import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


async def agregar_lead(phone: str) -> tuple[bool, str]:
    """Envía el lead al marcador predictivo Vicidial vía GET.

    Retorna (éxito, respuesta_texto).
    El teléfono se envía como los últimos 10 dígitos (formato local sin código de país).
    """
    phone_local = phone[-10:] if len(phone) > 10 else phone

    params = {
        "vendor_lead_code": "test",
        "source": "n8n",
        "user": settings.vicidial_user,
        "pass": settings.vicidial_pass,
        "function": "add_lead",
        "phone_number": phone_local,
        "list_id": settings.vicidial_list_id,
        "campaign_id": settings.vicidial_campaign_id,
    }

    try:
        # verify configurable: el modo inseguro (verify=False) es opt-in explícito
        # vía VICIDIAL_VERIFY_TLS, no el default. Evita MITM silencioso.
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, verify=settings.vicidial_verify_tls
        ) as client:
            r = await client.get(settings.vicidial_url, params=params)
            r.raise_for_status()
            texto = r.text.strip()
            logger.info(
                "vicidial_lead_agregado",
                extra={"phone_tail": phone[-4:], "status": r.status_code, "response": texto[:100]},
            )
            return True, texto
    except Exception as exc:
        logger.error("vicidial_error", extra={"phone_tail": phone[-4:], "error": str(exc)})
        return False, str(exc)

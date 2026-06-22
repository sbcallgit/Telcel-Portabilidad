"""Consulta de Ad Insights desde Meta Marketing API via facebook-business SDK."""

import asyncio
import logging
from functools import lru_cache

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

from config.settings import settings

logger = logging.getLogger(__name__)

_INSIGHT_FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_name",
    "ad_id",
    "ad_name",
    "impressions",
    "reach",
    "clicks",
    "spend",
    "cpc",
    "cpm",
    "ctr",
    "actions",
    "cost_per_action_type",
]

# Tipos de acción que representan conversaciones WhatsApp iniciadas
_WA_ACTION_TYPES = {
    "onsite_conversion.total_messaging_connection",
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_first_reply",
}


def _init_api() -> None:
    # Solo token de acceso — sin appsecret_proof para evitar conflicto con otras apps configuradas
    FacebookAdsApi.init(access_token=settings.meta_access_token)


def _extract_action(actions: list, action_types: set) -> int:
    """Suma valores de los action_types especificados."""
    return sum(
        int(a.get("value", 0))
        for a in (actions or [])
        if a.get("action_type") in action_types
    )


def _fetch_insights_sync(date_preset: str | None, since: str | None, until: str | None, level: str) -> list[dict]:
    _init_api()
    account = AdAccount(settings.meta_ad_account_id)

    params: dict = {"level": level}
    if date_preset:
        params["date_preset"] = date_preset
    elif since and until:
        params["time_range"] = {"since": since, "until": until}
    else:
        params["date_preset"] = "last_30d"

    insights = account.get_insights(fields=_INSIGHT_FIELDS, params=params)

    results = []
    for row in insights:
        row_dict = dict(row)
        actions = row_dict.pop("actions", []) or []
        cost_per_action = row_dict.pop("cost_per_action_type", []) or []

        wa_convs = _extract_action(actions, _WA_ACTION_TYPES)
        cpa_wa = next(
            (float(x["value"]) for x in cost_per_action
             if x.get("action_type") in _WA_ACTION_TYPES),
            None,
        )

        results.append({
            "campaign_id":   row_dict.get("campaign_id", ""),
            "campaign_name": row_dict.get("campaign_name", ""),
            "adset_name":    row_dict.get("adset_name", ""),
            "ad_id":         row_dict.get("ad_id", ""),
            "ad_name":       row_dict.get("ad_name", ""),
            "impressions":   int(row_dict.get("impressions", 0)),
            "reach":         int(row_dict.get("reach", 0)),
            "clicks":        int(row_dict.get("clicks", 0)),
            "spend":         round(float(row_dict.get("spend", 0)), 2),
            "cpc":           round(float(row_dict.get("cpc", 0)), 2),
            "cpm":           round(float(row_dict.get("cpm", 0)), 2),
            "ctr":           round(float(row_dict.get("ctr", 0)), 2),
            "wa_conversaciones": wa_convs,
            "cpa_wa":        round(cpa_wa, 2) if cpa_wa else None,
        })

    return results


async def get_insights(
    date_preset: str | None = "last_30d",
    since: str | None = None,
    until: str | None = None,
    level: str = "campaign",
) -> list[dict]:
    """Obtiene insights de la cuenta de anuncios de forma async (ejecuta en executor)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _fetch_insights_sync,
        date_preset, since, until, level,
    )

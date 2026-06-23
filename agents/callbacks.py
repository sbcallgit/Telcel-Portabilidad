"""Callback handler para capturar uso de tokens de cada llamada al LLM.

Al finalizar cada ainvoke(), almacena los tokens en Redis con clave
`token_pending:{thread_id}` (TTL 5 min). log_mensaje_evento() en kpi_eventos.py
lee esa clave al insertar el mensaje del bot en bitrix_eventos, guardando
tokens_entrada, tokens_salida y costo_usd directamente en esa fila.

Precios OpenRouter para anthropic/claude-sonnet-4-5 (junio 2026):
  Input:  $3.00 / 1M tokens
  Output: $15.00 / 1M tokens
"""

import json
import logging

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

_PRICE_INPUT_PER_TOKEN  = 3.00  / 1_000_000
_PRICE_OUTPUT_PER_TOKEN = 15.00 / 1_000_000
_REDIS_TTL = 300  # 5 minutos — tiempo máximo entre ainvoke y log_mensaje_evento


class TokenUsageCallback(AsyncCallbackHandler):
    """Captura token_usage al finalizar cada llamada al LLM y lo deposita en Redis."""

    def __init__(self, thread_id: str = "", node_name: str = "", model: str = "claude-sonnet-4-5"):
        self.thread_id = thread_id
        self.node_name = node_name
        self.model = model

    async def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        try:
            token_usage = (response.llm_output or {}).get("token_usage", {})
            input_tokens  = int(token_usage.get("prompt_tokens", 0))
            output_tokens = int(token_usage.get("completion_tokens", 0))
            if not input_tokens and not output_tokens:
                return

            cost_usd = round(
                input_tokens  * _PRICE_INPUT_PER_TOKEN +
                output_tokens * _PRICE_OUTPUT_PER_TOKEN,
                8,
            )

            from integrations.redis_client import get_redis
            redis = await get_redis()
            await redis.setex(
                f"token_pending:{self.thread_id}",
                _REDIS_TTL,
                json.dumps({
                    "input_tokens":  input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd":      cost_usd,
                    "node_name":     self.node_name,
                }),
            )
            logger.debug(
                "token_pending_stored",
                extra={
                    "thread_id": self.thread_id,
                    "node": self.node_name,
                    "input": input_tokens,
                    "output": output_tokens,
                    "cost_usd": cost_usd,
                },
            )
        except Exception as exc:
            logger.warning("token_usage_callback_error", extra={"error": str(exc)})

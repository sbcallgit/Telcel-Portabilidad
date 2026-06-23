"""Callback handler para capturar uso de tokens de cada llamada al LLM.

Registra input_tokens, output_tokens y costo estimado en USD por nodo y
conversación en la tabla `token_usage` de PostgreSQL.

Precios OpenRouter para anthropic/claude-sonnet-4-5 (junio 2026):
  Input:  $3.00 / 1M tokens
  Output: $15.00 / 1M tokens
"""

import logging

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

_PRICE_INPUT_PER_TOKEN  = 3.00  / 1_000_000
_PRICE_OUTPUT_PER_TOKEN = 15.00 / 1_000_000


class TokenUsageCallback(AsyncCallbackHandler):
    """Captura token_usage al finalizar cada llamada al LLM y lo persiste en PostgreSQL."""

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

            from integrations.postgres import client as db
            await db.execute(
                """
                INSERT INTO token_usage
                    (thread_id, node_name, model, input_tokens, output_tokens, cost_usd)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                self.thread_id, self.node_name, self.model,
                input_tokens, output_tokens, cost_usd,
            )
            logger.debug(
                "token_usage_recorded",
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

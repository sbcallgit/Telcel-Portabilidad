"""Factory del modelo de lenguaje via OpenRouter.

OpenRouter expone una API compatible con OpenAI, así que usamos ChatOpenAI
apuntando a https://openrouter.ai/api/v1. El modelo se configura en .env
(OPENROUTER_MODEL) para poder cambiar entre modelos sin tocar el código.

Modelos recomendados en OpenRouter para este proyecto:
  anthropic/claude-sonnet-4-5   → mejor balance calidad/costo
  anthropic/claude-haiku-4-5    → más rápido y barato (para pruebas)
  openai/gpt-4o-mini             → alternativa económica
"""

from langchain_openai import ChatOpenAI

from config.settings import settings

_llm_instance: ChatOpenAI | None = None


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Retorna la instancia de ChatOpenAI configurada para OpenRouter.

    Singleton lazy: se crea en el primer uso para que el contenedor arranque
    sin error aunque OPENROUTER_API_KEY esté vacío en desarrollo.
    Lanza ValueError si la API key no está configurada.
    """
    global _llm_instance
    if _llm_instance is None:
        if not settings.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY no está configurado en .env. "
                "Obtén tu key en https://openrouter.ai/keys"
            )
        _llm_instance = ChatOpenAI(
            model=settings.openrouter_model,
            openai_api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
            openai_api_base=settings.openrouter_base_url,
            temperature=temperature,
            max_tokens=1024,
            default_headers={
                "HTTP-Referer": "https://github.com/bot-telcel-portabilidad",
                "X-Title": "Bot Telcel Portabilidad R4",
            },
        )
    return _llm_instance

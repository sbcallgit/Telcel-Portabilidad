from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # WhatsApp Business
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Bitrix24
    bitrix_webhook_url: str = ""
    bitrix_pipeline_id: str = ""

    # Chatwoot
    chatwoot_api_key: str = ""
    chatwoot_base_url: str = ""
    chatwoot_inbox_id: str = ""

    # PostgreSQL
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "portabilidad"
    db_user: str = "bot"
    db_password: str = "botpassword"

    # Redis
    redis_url: str = "redis://redis:6379"

    # OpenRouter (LLM gateway — compatible con API de OpenAI)
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4-5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Telegram (para pruebas — no requiere aprobación de Meta)
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "tg_webhook_secret_dev"

    # App
    app_version: str = "1.0.0"
    environment: str = "development"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()

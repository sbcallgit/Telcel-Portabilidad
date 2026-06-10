from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # WhatsApp Business
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Bitrix24 — webhook REST (CRM básico)
    bitrix_webhook_url: str = ""
    bitrix_pipeline_id: str = ""

    # Bitrix24 — OAuth + conector personalizado (Open Lines)
    bitrix_client_id: str = ""
    bitrix_client_secret: str = ""
    bitrix_connector_id: str = "whatsapp_vera"
    bitrix_connector_line_id: str = ""
    bitrix_stage_ia_porta: str = "C90:NEW"        # Primer contacto — bot activo
    bitrix_stage_prospecto: str = "C90:PROSPECTO"  # KPIs completos — listo para portabilidad
    bitrix_stage_seguimiento: str = "C90:SEGUIMIENTO"  # Quiere ser contactado después
    bitrix_stage_escalamiento: str = "C90:UC_8WB2DT"   # Solicita asesor humano ahora
    bitrix_stage_listo: str = "C90:PROSPECTO"      # alias de compatibilidad → prospecto
    bitrix_public_url: str = "https://portabilidad.callcomcc.io"

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

    # Qdrant (vector database — RAG de objeciones)
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Debounce de mensajes WhatsApp (ms; 0 = desactivado)
    debounce_window_ms: int = 1500

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

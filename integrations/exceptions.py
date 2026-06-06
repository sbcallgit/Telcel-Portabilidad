class IntegrationError(Exception):
    """Base para todos los errores de integración."""

    def __init__(self, message: str, *, retriable: bool = False, original: Exception | None = None):
        super().__init__(message)
        self.retriable = retriable
        self.original = original


class WhatsAppError(IntegrationError):
    """Error al comunicarse con la API de WhatsApp Business."""


class BitrixError(IntegrationError):
    """Error al comunicarse con Bitrix24."""


class DatabaseError(IntegrationError):
    """Error al comunicarse con PostgreSQL."""

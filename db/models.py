from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator


class IncomingWhatsAppMessage(BaseModel):
    phone: str
    body: str
    message_id: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) not in (10, 12, 13):
            raise ValueError("Teléfono debe tener 10 dígitos (o formato E.164)")
        return v

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        if len(v) > 4096:
            raise ValueError("El mensaje excede 4096 caracteres")
        return v


class Lead(BaseModel):
    nombre: str = ""
    telefono: str
    numero_a_portar: str = ""
    compania_donante: str = ""
    municipio: str = ""
    recarga_habitual: int = 0
    temperatura: Literal["caliente", "tibio", "frio", ""] = ""
    promo_elegida: str = ""
    bitrix_lead_id: str = ""


class Lada(BaseModel):
    lada: str
    ciudad: str
    estado: str
    habilitada: bool


class Promo(BaseModel):
    nombre: str
    recarga: int
    beneficios: str
    vigencia: date
    condicion: str


class CAC(BaseModel):
    nombre: str
    direccion: str
    municipio: str
    estado: str
    lat: float
    lng: float
    horario: str


class EquipoDesbloqueo(BaseModel):
    marca: str
    modelo: str
    requiere_desbloqueo: bool


class Objecion(BaseModel):
    texto: str
    categoria: str
    respuesta: str

"""DDL para crear todas las tablas del sistema.

Ejecutar una vez al iniciar en un ambiente nuevo, o usar Alembic para migraciones versionadas.
"""

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS ladas (
    id SERIAL PRIMARY KEY,
    lada VARCHAR(5) NOT NULL UNIQUE,
    ciudad VARCHAR(100) NOT NULL,
    estado VARCHAR(100) NOT NULL,
    habilitada BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS promos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    recarga INTEGER NOT NULL,
    beneficios TEXT NOT NULL,
    vigencia DATE NOT NULL,
    condicion TEXT NOT NULL DEFAULT '',
    activa BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cacs (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    direccion TEXT NOT NULL,
    municipio VARCHAR(100) NOT NULL,
    estado VARCHAR(100) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    horario VARCHAR(200) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS equipos_desbloqueo (
    id SERIAL PRIMARY KEY,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(200) NOT NULL,
    requiere_desbloqueo BOOLEAN NOT NULL DEFAULT false,
    UNIQUE(marca, modelo)
);

CREATE TABLE IF NOT EXISTS objeciones (
    id SERIAL PRIMARY KEY,
    texto TEXT NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    respuesta TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    telefono VARCHAR(20) NOT NULL,
    nombre VARCHAR(200) NOT NULL DEFAULT '',
    numero_a_portar VARCHAR(20) NOT NULL DEFAULT '',
    compania_donante VARCHAR(100) NOT NULL DEFAULT '',
    municipio VARCHAR(100) NOT NULL DEFAULT '',
    recarga_habitual INTEGER NOT NULL DEFAULT 0,
    temperatura VARCHAR(20) NOT NULL DEFAULT '',
    promo_elegida VARCHAR(200) NOT NULL DEFAULT '',
    bitrix_lead_id VARCHAR(50) NOT NULL DEFAULT '',
    etapa VARCHAR(50) NOT NULL DEFAULT 'validacion',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seguimientos_fallidos (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) UNIQUE,
    error TEXT NOT NULL,
    intentos INTEGER NOT NULL DEFAULT 0,
    ultimo_intento TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    requiere_revision BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS seguimientos_log (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    etapa VARCHAR(50) NOT NULL DEFAULT '',
    numero_seq INTEGER NOT NULL DEFAULT 1,
    enviado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS seguimientos_enviados INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ultimo_seguimiento TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS paquetes_asl (
    id SERIAL PRIMARY KEY,
    monto INTEGER NOT NULL UNIQUE,
    datos_mb INTEGER NOT NULL DEFAULT 0,
    vigencia_dias INTEGER NOT NULL,
    redes_ilimitadas BOOLEAN NOT NULL DEFAULT false,
    bolsa_redes_mb INTEGER NOT NULL DEFAULT 0,
    redes_bolsa TEXT NOT NULL DEFAULT '',
    whatsapp_ilimitado BOOLEAN NOT NULL DEFAULT true,
    amazon_prime TEXT,
    claro_musica_mb INTEGER NOT NULL DEFAULT 0,
    claro_drive_gb INTEGER NOT NULL DEFAULT 0,
    notas TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

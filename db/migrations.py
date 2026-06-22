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

-- Tabla de KPIs de conversaciones para exportación a BI (aislada del agente)
CREATE TABLE IF NOT EXISTS kpi_conversaciones (
    id SERIAL PRIMARY KEY,
    id_conversacion TEXT NOT NULL UNIQUE,
    id_contacto TEXT NOT NULL DEFAULT '',
    id_negociacion TEXT NOT NULL DEFAULT '',
    telefono TEXT NOT NULL DEFAULT '',
    pipeline TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL DEFAULT '',
    primer_mensaje TEXT NOT NULL DEFAULT '',
    tipo_mensaje TEXT NOT NULL DEFAULT 'Entrante',
    estado_actual TEXT NOT NULL DEFAULT '',
    etapa TEXT NOT NULL DEFAULT '',
    empleado TEXT NOT NULL DEFAULT '',
    mensajes_totales INTEGER NOT NULL DEFAULT 0,
    mensajes_cliente INTEGER NOT NULL DEFAULT 0,
    mensajes_bot INTEGER NOT NULL DEFAULT 0,
    mensajes_humano INTEGER NOT NULL DEFAULT 0,
    creado_el TIMESTAMPTZ,
    primera_respuesta TIMESTAMPTZ,
    el_bot_respondio_el TIMESTAMPTZ,
    solicitud_enviada_al_agente_el TIMESTAMPTZ,
    el_agente_respondio_el TIMESTAMPTZ,
    cerrado_el TIMESTAMPTZ,
    tiempo_primera_respuesta_segs NUMERIC,
    tiempo_promedio_respuestas_segs NUMERIC,
    tiempo_maximo_respuesta_segs NUMERIC,
    tiempo_cierre_segs NUMERIC,
    texto_usuario TEXT NOT NULL DEFAULT '',
    texto_agente TEXT NOT NULL DEFAULT '',
    texto_humano TEXT NOT NULL DEFAULT '',
    resumen TEXT NOT NULL DEFAULT '',
    fecha_extraccion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Columnas de texto y resumen (para instancias existentes)
ALTER TABLE kpi_conversaciones
  ADD COLUMN IF NOT EXISTS texto_usuario TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS texto_agente  TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS texto_humano  TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS resumen       TEXT NOT NULL DEFAULT '';

-- Seguimientos: stage de Bitrix en leads + unicidad de teléfono
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS bitrix_stage VARCHAR(50) NOT NULL DEFAULT '';

CREATE UNIQUE INDEX IF NOT EXISTS leads_telefono_uq ON leads(telefono);

-- Atribución UTM / Click-to-WhatsApp
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS utm_source   TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS utm_medium   TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS utm_campaign TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS utm_content  TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS utm_term     TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS ctwa_clid    TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS ad_id        TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS referral_source_url TEXT NOT NULL DEFAULT '';

-- Usuarios del dashboard KPI
CREATE TABLE IF NOT EXISTS dashboard_users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
"""

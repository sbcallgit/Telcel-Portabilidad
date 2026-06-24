# Estructura de tablas — Bot Telcel Portabilidad

Base de datos: **PostgreSQL 16** · Nombre: `portabilidad`

---

## Índice

1. [Base de conocimiento](#1-base-de-conocimiento)
2. [Operación del bot](#2-operación-del-bot)
3. [Memoria conversacional (LangGraph)](#3-memoria-conversacional-langgraph)
4. [KPIs y trazabilidad](#4-kpis-y-trazabilidad)
5. [Autenticación](#5-autenticación)
6. [Relaciones entre tablas](#6-relaciones-entre-tablas)

---

## 1. Base de conocimiento

Tablas de solo lectura durante la conversación. Se poblan con `make seed` y se actualizan manualmente cuando cambian las promos, LADAs o CACs.

### `ladas`

Prefijos telefónicos habilitados para portabilidad digital en Región 4.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `lada` | VARCHAR(5) UNIQUE | Prefijo de 3 dígitos (ej. `818`) |
| `ciudad` | VARCHAR(100) | Ciudad o zona asociada |
| `estado` | VARCHAR(100) | Estado de la república |
| `habilitada` | BOOLEAN | `true` = acepta portabilidad digital; `false` = deriva a CAC |
| `created_at` | TIMESTAMPTZ | — |

**Quién la usa:** `validacion_node` → `_query_lada()` para decidir si el número aplica.

---

### `promos`

Catálogo de paquetes ASL vigentes por monto de recarga.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `nombre` | VARCHAR(200) | Nombre comercial de la promo |
| `recarga` | INTEGER | Monto de recarga en MXN |
| `beneficios` | TEXT | Descripción completa de los beneficios |
| `vigencia` | DATE | Fecha de expiración de la promo |
| `condicion` | TEXT | Condiciones especiales (ej. solo portabilidad) |
| `activa` | BOOLEAN | `false` = no se presenta al cliente |
| `created_at` | TIMESTAMPTZ | — |

**Quién la usa:** `sondeo_node` y `oferta_node` para presentar la promo correcta según recarga.

---

### `paquetes_asl`

Detalle técnico de los paquetes Amigo Sin Límite por monto. Complementa `promos` con campos estructurados para el catálogo del agente.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `monto` | INTEGER UNIQUE | Monto de recarga en MXN |
| `datos_mb` | INTEGER | Datos de navegación en MB |
| `vigencia_dias` | INTEGER | Días de vigencia del paquete |
| `redes_ilimitadas` | BOOLEAN | ¿Redes sociales ilimitadas? |
| `bolsa_redes_mb` | INTEGER | MB de bolsa para redes (si no son ilimitadas) |
| `redes_bolsa` | TEXT | Redes incluidas en la bolsa |
| `whatsapp_ilimitado` | BOOLEAN | WhatsApp sin consumir datos |
| `amazon_prime` | TEXT | Descripción del beneficio Amazon Prime (si aplica) |
| `claro_musica_mb` | INTEGER | MB dedicados a Claro Música |
| `claro_drive_gb` | INTEGER | GB de Claro Drive incluidos |
| `notas` | TEXT | Notas adicionales |
| `created_at` | TIMESTAMPTZ | — |

---

### `cacs`

Directorio de Centros de Atención al Cliente de Región 4.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `nombre` | VARCHAR(200) | Nombre del CAC |
| `direccion` | TEXT | Dirección completa |
| `municipio` | VARCHAR(100) | Municipio |
| `estado` | VARCHAR(100) | Estado |
| `lat` | DOUBLE PRECISION | Latitud GPS |
| `lng` | DOUBLE PRECISION | Longitud GPS |
| `horario` | VARCHAR(200) | Horario de atención |
| `created_at` | TIMESTAMPTZ | — |

**Quién la usa:** `validacion_node` → `_get_cacs_by_city()` cuando el cliente pide dirección.

---

### `equipos_desbloqueo`

Catálogo de equipos y si requieren desbloqueo previo a la portabilidad.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `marca` | VARCHAR(100) | Marca del equipo |
| `modelo` | VARCHAR(200) | Modelo del equipo |
| `requiere_desbloqueo` | BOOLEAN | `true` = necesita desbloqueo antes de portar |

---

### `objeciones`

Banco de objeciones con respuestas sugeridas. También indexado en Qdrant para RAG semántico.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `texto` | TEXT | Texto de la objeción del cliente |
| `categoria` | VARCHAR(100) | Categoría (precio, cobertura, contrato, etc.) |
| `respuesta` | TEXT | Respuesta sugerida para Vera |
| `created_at` | TIMESTAMPTZ | — |

**Quién la usa:** `objeciones_node` como fallback cuando Qdrant no encuentra resultado con score ≥ 0.4.

---

## 2. Operación del bot

### `leads`

Una fila por número de teléfono. Fuente de verdad operativa para seguimientos y sincronización con Bitrix.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `telefono` | VARCHAR(20) UNIQUE | Número del remitente (ej. `521XXXXXXXXXX`) |
| `nombre` | VARCHAR(200) | Nombre capturado en cierre |
| `numero_a_portar` | VARCHAR(20) | Número que el cliente quiere portar |
| `compania_donante` | VARCHAR(100) | Operador actual del cliente |
| `municipio` | VARCHAR(100) | Municipio del cliente |
| `recarga_habitual` | INTEGER | Monto de recarga mensual en MXN |
| `temperatura` | VARCHAR(20) | `caliente` / `tibio` / `frío` |
| `promo_elegida` | VARCHAR(200) | Nombre de la promo presentada |
| `bitrix_lead_id` | VARCHAR(50) | ID del deal en Bitrix24 pipeline 90 |
| `etapa` | VARCHAR(50) | Etapa del agente: `validacion`, `sondeo`, `oferta`, `escalado`, `fin` |
| `bitrix_stage` | VARCHAR(50) | Stage actual en Bitrix (sincronizado por `job_bitrix_sync` cada 30 min) |
| `seguimientos_enviados` | INTEGER | Contador acumulado de mensajes de rescate enviados |
| `ultimo_seguimiento` | TIMESTAMPTZ | Timestamp del último rescate enviado |
| `utm_source` | TEXT | UTM source del anuncio de origen |
| `utm_medium` | TEXT | UTM medium |
| `utm_campaign` | TEXT | UTM campaign |
| `utm_content` | TEXT | UTM content |
| `utm_term` | TEXT | UTM term |
| `ctwa_clid` | TEXT | Click-to-WhatsApp Click ID de Meta |
| `ad_id` | TEXT | ID del anuncio de origen (`referral.source_id`) |
| `referral_source_url` | TEXT | URL completa del anuncio con UTMs |
| `created_at` | TIMESTAMPTZ | Primer contacto |
| `updated_at` | TIMESTAMPTZ | Última modificación |

**Quién la usa:**
- `validacion_node` → `_upsert_lead_primer_contacto()` al primer mensaje
- `escalate_node` → `_upsert_lead_kpis()` al completar KPIs
- `job_seguimientos` → consulta leads activos para enviar rescates
- `job_bitrix_sync` → actualiza `bitrix_stage` cada 30 min

---

### `seguimientos_log`

Registro histórico de cada mensaje de rescate enviado.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `lead_id` | INTEGER FK → `leads.id` | Lead al que se envió |
| `etapa` | VARCHAR(50) | Stage de Bitrix al momento del envío |
| `numero_seq` | INTEGER | Número de seguimiento (1, 2, 3…) |
| `enviado_at` | TIMESTAMPTZ | Cuándo se envió |

---

### `seguimientos_fallidos`

Rescates que no pudieron enviarse (WhatsApp rechazó el mensaje o error de red).

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `lead_id` | INTEGER FK → `leads.id` UNIQUE | Un registro por lead |
| `error` | TEXT | Descripción del error |
| `intentos` | INTEGER | Cantidad de reintentos fallidos |
| `ultimo_intento` | TIMESTAMPTZ | Timestamp del último intento |
| `requiere_revision` | BOOLEAN | Marcado para revisión manual |

---

## 3. Memoria conversacional (LangGraph)

Gestionadas automáticamente por `langgraph-checkpoint-postgres`. No se modifican manualmente. Se crean con `checkpointer.setup()` al arrancar la API.

| Tabla | Descripción |
|---|---|
| `checkpoints` | Estado completo del agente por `thread_id` (= teléfono). Una fila por checkpoint. |
| `checkpoint_blobs` | Blobs binarios del estado (mensajes, datos del lead). |
| `checkpoint_writes` | Escrituras pendientes entre checkpoints. |
| `checkpoint_migrations` | Control de versiones del schema del checkpointer. |

**`thread_id`:** `phone` en WhatsApp, `str(chat_id)` en Telegram.

**Nota:** al reactivar un deal `C90:LOSE`, se borran los checkpoints del teléfono (`DELETE FROM checkpoints WHERE thread_id = $1`) para que la conversación empiece limpia.

---

## 4. KPIs y trazabilidad

### `kpi_conversaciones`

Una fila por conversación. Tabla aislada del agente — no la leen los nodos. Se popula por `job_kpi_export` (cron 3am) o via `POST /admin/kpi-export`.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `id_conversacion` | TEXT UNIQUE | `thread_id` del agente (teléfono o `tg_...`) |
| `id_contacto` | TEXT | ID del contacto en Bitrix |
| `id_negociacion` | TEXT | ID del deal en Bitrix |
| `telefono` | TEXT | Número del lead |
| `pipeline` | TEXT | Nombre del pipeline (`C90`) |
| `origen` | TEXT | `SOURCE_ID` del deal en Bitrix |
| `primer_mensaje` | TEXT | Texto del primer mensaje del cliente |
| `tipo_mensaje` | TEXT | `Entrante` / `Saliente` |
| `estado_actual` | TEXT | Stage actual del deal en Bitrix (`C90:NEW`, `C90:WON`, etc.) |
| `etapa` | TEXT | Etapa del agente al momento de la extracción |
| `empleado` | TEXT | ID del asesor asignado al deal |
| `mensajes_totales` | INTEGER | Total de mensajes en la conversación |
| `mensajes_cliente` | INTEGER | Mensajes enviados por el cliente |
| `mensajes_bot` | INTEGER | Mensajes enviados por Vera |
| `mensajes_humano` | INTEGER | Mensajes enviados por el asesor humano |
| `creado_el` | TIMESTAMPTZ | Timestamp del primer checkpoint LangGraph |
| `primera_respuesta` | TIMESTAMPTZ | Primera respuesta del bot (Bitrix) |
| `el_bot_respondio_el` | TIMESTAMPTZ | Timestamp de la primera respuesta de Vera |
| `solicitud_enviada_al_agente_el` | TIMESTAMPTZ | Pendiente v2 |
| `el_agente_respondio_el` | TIMESTAMPTZ | Primera respuesta del asesor humano |
| `cerrado_el` | TIMESTAMPTZ | `CLOSEDATE` del deal en Bitrix |
| `tiempo_primera_respuesta_segs` | NUMERIC | Segundos entre mensaje del cliente y primera respuesta del bot |
| `tiempo_promedio_respuestas_segs` | NUMERIC | Tiempo promedio de respuesta |
| `tiempo_maximo_respuesta_segs` | NUMERIC | Tiempo máximo de respuesta |
| `tiempo_cierre_segs` | NUMERIC | Segundos desde primer mensaje hasta cierre |
| `texto_usuario` | TEXT | Todos los mensajes del cliente concatenados con `\n---\n` |
| `texto_agente` | TEXT | Todos los mensajes de Vera concatenados |
| `texto_humano` | TEXT | Todos los mensajes del asesor concatenados |
| `resumen` | TEXT | Resumen LLM de 3 oraciones: qué quería, cómo respondió, resultado |
| `motivo_escalacion` | TEXT | Motivo del escalamiento (`telcel_a_telcel`, `cierre`, `seguimiento`, etc.) |
| `rescates_enviados` | INTEGER | Cantidad de mensajes de rescate enviados |
| `fecha_nuevo` | TIMESTAMPTZ | Primera vez en `C90:NEW` |
| `fecha_prospecto` | TIMESTAMPTZ | Primera vez en `C90:PROSPECTO` |
| `fecha_escalamiento` | TIMESTAMPTZ | Primera vez en `C90:UC_8WB2DT` |
| `fecha_seguimiento` | TIMESTAMPTZ | Primera vez en `C90:SEGUIMIENTO` |
| `fecha_rescate1` | TIMESTAMPTZ | Primera vez en `C90:1` |
| `fecha_rescate2` | TIMESTAMPTZ | Primera vez en `C90:2` |
| `fecha_rescate3` | TIMESTAMPTZ | Primera vez en `C90:3` |
| `fecha_won` | TIMESTAMPTZ | Primera vez en `C90:WON` |
| `fecha_lose` | TIMESTAMPTZ | Primera vez en `C90:LOSE` |
| `tipificacion` | TEXT | Tipificación de cierre/caída del asesor |
| `tiempo_bot_a_prospecto_segs` | NUMERIC | Segundos desde primer mensaje hasta `C90:PROSPECTO` |
| `tiempo_prospecto_a_won_segs` | NUMERIC | Segundos desde `C90:PROSPECTO` hasta `C90:WON` |
| `fecha_extraccion` | TIMESTAMPTZ | Cuándo se corrió el kpi_export |

---

### `bitrix_eventos`

Un registro por evento del canal Bitrix Open Lines: mensajes (usuario / bot / asesor) y cambios de stage. Permite reconstruir el timeline completo de cada deal.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | BIGSERIAL PK | — |
| `id_conversacion` | TEXT | `thread_id` del agente |
| `deal_id` | TEXT | ID del deal en Bitrix |
| `chat_id` | TEXT | ID interno del chat en Bitrix IM |
| `telefono` | TEXT | Número del lead |
| `bitrix_conversation_id` | TEXT | ID de sesión Open Lines (ej. `IMOL_2602658`) |
| `message_id` | TEXT | ID del mensaje en Bitrix (`stage_{id}_{ts}` para cambios de stage) |
| `fecha_evento` | TIMESTAMPTZ | Timestamp exacto del evento |
| `tipo_actor` | TEXT | `usuario` / `bot` / `humano` / `sistema` |
| `texto` | TEXT | Contenido del mensaje o descripción del cambio de stage |
| `stage_id` | TEXT | Stage vigente en el momento del evento |
| `stage_nombre` | TEXT | Nombre legible del stage |
| `empleado_id` | TEXT | ID del asesor asignado |
| `stage_anterior` | TEXT | Stage previo (solo eventos `sistema`) |
| `stage_anterior_nombre` | TEXT | Nombre legible del stage anterior |
| `duracion_en_stage_segs` | NUMERIC | Segundos en `stage_anterior` antes de esta transición |
| `duracion_formateada` | TEXT | Formato legible: `"8m 48s"`, `"1h 22m 05s"` |
| `ultimo_mensaje_usuario` | TEXT | Último texto del cliente al momento del cambio de stage |
| `fecha_ultimo_usuario` | TIMESTAMPTZ | Timestamp de ese mensaje |
| `ultimo_mensaje_bot` | TEXT | Última respuesta de Vera al momento del cambio (sin prefijo `🤖 Vera \|`) |
| `fecha_ultimo_bot` | TIMESTAMPTZ | Timestamp de esa respuesta |
| `ultimo_mensaje_humano` | TEXT | Último mensaje del asesor al momento del cambio |
| `fecha_ultimo_humano` | TIMESTAMPTZ | Timestamp de ese mensaje |
| `canal` | TEXT | Canal de origen (`whatsapp` / `telegram`) |
| `wa_message_id` | TEXT | ID del mensaje en WhatsApp Cloud API |
| `autor_bitrix_id` | TEXT | ID del autor en Bitrix IM |
| `tokens_entrada` | INTEGER | Tokens de entrada del LLM en este turno (solo mensajes bot) |
| `tokens_salida` | INTEGER | Tokens de salida del LLM |
| `costo_usd` | NUMERIC(12,8) | Costo estimado en USD del turno LLM |
| `created_at` | TIMESTAMPTZ | Cuándo se insertó el registro |

**Índices:** `id_conversacion`, `deal_id`, `fecha_evento DESC`, `tipo_actor`, `stage_id`.
**Constraint único:** `(id_conversacion, message_id, tipo_actor)`.

---

### `bitrix_deal_timeline`

Una fila por deal. Pivote de stages: cuándo entró a cada etapa y cuánto tiempo pasó en ella. Se popula automáticamente desde `POST /bitrix/stage-event` (webhook de automatización Bitrix).

| Columna | Tipo | Descripción |
|---|---|---|
| `deal_id` | TEXT PK | ID del deal en Bitrix |
| `id_conversacion` | TEXT | `thread_id` del agente |
| `telefono` | TEXT | Número del lead |
| `fecha_new` | TIMESTAMPTZ | Primera entrada a `C90:NEW` |
| `duracion_new_segs` | NUMERIC | Segundos en `C90:NEW` |
| `fecha_prospecto` | TIMESTAMPTZ | Primera entrada a `C90:PROSPECTO` |
| `duracion_prospecto_segs` | NUMERIC | Segundos en `C90:PROSPECTO` |
| `fecha_escalamiento` | TIMESTAMPTZ | Primera entrada a `C90:UC_8WB2DT` |
| `duracion_escalamiento_segs` | NUMERIC | Segundos en escalamiento |
| `fecha_seguimiento` | TIMESTAMPTZ | Primera entrada a `C90:SEGUIMIENTO` |
| `duracion_seguimiento_segs` | NUMERIC | Segundos en seguimiento |
| `fecha_rescate1` | TIMESTAMPTZ | Primera entrada a `C90:1` |
| `duracion_rescate1_segs` | NUMERIC | Segundos en Rescate 1 |
| `fecha_rescate2` | TIMESTAMPTZ | Primera entrada a `C90:2` |
| `duracion_rescate2_segs` | NUMERIC | Segundos en Rescate 2 |
| `fecha_rescate3` | TIMESTAMPTZ | Primera entrada a `C90:3` |
| `duracion_rescate3_segs` | NUMERIC | Segundos en Rescate 3 |
| `fecha_won` | TIMESTAMPTZ | Primera entrada a `C90:WON` |
| `duracion_won_segs` | NUMERIC | — |
| `fecha_lose` | TIMESTAMPTZ | Primera entrada a `C90:LOSE` |
| `duracion_lose_segs` | NUMERIC | — |
| `fecha_recuperacion` | TIMESTAMPTZ | Primera entrada a `C90:8` / `C90:PREPAYMENT_INVOIC` |
| `duracion_recuperacion_segs` | NUMERIC | Segundos en recuperación |
| `empleado_id` | TEXT | Asesor asignado (se actualiza en cada cambio de stage) |
| `updated_at` | TIMESTAMPTZ | Último upsert |

**Regla de upsert:** `fecha_*` se preserva con `COALESCE` (primera entrada no se sobreescribe). `duracion_*` y `empleado_id` siempre se actualizan.

---

## 5. Autenticación

### `dashboard_users`

Usuarios con acceso al dashboard KPI Angular.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | — |
| `email` | TEXT UNIQUE | Correo del usuario |
| `nombre` | TEXT | Nombre para mostrar |
| `password_hash` | TEXT | Hash bcrypt de la contraseña |
| `activo` | BOOLEAN | `false` = acceso revocado |
| `created_at` | TIMESTAMPTZ | — |
| `last_login` | TIMESTAMPTZ | Último acceso exitoso |

**Seed:** `docker compose exec api python scripts/seed_dashboard_users.py`

---

## 6. Relaciones entre tablas

```
leads (1) ──────────────< seguimientos_log (N)
leads (1) ──────────────  seguimientos_fallidos (1)

leads.bitrix_lead_id ──── bitrix_deal_timeline.deal_id  (join por deal_id)
leads.telefono ─────────  checkpoints.thread_id          (join por teléfono)
leads.telefono ─────────  bitrix_eventos.telefono        (join por teléfono)

kpi_conversaciones.id_conversacion ── checkpoints.thread_id   (misma clave)
kpi_conversaciones.id_negociacion  ── bitrix_deal_timeline.deal_id
bitrix_eventos.deal_id             ── bitrix_deal_timeline.deal_id
```

### Consultas de cruce útiles

```sql
-- Conversación completa de un teléfono: KPIs + eventos + timeline
SELECT k.estado_actual, k.mensajes_cliente, k.mensajes_bot, k.resumen,
       t.fecha_new, t.fecha_prospecto, t.fecha_won, t.empleado_id
FROM kpi_conversaciones k
JOIN bitrix_deal_timeline t ON t.deal_id = k.id_negociacion
WHERE k.telefono = '521XXXXXXXXXX';

-- Todos los mensajes de un deal ordenados cronológicamente
SELECT fecha_evento, tipo_actor, stage_nombre, texto
FROM bitrix_eventos
WHERE deal_id = '2302394'
ORDER BY fecha_evento;

-- Leads con conversación en el bot pero sin deal en timeline (posibles huecos)
SELECT l.telefono, l.bitrix_lead_id, l.bitrix_stage
FROM leads l
LEFT JOIN bitrix_deal_timeline t ON t.deal_id = l.bitrix_lead_id
WHERE t.deal_id IS NULL AND l.bitrix_lead_id != '';

-- Funnel de conversión agregado
SELECT
  COUNT(*) FILTER (WHERE fecha_new IS NOT NULL)       AS new,
  COUNT(*) FILTER (WHERE fecha_prospecto IS NOT NULL) AS prospecto,
  COUNT(*) FILTER (WHERE fecha_won IS NOT NULL)       AS won,
  COUNT(*) FILTER (WHERE fecha_lose IS NOT NULL)      AS lose,
  ROUND(COUNT(*) FILTER (WHERE fecha_won IS NOT NULL)::NUMERIC
    / NULLIF(COUNT(*) FILTER (WHERE fecha_new IS NOT NULL), 0) * 100, 1) AS tasa_cierre_pct
FROM bitrix_deal_timeline;
```

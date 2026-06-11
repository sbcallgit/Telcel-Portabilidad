# Bot Telcel Portabilidad — Documentación del Proyecto

**Campaña:** Muévete Prepago · Región 4
**Canal:** WhatsApp Business (solo texto)
**Origen de leads:** Meta Ads (Click-to-WhatsApp)
**CRM:** Bitrix24

---

## Stack

| Componente | Tecnología | Propósito |
|---|---|---|
| API | FastAPI + Python 3.12 | Webhook de WhatsApp, endpoints de control |
| Agente | LangGraph + Claude (Anthropic) | Orquestación del flujo de venta |
| Base de datos | PostgreSQL 16 | Leads, conversaciones, base de conocimiento, checkpoints |
| Caché / Cola | Redis 7 + arq | Contexto de sesión y cola de mensajes |
| Memoria conversacional | `langgraph-checkpoint-postgres` + `psycopg` | Checkpoints persistentes del agente (sobrevive reinicios) |
| Memoria semántica | Qdrant + fastembed | RAG vectorial para objeciones (modelo multilingüe local) |
| Jobs | APScheduler | Seguimientos automáticos |
| CRM | Bitrix24 | Pipeline operativo y tipificaciones |
| Escalamiento | Bitrix24 Open Lines | Handoff al asesor humano (imconnector) |

---

## Estructura de carpetas

```
bot_telcel_portabilidad/
├── prompts/                 # System prompts del agente (archivos .txt editables)
│   ├── horarios.txt             # Respuestas a preguntas de horario de portación (compartido)
│   ├── validacion_general.txt   # Primer contacto y mensaje general (validacion)
│   ├── sondeo_con_recarga.txt   # Presentación de oferta tras capturar monto de recarga
│   ├── sondeo_sin_recarga.txt   # Sondeo sin monto de recarga conocido
│   ├── oferta_principal.txt     # Presentación principal de la promo
│   ├── objeciones.txt           # Rebate de objeciones con banco de respuestas
│   └── cierre_fallback.txt      # Fallback cuando el cliente no dio un campo KPI claro
│
├── agents/                  # Agente de venta (LangGraph)
│   └── portabilidad/
│       ├── state.py         # Estado del agente (PortabilidadState TypedDict)
│       ├── graph.py         # Grafo LangGraph — conecta todos los nodos
│       ├── utils.py         # split_msg(), load_prompt(), render_prompt()
│       └── nodes/
│           ├── validacion.py    # Valida LADA/región (primer filtro)
│           ├── sondeo.py        # Conoce al cliente: recarga, uso, necesidad
│           ├── clasificacion.py # Temperatura: caliente/tibio/frío
│           ├── oferta.py        # Presenta la promo correcta
│           ├── objeciones.py    # Rebate objeciones (max 3 intentos)
│           ├── cierre.py        # Captura datos para handoff
│           └── escalate.py      # Crea lead en Bitrix y envía handoff al asesor
│
├── integrations/            # Conexiones con servicios externos
│   ├── exceptions.py        # WhatsAppError, BitrixError, DatabaseError
│   ├── debounce.py          # Motor de debounce — agrupa mensajes consecutivos por número
│   ├── whatsapp/
│   │   ├── client.py        # WhatsAppClient.send_message() — httpx + tenacity
│   │   └── handlers.py      # verify_webhook_signature() — HMAC-SHA256
│   ├── bitrix/
│   │   ├── client.py        # BitrixClient — crear_deal(), actualizar_deal(), mover etapa
│   │   ├── oauth.py         # OAuth tokens — exchange, refresh, Redis-backed
│   │   └── connector.py     # imconnector API — mirror de mensajes en Open Lines
│   ├── telegram/
│   │   ├── client.py        # TelegramClient.send_message()
│   │   └── handlers.py      # parse_update() — extrae chat_id, text, phone
│   ├── postgres/
│   │   └── client.py        # Pool asyncpg — execute/fetch/fetchrow parametrizados
│   └── qdrant/
│       └── client.py        # RAG semántico — index_objeciones(), search_objection()
│
├── api/                     # Endpoints HTTP
│   ├── main.py              # App FastAPI — lifespan, middleware de logging
│   └── routes/
│       ├── health.py        # GET /health — status ok/degraded + check de DB
│       ├── webhooks.py      # POST/GET /webhooks/telcel — entry point de WhatsApp
│       └── telegram.py      # POST /webhooks/telegram — entry point de Telegram (pruebas)
│
├── db/                      # Capa de datos
│   ├── models.py            # Modelos Pydantic: Lead, Lada, Promo, CAC, Objecion
│   └── migrations.py        # DDL CREATE TABLE para todas las tablas
│
├── jobs/                    # Tareas programadas
│   ├── seguimientos.py      # Cadencia de seguimientos automáticos (APScheduler)
│   └── connector_poll.py    # Polling cada 30s: reenvía mensajes del asesor al usuario
│
├── knowledge/               # Base de conocimiento del bot
│   ├── seed.py              # Script principal: crea tablas y carga todo
│   ├── loaders/
│   │   ├── load_ladas.py    # LADAs habilitadas Región 4
│   │   ├── load_promos.py   # Promos vigentes con fecha de expiración
│   │   ├── load_cacs.py     # Directorio CACs R4 con coordenadas
│   │   ├── load_equipos.py  # Equipos y si requieren desbloqueo
│   │   └── load_objeciones.py  # Banco de objeciones con respuestas
│   └── prompts/             # Versiones del prompt del agente (v1, v2…)
│
├── config/
│   ├── settings.py          # Pydantic BaseSettings — todas las vars de entorno
│   └── logging.py           # JSON logging + mask_phone()
│
└── tests/
    ├── unit/                # Tests con mocks de APIs externas
    └── scenarios/           # Tests de conversaciones completas (regresión de auditoría)
```

---

## Comandos principales

```bash
make dev          # Levanta API + PostgreSQL + Redis en modo desarrollo (hot reload)
make build        # Construye la imagen Docker
make down         # Apaga todos los contenedores
make seed         # Carga la base de conocimiento (LADAs, promos, CACs, equipos, objeciones)
make worker       # Levanta el worker de la cola de mensajes arq
make test         # Corre tests con cobertura
make lint         # ruff + mypy
make health       # curl /health y muestra el resultado
make export_kpi   # Exporta kpi_conversaciones a CSV en ./exports/
```

---

## Variables de entorno

Ver `.env.example` para la lista completa. Nunca commitear `.env`.

| Variable | Propósito |
|---|---|
| `WHATSAPP_TOKEN` | Bearer token para Graph API de Meta |
| `WHATSAPP_APP_SECRET` | Usado para validar firma HMAC de webhooks |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificación del webhook (handshake Meta) |
| `BITRIX_WEBHOOK_URL` | URL del webhook entrante de Bitrix24 (CRM: crear/mover deals) |
| `BITRIX_PIPELINE_ID` | ID del pipeline de deals (actualmente `90`) |
| `BITRIX_STAGE_IA_PORTA` | Stage ID inicial al crear deal en primer contacto (actualmente `C90:NEW`) |
| `BITRIX_STAGE_PROSPECTO` | Stage ID para KPIs completos — listo para portabilidad (`C90:PROSPECTO`) |
| `BITRIX_STAGE_SEGUIMIENTO` | Stage ID para usuario que quiere ser contactado después (`C90:SEGUIMIENTO`) |
| `BITRIX_STAGE_ESCALAMIENTO` | Stage ID para solicitud de asesor humano (`C90:UC_8WB2DT`) |
| `BITRIX_CLIENT_ID` | Client ID de la app local OAuth de Bitrix24 |
| `BITRIX_CLIENT_SECRET` | Client Secret de la app local OAuth |
| `BITRIX_CONNECTOR_ID` | ID del conector imconnector registrado en el portal (`telegram_ai_agent`) |
| `BITRIX_CONNECTOR_LINE_ID` | ID del Open Channel en Bitrix24 (actualmente `542`) |
| `BITRIX_PUBLIC_URL` | URL pública del servidor para el callback OAuth de Bitrix |
| `ANTHROPIC_API_KEY` | API key de Claude (Anthropic) |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `REDIS_URL` | URL de conexión a Redis |
| `DEBOUNCE_WINDOW_MS` | Ventana de debounce en ms (0 = desactivado, producción: `10000`) |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (canal de pruebas) |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para validar webhooks de Telegram (X-Telegram-Bot-Api-Secret-Token) |
| `QDRANT_URL` | URL del servidor Qdrant (default: `http://qdrant:6333`) |
| `QDRANT_API_KEY` | API key de Qdrant (obligatoria en producción) |
| `QDRANT_EMBEDDING_MODEL` | Modelo fastembed local (default: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) |

---

## Pipeline operativo de Bitrix (pipeline ID 90 — deals, no leads)

El pipeline usa `crm.deal.*` con `CATEGORY_ID=90`. Las etapas siguen el formato `C90:*`.

| Etapa | Stage ID | Significado | Cuándo se asigna |
|---|---|---|---|
| Lead Nuevo / IA Porta | `C90:NEW` | Deal en manos del bot | Al primer mensaje del usuario (`validacion_node`) |
| Prospecto | `C90:PROSPECTO` | KPIs completos — listo para portabilidad | Al completar cierre con nombre, número y compañía (`escalate_node`, motivo `cierre`) |
| Seguimiento | `C90:SEGUIMIENTO` | Usuario quiere ser contactado después | Cuando el usuario expresa intención de continuar más adelante (`motivo: seguimiento, max_objeciones_alcanzado`) |
| Escalamiento Humano | `C90:UC_8WB2DT` | Solicita asesor humano ahora | Solicitud directa, caso sensible, ARCO, Telcel→Telcel, cambio de titularidad (`escalate_node`) |
| Venta | `C90:WON` | Solo leads con Venta Exitosa | Manual por el asesor |
| Recuperación | `C90:8` | Lead a reactivar | Regla automática Bitrix (24h sin avance) |
| Caído | `C90:LOSE` | Lead perdido (con tipificación) | Manual por el asesor |

**Resolución de stage en `escalate_node`:** `_resolve_stage(motivo)` mapea el `motivo_escalacion` al stage correcto. El deal se crea al primer contacto en `validacion_node` (`C90:NEW`) y se actualiza en `escalate_node` con el stage según intención. Nunca se crean dos deals para el mismo usuario.

**Detección de intent `seguimiento`:** los nodos `sondeo`, `oferta`, `objeciones` y `cierre` detectan frases como "más adelante", "llámame después", "contáctenme", "ahorita no puedo", etc. mediante la lista `_SEGUIMIENTO`.

---

## Seguridad y privacidad (LFPDPPP)

- **SQL injection:** SOLO queries parametrizadas (`$1`, `$2`). NUNCA f-strings con datos de usuario.
- **Logs:** teléfonos y nombres siempre enmascarados (`mask_phone()`). Nunca datos completos.
- **WhatsApp:** NIP NUNCA se pide ni procesa. La firma HMAC-SHA256 valida cada webhook.
- **Datos sensibles:** solo en PostgreSQL/Bitrix, con política de retención. Sin INE/CURP/bancarios por WhatsApp.
- **Solicitudes ARCO:** "borra mis datos" se canaliza al proceso de derechos ARCO, nunca se ignora.

---

## Debounce de mensajes

Los webhooks de WhatsApp y Telegram aplican debounce antes de invocar el agente.
Cuando un usuario manda varios mensajes seguidos, se acumulan en Redis y se procesan
juntos como un solo turno tras `DEBOUNCE_WINDOW_MS` ms de silencio.

| Clave Redis | Contenido |
|---|---|
| `debounce:msgs:{phone\|chat_id}` | Lista de textos acumulados (RPUSH) |
| `debounce:token:{phone\|chat_id}` | UUID del último mensaje (SET EX 300) |

El webhook retorna `200` a Meta/Telegram de inmediato; el agente corre en un
`asyncio.Task` en background. Si llega un mensaje más nuevo antes de que expire
la ventana, el Task anterior detecta que su token ya no es el actual y aborta.

---

## Flujo del agente (embudo)

```
WhatsApp / Telegram (lead Meta Ads)
        │
        ▼
[webhook] → debounce buffer (Redis)
        │  espera DEBOUNCE_WINDOW_MS ms sin nuevos mensajes
        ▼
[validacion] → ¿LADA en R4?
    ├── NO → mensaje + derivar CAC presencial → Bitrix: tipificar "no pertenece a región"
    └── SÍ ↓
[sondeo] → ¿cuánto recargas? ¿qué usas más?
        ↓
[clasificacion] → caliente / tibio / frío
        ↓
[oferta] → promo correcta según recarga (de tabla promos)
        ↓
[objeciones] → RAG semántico en Qdrant (max 3 rebates, fallback a PostgreSQL)
        ↓
[cierre] → captura nombre, número a portar, compañía donante, municipio
        ↓
[escalate] → Bitrix: lead a "Listo para Portabilidad" + Open Lines asigna a asesor
             El asesor gestiona el NIP en llamada.
```

---

## Defectos conocidos del bot anterior (resueltos en este diseño)

Basado en 2 rondas de auditoría y mystery shopper (40 hallazgos, 13 patrones sistémicos):

| Patrón | Problema anterior | Solución implementada |
|---|---|---|
| #1 | Exigía número antes de responder preguntas comerciales | sondeo.py responde info sin pedir número primero |
| #2 | Repetía el mismo texto idéntico hasta 7 veces | Claude genera respuesta (no plantillas fijas) |
| #4 | Reiniciaba con "Hola" a media conversación | Saludo solo en primer turno; checkpointer LangGraph |
| #5 | Trataba un emoji como número de teléfono | validacion.py valida input antes de procesar |
| #7 | Respondía con promo ante "mi mamá murió" | objeciones.py: casos sensibles → empatía + escalamiento |
| #8 | Daba credibilidad a "descuentos de familiar en Telcel" | Rechazar solicitudes fraudulentas con firmeza |
| #13 | Ante "ya decidí", respondía con más info de venta | cierre.py: detecta decisión → captura datos directo |

---

## Sistema de prompts

Los system prompts del agente viven en `prompts/*.txt` — **no** en el código Python. Para editar el comportamiento de Vera, editar el `.txt` correspondiente y reiniciar el contenedor; no se requiere cambiar código.

| Archivo | Cuándo se usa |
|---|---|
| `horarios.txt` | Pregunta sobre horarios de portación (validacion, sondeo, oferta) |
| `validacion_general.txt` | Primer contacto y mensajes generales antes de tener el número |
| `sondeo_con_recarga.txt` | Presentación de oferta tras capturar el monto de recarga |
| `sondeo_sin_recarga.txt` | Sondeo cuando aún no se tiene el monto de recarga |
| `oferta_principal.txt` | Re-presentación o ajuste de la promo en el nodo de oferta |
| `objeciones.txt` | Rebate de objeciones usando el banco de respuestas de la BD |
| `cierre_fallback.txt` | Fallback cuando el cliente no dio un campo KPI claramente |
| `prompt_unificado.md` | **Referencia consolidada** — todos los bloques ensamblados en un solo documento (catálogo, reglas, horarios, saludos, formato). Útil para revisar el comportamiento completo de Vera, hacer pruebas en playground o migrar a un agente de nodo único. |

Los archivos `.txt` usan placeholders `{NOMBRE}` que `render_prompt()` (`agents/portabilidad/utils.py`) sustituye en tiempo de ejecución con las constantes de `context.py` y variables dinámicas (monto de recarga, promos, etc.).

---

## Integración Bitrix24 Open Lines (imconnector)

El espejeo de mensajes usa la API `imconnector` vía OAuth (no el webhook REST básico).

### Flujo bidireccional

```
Usuario (Telegram/WhatsApp)
    │  mensaje
    ▼
webhook → mark_as_read(msg_id) → doble check azul + typing indicator al usuario
    │
    ▼
send_user_message() → imconnector.send.messages → Open Lines 542
    │                   └─ si sesión nueva: _fetch_openlines_deal_async() (bg, 3s delay)
    ▼  (debounce 10s + agente)
send_bot_message() → imconnector.send.messages (user.id=phone, prefijo "🤖 Vera |") → mismo chat

Asesor responde en Bitrix Open Lines
    │
    ▼  (polling cada 30s — connector_poll.py)
im.dialog.messages.get → _forward_to_user() → Telegram o WhatsApp
```

### Claves Redis del conector

| Clave Redis | Contenido |
|---|---|
| `connector_ext_chat:{phone}` | external_chat_id para la sesión activa (TTL **90 días** — preserva el vínculo teléfono↔deal entre visitas) |
| `connector_session:{phone}` | session_id de Open Lines devuelto por Bitrix (TTL 24h) |
| `connector_chat:{phone}` | chat_id interno de Bitrix (para im.dialog.messages.get) (TTL 24h) |
| `connector_deal:{phone}` | deal_id vinculado al canal Open Lines (TTL 24h) |
| `connector_last_msg:{phone}` | cursor: ID del último mensaje procesado del asesor |
| `connector_delivered:{msg_id}` | deduplicación de mensajes ya reenviados (TTL 24h) |

### Notas críticas de imconnector

- **Auth:** el token OAuth va en el **body JSON** como `"auth": token`, NO como header `Authorization: Bearer`.
- **Estructura de mensajes de usuario:** claves **lowercase** (`user`, `message`, `chat`). Uppercase (`USER`, `MESSAGE`) no funciona.
- **Mensajes del bot:** `send_bot_message()` usa `imconnector.send.messages` con el **mismo `user.id = phone`** que el usuario real. Usar un `user.id` diferente (ej. `"bot_{phone}"`) hace que imconnector abra una segunda sesión de Open Lines → segundo deal duplicado. El prefijo `"🤖 Vera |"` en el texto distingue visualmente las respuestas del bot. `im.message.add` no funciona en chats de Open Lines (error `CANCELED: No puede enviar mensajes al chat especificado`).
- **Deal asíncrono:** Bitrix crea el deal via Open Lines de forma asíncrona. `_fetch_openlines_deal_async()` espera 3s y busca el deal con `buscar_deal_por_telefono()`, guardándolo en Redis `connector_deal:{phone}` antes de que el debounce (10s) dispare. Así `validacion_node` reutiliza el deal de Open Lines en lugar de crear un fallback sin vínculo al canal.
- **Conector activo:** `telegram_ai_agent` (ya registrado en el portal b24-ahyle8.bitrix24.mx, activado en línea 542). No usar conectores nuevos — registrar uno nuevo con una app local requiere placement handler de marketplace.
- **Registro OAuth:** flujo en `GET /bitrix/auth` → Bitrix redirige a `BITRIX_PUBLIC_URL/bitrix/app` → tokens en Redis `bitrix:oauth_tokens`. Re-ejecutar si expira el refresh_token.
- **Polling concurrente:** `_poll_once` procesa todos los teléfonos activos en paralelo con `asyncio.gather`. El polling usa `_call_poll` (sin reintentos, timeout 20s) para no bloquear el ciclo si Bitrix tarda.

---

## Memoria conversacional y semántica

### Memoria conversacional (PostgreSQL checkpointer)

El agente usa `AsyncPostgresSaver` de `langgraph-checkpoint-postgres` como checkpointer. El estado completo de cada conversación se persiste en 4 tablas de PostgreSQL (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) y sobrevive reinicios del contenedor.

- **Thread ID:** `phone` en WhatsApp, `str(chat_id)` en Telegram
- **Inicialización:** en el lifespan de FastAPI (`api/main.py`). Fallback a `MemorySaver` si PostgreSQL falla al arrancar.
- **Setup automático:** `checkpointer.setup()` crea las tablas si no existen en cada arranque.

### Memoria semántica (Qdrant RAG)

El nodo de objeciones busca en Qdrant la respuesta más relevante por similitud semántica.

- **Colección:** `objeciones` — 20 vectores indexados con modelo multilingüe local
- **Modelo:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (fastembed, descarga automática en `make seed`)
- **Score threshold:** `0.4` — resultados por debajo se descartan y usan fallback PostgreSQL
- **Indexación:** al final de `load_objeciones.py` → correr `make seed` para re-indexar
- **Dashboard:** `qdrant-portabilidad.callcomcc.io` — usuario `admin`, contraseña en `.env`

---

## Notas de desarrollo

- **Promos:** configuración versionada en tabla `promos`. Cuando Telcel publique nuevas, actualizar `load_promos.py` y correr `make seed`. NUNCA hardcodear precios en el agente.
- **LADAs:** tabla técnica, no parte del guion. El bot la consulta internamente para decidir si continúa el flujo o deriva a CAC.
- **Versiones de prompt:** editar los archivos en `prompts/` directamente. Para historial de versiones usar git. La carpeta `knowledge/prompts/` es para specs de auditoría, no para los prompts activos.
- **APScheduler:** corre dentro del proceso FastAPI (lifespan). Dos jobs: `seguimientos` (cada 5 min, ventana L-S 9am–9pm) y `kpi_export` (cron 3am Monterrey). El scheduler se inicia en `api/main.py` con `create_scheduler().start()` y se apaga con `scheduler.shutdown(wait=False)`.
- **Jobs timezone:** siempre `America/Monterrey` explícito. El horario de portabilidad es L-S 9am–9pm; sin domingos.
- **Debounce:** configurar `DEBOUNCE_WINDOW_MS` en `.env`. Valor actual en producción: `10000` ms (10s). Poner `0` solo en pruebas unitarias o entornos donde cada mensaje debe procesarse de forma independiente.
- **Telegram:** canal de pruebas que corre el mismo agente y el mismo debounce que WhatsApp. El `thread_id` de LangGraph es `str(chat_id)` en Telegram y `phone` en WhatsApp. El `phone` en Telegram tiene prefijo `tg_` (ej. `tg_8211184685`).
- **Bitrix deals vs leads:** el pipeline 90 es de **deals** (`crm.deal.*`). No usar `crm.lead.*` — son entidades distintas con etapas distintas.
- **Connector poll:** `connector_poll.py` corre como `asyncio.Task` en el lifespan de FastAPI (no como job de APScheduler). Intervalo: 30 segundos. Procesamiento concurrente con `asyncio.gather`.
- **Deal en primer contacto:** Bitrix Open Lines / imconnector crea automáticamente un deal cuando el chat de WhatsApp se abre. `validacion_node` llama `buscar_deal_por_telefono()` (búsqueda por `%TITLE: "*{last4}"`) para encontrar ese deal y reutilizarlo; solo crea un deal nuevo como fallback si no encuentra ninguno. `escalate_node` actualiza el mismo deal con KPIs y stage. **Nunca crear un segundo deal para el mismo número** — duplicar el deal rompe el seguimiento en Open Lines.
- **Rebuild obligatorio tras cambios de código:** `docker compose restart api` NO recarga el código (la imagen está horneada en build time). Siempre usar `docker compose build api && docker compose up -d api` para que los cambios tengan efecto en producción.
- **WhatsApp typing indicator:** `WhatsAppClient.mark_as_read(message_id)` envía en una sola llamada el doble check azul **y** el indicador "...escribiendo" (`typing_indicator: {"type": "text"}`). Se llama al recibir cada mensaje, antes del debounce. El indicador se auto-descarta a los 25s o al llegar la respuesta del bot. API: `POST /{phone_id}/messages` con `status: "read"` + `typing_indicator`. Documentación oficial: `developers.facebook.com/docs/whatsapp/cloud-api/typing-indicators/`.
- **Anti-duplicado de deals:** `send_bot_message` DEBE usar el mismo `user.id` que los mensajes del usuario. Un `user.id` diferente abre segunda sesión de Open Lines → segundo deal. El poll filtra mensajes del bot (tienen `CONNECTOR_MID`) → no se reenvían a WhatsApp.
- **`_fin_node` silenciado (escalamiento duro):** cuando `etapa: fin` y `motivo_escalacion` es un escalamiento duro (`solicitud_directa`, `caso_sensible`, `solicitud_arco`, `telcel_a_telcel`, `cambio_titularidad`, `lada_no_identificada`), el bot retorna `{}` — silencio total, el asesor humano gestiona la conversación desde Bitrix Open Lines. Única excepción: el cliente dice palabras de `_FIN_PROSPECTO` ("ya decidí", "quiero portarme") → el bot responde con un mensaje de confirmación y mueve el deal a `C90:PROSPECTO`. Para seguimiento suave (`seguimiento`, `max_objeciones_alcanzado`), el bot sigue activo y Claude responde preguntas mientras el cliente espera.
- **`escalate_node` sin mensajes:** el nodo solo actualiza Bitrix y el estado del agente. No agrega `AIMessage` — el mensaje de confirmación al usuario lo genera el nodo que llama a `escalate` (cierre, objeciones, etc.).
- **Principio Anti-Rendición (`context.py`):** las constantes `ANTI_RENDICION` y `OBJECTIONS_HANDLING` se definen en `agents/portabilidad/context.py` y se inyectan en los prompts via `render_prompt()` como `{ANTI_RENDICION}`. Aplican en `sondeo`, `oferta`, `objeciones` y `validacion`. La regla central: ante un "no", silencio o respuesta fría, Vera no cierra — intenta entender la objeción real hasta 3 veces antes del cierre cálido. Excepción: rechazo explícito, molestia real o solicitud de asesor → respetar de inmediato sin reformular.
- **`BitrixClient.get_deal(deal_id)`:** método nuevo en `integrations/bitrix/client.py` — llama `crm.deal.get` y retorna el dict del deal (STAGE_ID, ASSIGNED_BY_ID, SOURCE_ID, CLOSEDATE, CONTACT_ID). Usado por `job_kpi_export`.

## Exportación de KPIs para BI

### Tabla `kpi_conversaciones`

Tabla aislada del agente (no la usan los nodos). Una fila por conversación. Se crea con el DDL en `db/migrations.py` (incluido en `make seed`).

| Campo | Fuente |
|---|---|
| `id_conversacion`, `etapa`, `bitrix_lead_id` | Checkpoints LangGraph (`checkpoints` table, JSONB `channel_values`) |
| `creado_el` | Primer checkpoint del thread (`MIN(checkpoint->>'ts')`) |
| `estado_actual`, `empleado`, `origen`, `cerrado_el` | Bitrix `crm.deal.get` |
| `mensajes_cliente`, `mensajes_bot`, `primer_mensaje` | `graph.aget_state()` — requiere checkpointer PG activo |
| `mensajes_humano`, `primera_respuesta`, `el_agente_respondio_el`, tiempos | Bitrix Open Lines `im.dialog.messages.get` |

### Job nocturno (`jobs/kpi_export.py`)

- Corre a las **3am America/Monterrey** via APScheduler (`id="kpi_export"`)
- Fuente: tabla `checkpoints` (últimos 30 días, máx 500 threads), no la tabla `leads`
- Procesa en lotes de 50 con 0.3s de pausa entre lotes para no saturar el event loop
- Upsert por `id_conversacion` → seguro re-ejecutar
- `_ensure_graph_initialized()`: en el proceso FastAPI el grafo ya está listo; en standalone inicializa un pool psycopg con timeout de 8s
- **`solicitud_enviada_al_agente_el`:** pendiente v2 (no hay timestamp de escalación en el estado actual)

### Export a CSV

- **Comando:** `make export_kpi`
- **Ruta en contenedor:** `/app/reporteskpi/kpi_conversaciones_{YYYYMMDD_HHMM}.csv`
- **Ruta en host:** `./reporteskpi/kpi_conversaciones_{YYYYMMDD_HHMM}.csv` (volumen bind mount en `docker-compose.yml`)
- Encoding `utf-8-sig` (compatible con Excel / Power BI sin problemas de tildes)
- La carpeta `./reporteskpi/` está en `.gitignore` — los CSVs no se suben al repo

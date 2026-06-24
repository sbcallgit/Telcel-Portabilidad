# Bot Telcel Portabilidad — Documentación del Proyecto

**Campaña:** Muévete Prepago · Región 4
**Canal:** WhatsApp Business (solo texto)
**Origen de leads:** Meta Ads (Click-to-WhatsApp)
**CRM:** Bitrix24

---

## Documentación técnica

| Documento | Ruta | Descripción |
|---|---|---|
| Manual imconnector / Open Lines | [`docs/manual_imconnector_whatsapp_bitrix.md`](docs/manual_imconnector_whatsapp_bitrix.md) | Guía completa de implementación del canal WhatsApp ↔ Bitrix24 vía imconnector: OAuth, registro del conector, flujo de mensajes de entrada/salida, polling del asesor, claves Redis y reglas críticas. Reutilizable para otras integraciones. |
| Layout KPIs | [`docs/lay_out_ideal_kpis.md`](docs/lay_out_ideal_kpis.md) | Estructura ideal de la tabla `kpi_conversaciones` para reportes de BI. |
| Guía Dashboard KPI | [`docs/dashboard_kpi_guia.md`](docs/dashboard_kpi_guia.md) | Explicación de cada sección, gráfica y tabla del dashboard: cómo leerlas, señales de alerta, casos de uso analítico y gráficas planeadas para próximas secciones. |
| Prompt unificado | [`prompts/prompt_unificado.md`](prompts/prompt_unificado.md) | Todos los bloques del system prompt de Vera ensamblados en un solo documento. Útil para playground y auditorías. |
| Especificación del bot | [`VERA_Bot_Specification.md`](VERA_Bot_Specification.md) | Especificación funcional completa de Vera. |

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
| Dashboard KPI | Angular 18 (standalone) | Visualización de KPIs — acceso por correo/contraseña (JWT) |
| Meta Ads | `facebook-business` SDK | Ad Insights (gasto, clics, CPL) + Conversions API (CAPI) |

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
│   │   └── handlers.py      # verify_webhook_signature() + parse_whatsapp_message() (retorna referral)
│   ├── bitrix/
│   │   ├── client.py        # BitrixClient — crear_deal(), actualizar_deal(), mover etapa
│   │   ├── oauth.py         # OAuth tokens — exchange, refresh, Redis-backed
│   │   └── connector.py     # imconnector API — mirror de mensajes en Open Lines
│   ├── telegram/
│   │   ├── client.py        # TelegramClient.send_message()
│   │   └── handlers.py      # parse_update() — extrae chat_id, text, phone
│   ├── postgres/
│   │   └── client.py        # Pool asyncpg — execute/fetch/fetchrow parametrizados
│   ├── vicidial/
│   │   └── client.py        # agregar_lead() — GET a non_agent_api.php (Rescate 3)
│   ├── qdrant/
│   │   └── client.py        # RAG semántico — index_objeciones(), search_objection()
│   ├── meta/
│   │   ├── insights.py      # get_insights() — Ad Insights vía facebook-business SDK (async)
│   │   └── conversions.py   # send_purchase_event(), send_lead_event() — CAPI v20
│   └── megacable_db.py      # fetch_megacable() — conexión de solo lectura a BD bot_megacable
│
├── api/                     # Endpoints HTTP
│   ├── main.py              # App FastAPI — lifespan, middleware de logging, CORS con Authorization
│   ├── deps.py              # require_auth() — acepta Bearer JWT o X-Admin-Token
│   └── routes/
│       ├── health.py        # GET /health — status ok/degraded + check de DB
│       ├── auth.py          # POST /auth/login — JWT 8h; GET /auth/me
│       ├── webhooks.py      # POST/GET /webhooks/telcel — captura referral Click-to-WhatsApp
│       ├── telegram.py      # POST /webhooks/telegram — entry point de Telegram (pruebas)
│       └── admin.py         # Endpoints de administración y datos (ver tabla abajo)
│
├── db/                      # Capa de datos
│   ├── models.py            # Modelos Pydantic: Lead, Lada, Promo, CAC, Objecion
│   └── migrations.py        # DDL CREATE TABLE para todas las tablas
│
├── jobs/                    # Tareas programadas
│   ├── seguimientos.py      # Rescate 1, 2 y 3 — seguimientos automáticos (APScheduler, desactivado pending validación)
│   ├── bitrix_sync.py       # Sincroniza leads.bitrix_stage desde Bitrix cada 30 min (APScheduler, activo)
│   ├── kpi_export.py        # Extracción nocturna de KPIs a las 3am — upsert en kpi_conversaciones
│   ├── email_report.py      # Reporte diario KPI por correo (SMTP SSL Hostinger) — se dispara a las 00:00
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
├── dashboard/               # Dashboard KPI — Angular 18
│   └── src/app/
│       ├── pages/
│       │   ├── login/       # Formulario email + contraseña → JWT
│       │   └── dashboard/   # KPIs Telcel, Meta Ads Insights, UTM, Megacable
│       └── services/
│           ├── auth.service.ts   # login(), logout(), getToken()
│           └── kpi.service.ts    # getData(), getMetaInsights(), getUtmData(), getMegacableData()
│
├── scripts/
│   └── seed_dashboard_users.py  # Crea usuarios iniciales del dashboard (bcrypt)
│
└── tests/
    ├── unit/                # Tests con mocks de APIs externas
    └── scenarios/           # Tests de conversaciones completas (regresión de auditoría)
```

### Endpoints admin (`/admin/*`)

| Endpoint | Método | Descripción |
|---|---|---|
| `/admin/kpi-data` | GET | KPIs de Telcel desde `kpi_conversaciones` (paginado, filtros) |
| `/admin/kpi-export` | POST | Dispara regeneración de `kpi_conversaciones` en background |
| `/admin/kpi-email` | POST | Envía reporte KPI por correo inmediatamente |
| `/admin/seguimiento-test` | POST | Fuerza Rescate 1 o 2 para un teléfono específico |
| `/admin/vicidial-test` | POST | Dispara llamada Vicidial (Rescate 3) — `simulate=true` para prueba |
| `/admin/meta-insights` | GET | Ad Insights de Meta (gasto, clics, CPL) con filtro fecha y nivel |
| `/admin/capi-test` | POST | Dispara evento CAPI manualmente — `simulate=true` para prueba |
| `/admin/utm-data` | GET | Atribución UTM desde tabla `leads` — por campaña, fuente y ad_id |
| `/admin/megacable-data` | GET | KPIs del agente Megacable desde BD externa |
| `/admin/bitrix-eventos-seed` | POST | Puebla `bitrix_eventos` desde `kpi_conversaciones` existente (migración inicial) |

Todos los endpoints aceptan `X-Admin-Token` (header) **o** `Authorization: Bearer <JWT>`.

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
| `ADMIN_TOKEN` | Token para endpoints admin (header `X-Admin-Token`). Default `changeme` — cambiar en producción. |
| `VICIDIAL_URL` | URL de la API Vicidial (default: `http://189.209.207.222/vicidial/non_agent_api.php`) |
| `VICIDIAL_USER` | Usuario API Vicidial (default: `api_n8n`) |
| `VICIDIAL_PASS` | Contraseña API Vicidial |
| `VICIDIAL_LIST_ID` | ID de lista en Vicidial (default: `101`) |
| `VICIDIAL_CAMPAIGN_ID` | ID de campaña en Vicidial (default: `n8n_port`) |
| `SMTP_HOST` | Servidor SMTP para reporte KPI (default: `smtp.hostinger.com`) |
| `SMTP_PORT` | Puerto SMTP SSL (default: `465`) |
| `SMTP_USER` | Correo remitente (ej. `crm1@callcomcc.cloud`) |
| `SMTP_PASS` | Contraseña del correo remitente |
| `REPORT_EMAIL_TO` | Destinatarios del reporte KPI separados por coma (ej. `a@x.com,b@x.com`) |
| `JWT_SECRET` | Secreto para firmar tokens JWT del dashboard (cambiar en producción) |
| `JWT_EXPIRE_HOURS` | Duración del JWT en horas (default: `8`) |
| `META_APP_ID` | App ID de Meta for Developers (`874313662396190`) |
| `META_APP_SECRET` | App Secret de Meta (no mezclar con `WHATSAPP_APP_SECRET`) |
| `META_ACCESS_TOKEN` | System User Token con permiso `ads_read` (y `ads_management` para CAPI) |
| `META_AD_ACCOUNT_ID` | Cuenta de anuncios activa (ej. `act_3292969264212775` — Portabilidad 2 Callcom) |
| `META_PIXEL_ID` | ID del Pixel de Meta para Conversions API (ej. `1654668329217239`) |
| `MEGACABLE_DB_HOST` | Host de la BD del agente Megacable (ej. `147.79.78.75`) |
| `MEGACABLE_DB_PORT` | Puerto PostgreSQL de Megacable (default: `5433`) |
| `MEGACABLE_DB_NAME` | Nombre de la BD (`bot_megacable`) |
| `MEGACABLE_DB_USER` | Usuario de la BD Megacable |
| `MEGACABLE_DB_PASSWORD` | Contraseña de la BD Megacable |

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
| Rescate 1 | `C90:1` | Primer seguimiento enviado | `job_seguimientos` tras 30 min de silencio del usuario |
| Rescate 2 | `C90:2` | Segundo seguimiento enviado | `job_seguimientos` 60 min después de Rescate 1 (solo a `C90:1`) |
| Rescate 3 | `C90:3` | Llamada automática vía Vicidial | `job_seguimientos` 60 min después de Rescate 2 (solo a `C90:2`) |
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
- **APScheduler:** corre dentro del proceso FastAPI (lifespan). Jobs activos: `bitrix_sync` (cada 30 min), `kpi_export` (cron 3am Monterrey) y `job_seguimientos` (cada 5 min, L-S 9am–9pm). El scheduler se inicia en `api/main.py` con `create_scheduler().start()` y se apaga con `scheduler.shutdown(wait=False)`.
- **`SEGUIMIENTOS_TEST_PHONE`:** cuando está definido en `.env`, `job_seguimientos` solo procesa ese teléfono (modo validación). Para producción general dejar vacío (`SEGUIMIENTOS_TEST_PHONE=`) y hacer rebuild. Actualmente activo con el teléfono de prueba `593991053639`.
- **Lógica Rescate 1 simplificada:** `_procesar_lead` ya no usa cadencias por stage. Condiciones: 30+ min de silencio del usuario **y** `seguimientos_enviados < MAX_SEGUIMIENTOS` (5). Aplica a cualquier stage excepto `C90:WON`, `C90:1`, `C90:2`, `C90:3`. El filtro SQL usa `$1` como único parámetro cuando `SEGUIMIENTOS_TEST_PHONE` está activo (antes usaba `$2` causando error de BD).
- **Bug seguimientos ilimitados (resuelto):** `_procesar_lead` no chequeaba `MAX_SEGUIMIENTOS`. La constante existía pero solo la usaba `_siguiente_envio()`, función que nunca se invoca (código muerto de versión anterior). Combinado con que `job_bitrix_sync` sobreescribe `bitrix_stage` desde Bitrix cada 30 min (ej. `C90:LOSE` no está excluido de la query R1), un lead podía recibir un seguimiento en cada ciclo de 5 min indefinidamente. Fix: guardia `if num_enviados >= MAX_SEGUIMIENTOS: return` al inicio de `_procesar_lead`. `_siguiente_envio()` y `_cadencia()` son código muerto — no borrarlos sin reemplazar la lógica de cadencias si se quiere reactivar.
- **Jobs timezone:** siempre `America/Monterrey` explícito. El horario de portabilidad es L-S 9am–9pm; sin domingos.
- **Debounce:** configurar `DEBOUNCE_WINDOW_MS` en `.env`. Valor actual en producción: `10000` ms (10s). Poner `0` solo en pruebas unitarias o entornos donde cada mensaje debe procesarse de forma independiente.
- **Telegram:** canal de pruebas que corre el mismo agente y el mismo debounce que WhatsApp. El `thread_id` de LangGraph es `str(chat_id)` en Telegram y `phone` en WhatsApp. El `phone` en Telegram tiene prefijo `tg_` (ej. `tg_8211184685`).
- **Bitrix deals vs leads:** el pipeline 90 es de **deals** (`crm.deal.*`). No usar `crm.lead.*` — son entidades distintas con etapas distintas.
- **Connector poll:** `connector_poll.py` corre como `asyncio.Task` en el lifespan de FastAPI (no como job de APScheduler). Intervalo: 30 segundos. Procesamiento concurrente con `asyncio.gather`.
- **Deal en primer contacto:** Bitrix Open Lines / imconnector crea automáticamente un deal cuando el chat de WhatsApp se abre. `validacion_node` llama `buscar_deal_por_telefono()` (búsqueda por `%TITLE: "*{last4}"`) para encontrar ese deal y reutilizarlo; solo crea un deal nuevo como fallback si no encuentra ninguno. `escalate_node` actualiza el mismo deal con KPIs y stage. **Nunca crear un segundo deal para el mismo número** — duplicar el deal rompe el seguimiento en Open Lines.
- **Rebuild obligatorio tras cambios de código:** `docker compose restart api` NO recarga el código (la imagen está horneada en build time). Siempre usar `docker compose build api && docker compose up -d api` para que los cambios tengan efecto en producción.
- **WhatsApp typing indicator:** `WhatsAppClient.mark_as_read(message_id)` envía en una sola llamada el doble check azul **y** el indicador "...escribiendo" (`typing_indicator: {"type": "text"}`). Se llama al recibir cada mensaje, antes del debounce. El indicador se auto-descarta a los 25s o al llegar la respuesta del bot. API: `POST /{phone_id}/messages` con `status: "read"` + `typing_indicator`. Documentación oficial: `developers.facebook.com/docs/whatsapp/cloud-api/typing-indicators/`.
- **Anti-duplicado de deals:** `send_bot_message` DEBE usar el mismo `user.id` que los mensajes del usuario. Un `user.id` diferente abre segunda sesión de Open Lines → segundo deal. El poll filtra mensajes del bot (tienen `CONNECTOR_MID`) → no se reenvían a WhatsApp.
- **`_fin_node` silenciado (escalamiento duro):** cuando `etapa: fin` y `motivo_escalacion` es un escalamiento duro (`solicitud_directa`, `caso_sensible`, `solicitud_arco`, `telcel_a_telcel`, `cambio_titularidad`, `lada_no_identificada`), el bot retorna `{}` — silencio total, el asesor humano gestiona la conversación desde Bitrix Open Lines. Única excepción: el cliente dice palabras de `_FIN_PROSPECTO` ("ya decidí", "quiero portarme") → el bot responde con un mensaje de confirmación y mueve el deal a `C90:PROSPECTO`. Para seguimiento suave (`seguimiento`, `max_objeciones_alcanzado`), el bot sigue activo y Claude responde preguntas mientras el cliente espera. Segunda excepción: si el deal está en `C90:LOSE` al momento del mensaje (asesor lo marcó Caído), `_fin_node` lo detecta vía `bx.get_deal()`, lo mueve a `C90:PREPAYMENT_INVOIC` (Recuperación) y reactiva la conversación respondiendo al cliente.
- **`escalate_node` sin mensajes:** el nodo solo actualiza Bitrix y el estado del agente. No agrega `AIMessage` — el mensaje de confirmación al usuario lo genera el nodo que llama a `escalate` (cierre, objeciones, etc.).
- **Horario de contacto del asesor (`cierre.py`):** `_mensaje_contacto_asesor()` determina el texto de confirmación al completar los KPIs según día y hora en `America/Monterrey`. Reglas: domingo (cualquier hora) → lunes 9:00 a.m.; sábado 15:00–23:59 → lunes 9:00 a.m.; sábado 00:01–08:59 → hoy 9:00 a.m.; sábado 09:00–14:59 → conexión inmediata; lun–vie 21:00–23:59 → mañana 9:00 a.m.; lun–vie 00:01–08:59 → hoy 9:00 a.m.; lun–vie 09:00–20:59 → conexión inmediata.
- **Principio Anti-Rendición (`context.py`):** las constantes `ANTI_RENDICION` y `OBJECTIONS_HANDLING` se definen en `agents/portabilidad/context.py` y se inyectan en los prompts via `render_prompt()` como `{ANTI_RENDICION}`. Aplican en `sondeo`, `oferta`, `objeciones` y `validacion`. La regla central: ante un "no", silencio o respuesta fría, Vera no cierra — intenta entender la objeción real hasta 3 veces antes del cierre cálido. Excepción: rechazo explícito, molestia real o solicitud de asesor → respetar de inmediato sin reformular.
- **`BitrixClient.get_deal(deal_id)`:** método nuevo en `integrations/bitrix/client.py` — llama `crm.deal.get` y retorna el dict del deal (STAGE_ID, ASSIGNED_BY_ID, SOURCE_ID, CLOSEDATE, CONTACT_ID). Usado por `job_kpi_export`.
- **Contacto Bitrix con teléfono estructurado:** `BitrixClient._find_or_create_contact(telefono, nombre)` busca duplicados via `crm.duplicate.findbycomm` (retorna `[]` lista si no hay, `{"CONTACT":[...]}` dict si hay — se maneja con `isinstance`) y crea el contacto con `PHONE[VALUE_TYPE=WORK]` si no existe. `crear_deal()` siempre crea/vincula el contacto con `CONTACT_ID`. `link_contact_to_deal(deal_id, telefono)` cubre los deals de Open Lines: si ya tienen `CONTACT_ID` pero sin `PHONE` (caso típico de WhatsApp), actualiza el contacto via `crm.contact.update`. Se llama en background con `asyncio.create_task` desde `validacion_node` al encontrar un deal existente.
- **Campos personalizados UF en deals Bitrix:** `BitrixClient.ensure_custom_fields()` crea al arrancar dos campos UF en todos los deals del pipeline: `UF_CRM_MOTIVO_ESCALAMIENTO_HUMANO` (motivo exacto del estado del agente) y `UF_CRM_RESUMEN_CONVERSACION` (resumen LLM del chat para el asesor). También agrega ambos campos al layout común del formulario en una sección "Bot Telcel" vía `crm.deal.details.configuration.set`. `escalate_node` los puebla en background (`asyncio.create_task`) para **todos** los tipos de escalamiento. El resumen se genera con Claude a partir de los últimos 20 mensajes del estado LangGraph. `_ensure_layout_fields` es idempotente — si los campos ya están en el layout, no hace nada.
- **`motivo_escalacion` en `kpi_conversaciones`:** columna `TEXT NOT NULL DEFAULT ''` agregada a la tabla. Se extrae del snapshot LangGraph (`snapshot.values.get("motivo_escalacion")`) en `_get_message_counts()` del `kpi_export`. Se muestra como columna "Motivo Escalamiento" en la tabla de conversaciones del dashboard Angular.
- **`_TELCEL_TELCEL` en `validacion_node` (fix):** la lista de frases `telcel_a_telcel` solo existía en `sondeo.py` y `oferta.py`. Si el primer mensaje del cliente era "Ya soy cliente de Telcel", `validacion_node` no lo detectaba y caía al LLM, que respondía libre sin escalar. Fix: se agrega `_TELCEL_TELCEL` con 9 variantes en `validacion.py` y su detección en `_validacion_logic` antes del fallback al LLM, estableciendo `escalate_to_human=True` y `motivo_escalacion="telcel_a_telcel"`.
- **Reactivación de deals Caídos (`C90:LOSE → C90:PREPAYMENT_INVOIC`):** cuando un asesor mueve manualmente un deal a `C90:LOSE` y el cliente vuelve a escribir, el bot lo reactiva automáticamente a `C90:PREPAYMENT_INVOIC` (Recuperación) en lugar de crear un deal nuevo. Tres capas de detección: (1) `validacion_node` lee `leads.bitrix_stage` desde la BD local — funciona dentro de los 30 min del sync; (2) `_fin_node` llama `bx.get_deal()` directamente cuando el estado tiene `etapa=fin` + escalamiento duro, sin depender del sync; (3) `job_bitrix_sync` limpia `bot_pausado:{phone}` en Redis cuando detecta transición a `C90:LOSE`, para que el webhook no bloquee el mensaje. Adicionalmente, `buscar_deal_por_telefono` ya no excluye `C90:LOSE` del fallback (solo excluye `C90:WON`), evitando que se cree un deal duplicado. Al reactivar, se borran los checkpoints LangGraph del teléfono para que la conversación empiece limpia.
- **Dashboard — mejoras de gráficas (2026-06-24):** (1) Doughnut de stages: leyenda muestra `Etapa: N (X%)` con cantidad y porcentaje generados por `generateLabels`; (2) Mensajes por actor: segunda serie tipo `line` con promedio por conversación en eje Y derecho; (3) Funnel: cambiado de barras horizontales a verticales con línea de `% conversión` acumulada vs primer stage; (4) Meta Ads: cambiado a barras horizontales (`indexAxis: 'y'`) con nombres de campaña completos sin truncar, dos ejes X (gasto abajo, conversaciones arriba).

## Sistema de seguimientos automáticos (Rescate)

### Flujo Rescate

```
lead activo (any stage excepto C90:WON / C90:1 / C90:2 / C90:3)
  │  usuario sin actividad ≥ 30 min (MAX checkpoint ts)
  ▼
[job_seguimientos] → _procesar_lead() → WhatsApp: mensaje Rescate 1
                                      → Bitrix: mover deal a C90:1
                                      → leads: bitrix_stage = 'C90:1'

lead en C90:1
  │  usuario sin actividad ≥ 30 min Y ≥ 60 min desde Rescate 1
  ▼
[job_seguimientos] → _procesar_rescate2() → WhatsApp: mensaje Rescate 2
                                          → Bitrix: mover deal a C90:2
                                          → leads: bitrix_stage = 'C90:2'

lead en C90:2
  │  usuario sin actividad ≥ 30 min Y ≥ 60 min desde Rescate 2
  ▼
[job_seguimientos] → _procesar_rescate3() → Vicidial: GET non_agent_api.php (add_lead)
                                          → Bitrix: mover deal a C90:3
                                          → leads: bitrix_stage = 'C90:3'
```

### Mensajes personalizados con LLM (Rescate 1 y 2)

`_generar_mensaje_rescate(lead, rescate)` en `jobs/seguimientos.py` genera el texto de cada mensaje de seguimiento usando Claude con el historial real de la conversación como contexto.

**Fuente de contexto:** `_get_historial(phone)` llama `get_agent_graph().aget_state()` con `thread_id = phone` y extrae los últimos 20 mensajes (`HumanMessage` / `AIMessage`) en formato `Cliente: ... / Vera: ...`. Esto permite personalizar el mensaje con lo que el cliente mencionó (objeción, recarga, nombre, promo) aunque no haya completado el flujo.

- Si hay historial: el LLM referencia naturalmente lo que se habló ("la promo de $200 que platicamos").
- Si no hay historial (lead sin conversación): genera un mensaje genérico de portabilidad.
- Si el LLM falla: fallback automático al template estático de `_MENSAJES`.
- Log `llm_mensaje_generado` incluye campo `con_historial: true/false` para auditoría.

**Rescate 1:** tono cálido y cercano. **Rescate 2:** un poco más de urgencia, sin ser agresivo. Rescate 3 no envía mensaje — solo dispara la llamada Vicidial.

### Fuente de verdad y sincronización

- **`leads.bitrix_stage`** — columna local sincronizada desde Bitrix por `job_bitrix_sync` (cada 30 min, máx 1 000 leads)
- **`minutos_desde_ultimo_mensaje(phone)`** — consulta `MAX(checkpoint->>'ts')` en tabla `checkpoints` (LangGraph) por `thread_id = phone`
- **`leads.ultimo_seguimiento`** — timestamp del último seguimiento enviado; gate de 60 min para Rescate 2 y 3. Si es NULL (stage llegó vía sync de Bitrix sin pasar por el job), se usa `updated_at` como fallback para no bloquear el flujo indefinidamente.
- **`leads.seguimientos_enviados`** — contador acumulado de mensajes de seguimiento

### Exclusiones de Rescate 1

No se envía Rescate 1 a deals cuyo `bitrix_stage` esté en: `C90:WON`, `C90:1`, `C90:2`, `C90:3`.

### Exclusiones de Rescate 2

Solo se envía a leads con `bitrix_stage = 'C90:1'` (Rescate 1 ya enviado).

### Exclusiones de Rescate 3

Solo se envía a leads con `bitrix_stage = 'C90:2'` (Rescate 2 ya enviado).

### Jobs relacionados

| Job | Archivo | Frecuencia | Estado |
|---|---|---|---|
| `job_bitrix_sync` | `jobs/bitrix_sync.py` | Cada 30 min | **Activo** |
| `job_seguimientos` | `jobs/seguimientos.py` | Cada 5 min, L-S 9am–9pm | **Activo** (modo test — solo `SEGUIMIENTOS_TEST_PHONE`) |
| `job_kpi_export` | `jobs/kpi_export.py` | Diario 3am Monterrey | **Activo** |
| `send_kpi_report` | `jobs/email_report.py` | Diario 00:00 Monterrey | **Activo** |

### Trigger manual para validación

```bash
# Rescate 1 (detecta stage automáticamente)
curl -X POST https://portabilidad.callcomcc.io/admin/seguimiento-test \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"telefono": "521XXXXXXXXXX", "force": true}'

# Respuesta exitosa: {"status": "enviado", "flujo": "rescate1|rescate2",
#   "bitrix_stage_anterior": "C90:NEW", "bitrix_movido_a": "C90:1", ...}
```

`force: true` omite la ventana de 30 min de silencio (solo para pruebas). Si el lead tiene `bitrix_stage = 'C90:1'`, el endpoint detecta automáticamente y ejecuta flujo Rescate 2.

```bash
# Rescate 3 — llamada Vicidial (simulate=true omite la llamada real)
curl -X POST https://portabilidad.callcomcc.io/admin/vicidial-test \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"telefono": "521XXXXXXXXXX", "simulate": true}'

# Respuesta exitosa: {"status": "ok", "simulate": true,
#   "vicidial_response": "simulated", "bitrix_movido_a": "C90:3"}
```

**Nota Vicidial:** el servidor redirige HTTP→HTTPS (307) con certificado SSL de IP inválido — el cliente usa `follow_redirects=True, verify=False`. El 403 en producción indica que la IP del servidor no está en la whitelist de Vicidial — pendiente configuración en el servidor Vicidial. Usar `simulate=true` mientras tanto.

### Upsert de leads en nodos del agente

- **`validacion_node`** (`_upsert_lead`): inserta la fila en `leads` cuando la LADA es válida y habilitada. `ON CONFLICT (telefono) DO UPDATE` — no sobreescribe `bitrix_lead_id` si ya existe.
- **`escalate_node`** (`_upsert_lead_kpis`): actualiza la fila con KPIs completos (nombre, número a portar, compañía, municipio, recarga, temperatura, promo) y `etapa = 'escalado'`.

---

## Exportación de KPIs para BI

### Tabla `kpi_conversaciones`

Tabla aislada del agente (no la usan los nodos). Una fila por conversación. Se crea con el DDL en `db/migrations.py` (incluido en `make seed`). Las columnas nuevas incluyen `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para instancias existentes.

| Campo | Fuente |
|---|---|
| `id_conversacion`, `etapa`, `bitrix_lead_id` | Checkpoints LangGraph (`checkpoints` table, JSONB `channel_values`) |
| `creado_el` | Primer checkpoint del thread (`MIN(checkpoint->>'ts')`) |
| `estado_actual`, `empleado`, `origen`, `cerrado_el` | Bitrix `crm.deal.get` |
| `mensajes_cliente`, `mensajes_bot`, `primer_mensaje`, `texto_usuario`, `texto_agente` | `graph.aget_state()` — requiere checkpointer PG activo |
| `mensajes_humano`, `primera_respuesta`, `el_agente_respondio_el`, tiempos, `texto_humano` | Bitrix Open Lines `im.dialog.messages.get` |
| `resumen` | LLM (OpenRouter/Claude) — 3 oraciones: qué quería el cliente, cómo respondió el agente, resultado |

**Columnas de texto completo:** `texto_usuario`, `texto_agente` y `texto_humano` contienen todos los mensajes de cada actor concatenados con `\n---\n`. `texto_usuario` / `texto_agente` vienen de los `HumanMessage` / `AIMessage` de LangGraph; `texto_humano` filtra los mensajes de Bitrix Open Lines que no tienen `CONNECTOR_MID` (mensajes del asesor, no del conector externo).

**Clasificación de mensajes en Open Lines:** los mensajes del bot tienen `CONNECTOR_MID` porque se envían via imconnector, pero se distinguen de los mensajes del cliente por el prefijo `"🤖 Vera |"`. El campo `is_client` se fuerza a `False` si `is_bot` es `True`.

**`tiempo_primera_respuesta_segs`:** se calcula como `primera_respuesta - primer_msg_cliente_ts` usando timestamps de Bitrix para ambos extremos (evita el offset del debounce 10s que existe en `creado_el` del checkpoint). Bitrix devuelve los timestamps como ISO 8601 (`"2026-06-11T21:13:24+03:00"`), no como Unix epoch. Valores negativos se clampean a 0 (misma resolución de 1s).

### Job nocturno (`jobs/kpi_export.py`)

- Corre a las **3am America/Monterrey** via APScheduler (`id="kpi_export"`)
- Fuente: tabla `checkpoints` (últimos 30 días, máx 500 threads), no la tabla `leads`
- **Optimización delta:** solo procesa conversaciones nuevas (no están en `kpi_conversaciones`) o con actividad en las últimas 24h. Evita re-procesar el histórico completo en cada ejecución.
- **Resumen LLM reutilizado:** si la conversación ya tiene `resumen` en la tabla, se reutiliza sin llamar al LLM — solo conversaciones nuevas pagan el costo de ~2-3s del LLM.
- Procesa en lotes de 50 con 0.3s de pausa entre lotes para no saturar el event loop
- Upsert por `id_conversacion` → seguro re-ejecutar
- `_ensure_graph_initialized()`: en el proceso FastAPI el grafo ya está listo; en standalone inicializa un pool psycopg con timeout de 8s
- **`solicitud_enviada_al_agente_el`:** pendiente v2 (no hay timestamp de escalación en el estado actual)

### Reporte diario por correo (`jobs/email_report.py`)

- Corre a las **00:00 America/Monterrey** via APScheduler (`id="kpi_email_report"`) — job independiente del kpi_export
- **Contenido:** correo HTML con KPIs acumulados del mes + CSV adjunto con el detalle
- **Rango de datos:** del día 1 del mes en curso hasta el día actual (acumulado mensual). Ejemplo: el reporte del 5 de junio incluye conversaciones del 1 al 5 de junio.
- **Transporte:** SMTP SSL puerto 465 vía `smtplib` estándar en executor (sin dependencias adicionales)
- **Destinatarios:** configurados en `REPORT_EMAIL_TO` como lista separada por comas
- **KPIs en el HTML:** total de conversaciones, ventas WON, tiempo de primera respuesta promedio, tasa de automatización del bot, conversaciones con asesor humano, tiempo de cierre promedio, mensajes promedio por cliente

### Triggers manuales

```bash
# Regenerar tabla kpi_conversaciones
curl -X POST https://portabilidad.callcomcc.io/admin/kpi-export \
  -H "X-Admin-Token: <ADMIN_TOKEN>"

# Enviar reporte por correo de forma inmediata
curl -X POST https://portabilidad.callcomcc.io/admin/kpi-email \
  -H "X-Admin-Token: <ADMIN_TOKEN>"
```

Ambos endpoints retornan `{"status": "started"}` inmediatamente y corren en background. Progreso en logs (`job_kpi_export_done`, `kpi_email_sent`).

### Export a CSV

- **Comando:** `make export_kpi`
- **Ruta en contenedor:** `/app/reporteskpi/kpi_conversaciones_{YYYYMMDD_HHMM}.csv`
- **Ruta en host:** `./reporteskpi/kpi_conversaciones_{YYYYMMDD_HHMM}.csv` (volumen bind mount en `docker-compose.yml`)
- Encoding `utf-8-sig` (compatible con Excel / Power BI sin problemas de tildes)
- La carpeta `./reporteskpi/` está en `.gitignore` — los CSVs no se suben al repo

---

## Trazabilidad de eventos Bitrix (`bitrix_eventos`)

Tabla independiente de `kpi_conversaciones`. Una fila por evento del canal Bitrix Open Lines: mensajes (usuario/bot/humano) y cambios de stage. Permite reconstruir el timeline completo de cada deal con duración exacta entre stages.

### Tabla `bitrix_eventos`

| Campo | Descripción |
|---|---|
| `id_conversacion` | Thread del agente (teléfono o `tg_...`) |
| `deal_id` | ID del deal en Bitrix |
| `chat_id` | ID interno del chat en Bitrix IM (de Redis `connector_chat:{phone}`) |
| `bitrix_conversation_id` | ID de la sesión Open Lines en Bitrix (ej. `2602658` = `IMOL_2602658`) |
| `telefono` | Número del lead |
| `message_id` | ID del mensaje en Bitrix (o `stage_{id}_{ts}` para cambios de stage) |
| `fecha_evento` | Timestamp exacto del mensaje o cambio de stage |
| `tipo_actor` | `usuario` / `bot` / `humano` / `sistema` |
| `texto` | Contenido del mensaje o `"Etapa → Prospecto"` para eventos sistema |
| `stage_id` | Stage vigente en ese momento (`C90:NEW`, `C90:WON`, etc.) |
| `stage_nombre` | Nombre legible (`Lead Nuevo / IA Porta`, `Venta`, etc.) |
| `empleado_id` | Agente asignado al deal |
| `stage_anterior` | Stage del que venía el deal (solo eventos `sistema`) |
| `stage_anterior_nombre` | Nombre legible del stage anterior |
| `duracion_en_stage_segs` | Segundos que el deal estuvo en `stage_anterior` antes de esta transición |
| `duracion_formateada` | Formato legible: `"8m 48s"`, `"1h 22m 05s"` |
| `ultimo_mensaje_usuario` | Último texto enviado por el cliente al momento del cambio de stage |
| `fecha_ultimo_usuario` | Timestamp de ese mensaje (desde Bitrix Open Lines) |
| `ultimo_mensaje_bot` | Última respuesta de Vera al momento del cambio de stage (sin prefijo `🤖 Vera \|`) |
| `fecha_ultimo_bot` | Timestamp de esa respuesta |
| `ultimo_mensaje_humano` | Último mensaje del asesor humano al momento del cambio de stage |
| `fecha_ultimo_humano` | Timestamp de ese mensaje |

**Nota:** los campos `ultimo_mensaje_*` y `fecha_ultimo_*` se capturan únicamente en eventos `tipo_actor = 'sistema'` (cambios de stage), consultando `im.dialog.messages.get` en el momento exacto del webhook. Si el deal no tiene `chat_id` en Redis aún, estos campos quedan vacíos.

### Webhook de automatización (`POST /bitrix/stage-event`)

Endpoint que recibe el webhook de las reglas de automatización de Bitrix cuando un deal cambia de stage (manual o por el bot).

**Configuración de la regla en Bitrix24** — disparador "Al mover el deal a esta etapa", acción "Webhook saliente":
- **URL:** `https://portabilidad.callcomcc.io/bitrix/stage-event`
- **Campos a enviar:**

| Campo | Valor Bitrix |
|---|---|
| `deal_id` | `{=Document:ID}` |
| `stage_id` | `{=Document:STAGE_ID}` |
| `prev_stage` | `{=Document:PREVIOUS_STAGE_ID}` |

Si `stage_id` no viene en el payload, el endpoint lo consulta directamente a Bitrix vía `crm.deal.get`. La duración se calcula como diferencia entre el evento previo registrado en la tabla y el timestamp del webhook. Para el **primer evento de un deal** (sin historial previo en la tabla), se consulta `crm.stagehistory.list` para obtener cuándo entró al stage anterior y calcular la duración real.

**Mapa de stages** (pipeline 90):

| Stage ID | Nombre |
|---|---|
| `C90:NEW` | Lead Nuevo / IA Porta |
| `C90:PROSPECTO` | Prospecto |
| `C90:UC_8WB2DT` | Escalamiento Humano |
| `C90:SEGUIMIENTO` | Seguimiento |
| `C90:1` | Rescate 1 |
| `C90:2` | Rescate 2 |
| `C90:3` | Rescate 3 |
| `C90:WON` | Venta |
| `C90:LOSE` | Caído |
| `C90:8` | Recuperación |
| `C90:PREPAYMENT_INVOIC` | Recuperación |

### Módulo `jobs/kpi_eventos.py`

- `upsert_deal_timeline(deal_id, id_conversacion, telefono, stage_id, fecha_entrada, prev_stage, duracion_prev_segs, empleado_id)` — llamado desde `bitrix_stage_event` como `asyncio.create_task` en cada webhook de cambio de stage. Upsert en `bitrix_deal_timeline`.
- `upsert_eventos_from_bitrix()` — llamado desde `kpi_export._upsert()` para poblar mensajes e historial de stages con datos frescos de Bitrix.
- `seed_from_kpi_conversaciones()` — migración inicial opcional, disparable via `POST /admin/bitrix-eventos-seed`.

### Tabla pivote `bitrix_deal_timeline`

Una fila por deal. Se popula automáticamente desde el webhook `POST /bitrix/stage-event` en cada cambio de stage. Complementa `bitrix_eventos` para análisis agregados de funnel y tiempos sin necesidad de agrupar la tabla de eventos.

| Campo | Descripción |
|---|---|
| `deal_id` | PK — ID del deal en Bitrix |
| `id_conversacion` | Thread del agente (teléfono o `tg_...`) |
| `telefono` | Número del lead |
| `fecha_{stage}` | Primera vez que el deal entró a cada stage (COALESCE preserva el valor original en upserts posteriores) |
| `duracion_{stage}_segs` | Segundos que el deal pasó en ese stage antes de avanzar al siguiente (NUMERIC; vacío si el deal aún está en ese stage) |
| `empleado_id` | ID del asesor asignado al deal — se actualiza en cada cambio de stage (siempre refleja el asesor más reciente) |
| `updated_at` | Timestamp del último upsert |

**Stages cubiertos:** `new`, `prospecto`, `escalamiento`, `seguimiento`, `rescate1`, `rescate2`, `rescate3`, `won`, `lose`, `recuperacion`.

**Reglas de upsert:**
- `fecha_*` — se preserva la primera entrada (COALESCE); si el deal regresa a un stage ya visitado, la fecha original no cambia.
- `duracion_*` — se actualiza con el nuevo valor si llega uno (el deal puede re-entrar y recalcular).
- `empleado_id` — siempre sobreescribe con el asesor asignado en el webhook más reciente.

**Nota:** `empleado_id` solo se obtiene cuando el webhook no incluye `stage_id` directo y el endpoint llama a `crm.deal.get`. Si la regla de automatización en Bitrix envía `stage_id` en el payload, `empleado_id` puede quedar vacío — en ese caso se puede complementar con `bitrix_eventos.empleado_id` del evento `sistema` correspondiente.

### Consultas útiles

```sql
-- Timeline completo de un deal con snapshot de mensajes en cada transición
SELECT fecha_evento, stage_anterior_nombre || ' → ' || stage_nombre AS transicion,
       duracion_formateada,
       ultimo_mensaje_usuario, fecha_ultimo_usuario,
       ultimo_mensaje_bot, fecha_ultimo_bot,
       ultimo_mensaje_humano, fecha_ultimo_humano
FROM bitrix_eventos
WHERE deal_id = '2302394' AND tipo_actor = 'sistema'
ORDER BY fecha_evento;

-- Timeline completo con todos los eventos
SELECT fecha_evento, tipo_actor, stage_nombre, stage_anterior_nombre, duracion_formateada, texto
FROM bitrix_eventos
WHERE deal_id = '2302394'
ORDER BY fecha_evento;

-- Funnel de conversión por stage (tabla pivote)
SELECT
  COUNT(*) FILTER (WHERE fecha_new IS NOT NULL)          AS new,
  COUNT(*) FILTER (WHERE fecha_prospecto IS NOT NULL)    AS prospecto,
  COUNT(*) FILTER (WHERE fecha_escalamiento IS NOT NULL) AS escalamiento,
  COUNT(*) FILTER (WHERE fecha_rescate1 IS NOT NULL)     AS rescate1,
  COUNT(*) FILTER (WHERE fecha_rescate2 IS NOT NULL)     AS rescate2,
  COUNT(*) FILTER (WHERE fecha_rescate3 IS NOT NULL)     AS rescate3,
  COUNT(*) FILTER (WHERE fecha_won IS NOT NULL)          AS won,
  COUNT(*) FILTER (WHERE fecha_lose IS NOT NULL)         AS lose
FROM bitrix_deal_timeline;

-- Tiempo promedio en cada stage (análisis de cuellos de botella)
SELECT
  AVG(duracion_new_segs) / 60          AS min_promedio_en_new,
  AVG(duracion_prospecto_segs) / 60    AS min_promedio_en_prospecto,
  AVG(duracion_escalamiento_segs) / 60 AS min_promedio_en_escalamiento
FROM bitrix_deal_timeline;

-- Análisis por asesor: deals cerrados y tiempo promedio hasta WON
SELECT empleado_id,
       COUNT(*) AS deals_won,
       AVG(EXTRACT(EPOCH FROM (fecha_won - fecha_new))) / 60 AS min_promedio_cierre
FROM bitrix_deal_timeline
WHERE fecha_won IS NOT NULL
GROUP BY empleado_id
ORDER BY deals_won DESC;
```

---

## Dashboard KPI (Angular)

Panel web en `dashboard/` — accesible en `https://portabilidad.callcomcc.io/dashboard/`.

### Autenticación

- **Login:** `POST /auth/login` con `{ email, password }` → JWT HS256 con expiración de 8h
- **Tabla:** `dashboard_users` (PostgreSQL) — columnas: `id`, `email`, `nombre`, `password_hash` (bcrypt), `activo`, `last_login`
- **Usuarios iniciales:** sbecerra@callcom.mx, passpace04@gmail.com (L. Salazar), mbecerra@callcom.mx — contraseña `Callcom.2025`
- **Seed:** `docker compose exec api python scripts/seed_dashboard_users.py`
- **Compatibilidad:** el header `X-Admin-Token` sigue funcionando para scripts/curl (backward compatible)

### Secciones del dashboard

1. **Telcel Portabilidad** — KPI cards, distribución por stage (doughnut), mensajes por actor (bar), tabla de conversaciones paginada con filtros (fecha, stage, búsqueda)
2. **Meta Ads — Portabilidad 2 Callcom** — gasto, impresiones, clics, CTR, conversaciones WhatsApp, CPL; gráfica gasto vs conversaciones; tabla detallada. Filtro por fecha y nivel (campaña/conjunto/anuncio)
3. **Atribución UTM** — leads con UTM capturado, ventas atribuidas; gráfica por fuente; tabla por campaña con tasa de conversión; tabla por Ad ID
4. **Megacable** — KPI cards del agente Megacable (BD externa), gráficas de estado y mensajes por actor, tabla de conversaciones recientes. Filtro por fecha independiente

### Notas del dashboard

- **`@ViewChild` + `@if`:** los canvas de Chart.js viven dentro de bloques `@if` de Angular. `renderCharts()` se llama con `setTimeout(0)` después de setear `loading = false` para asegurar que el DOM ya renderizó antes de acceder al canvas. Sin el `setTimeout`, el `@ViewChild` devuelve `undefined`.
- **Rebuild:** cualquier cambio en `dashboard/` requiere `docker compose build dashboard && docker compose up -d dashboard`.

---

## Atribución UTM / Click-to-WhatsApp

### Captura en el webhook

Cuando un lead llega desde un anuncio Meta Ads Click-to-WhatsApp, Meta incluye un objeto `referral` en el payload del webhook:

```json
{
  "referral": {
    "source_id": "120246547033570677",   // Ad ID
    "source_type": "ad",
    "source_url": "https://...?utm_source=facebook&utm_campaign=...",
    "ctwa_clid": "ARAkLkA8..."           // Click-to-WhatsApp Click ID
  }
}
```

**Flujo:**
1. `parse_whatsapp_message()` (`handlers.py`) retorna `(phone, text, message_id, referral)` — 4 campos
2. El webhook guarda el referral en Redis como `wa_referral:{phone}` (TTL 24h)
3. `_upsert_lead_primer_contacto()` en `validacion_node` lee ese Redis, parsea los UTMs de `source_url` y hace upsert en `leads`

**Columnas UTM en `leads`:** `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `ctwa_clid`, `ad_id`, `referral_source_url`

**Política de no sobreescritura:** el `ON CONFLICT` solo actualiza los campos UTM si están vacíos en la fila existente — el primer anuncio que origina el lead siempre se preserva.

### Clave Redis

| Clave | Contenido |
|---|---|
| `wa_referral:{phone}` | JSON del objeto `referral` del webhook (TTL 24h) |

---

## Meta Ads Integration

### Caso A — Ad Insights (`integrations/meta/insights.py`)

Consulta métricas de la cuenta **Portabilidad 2 Callcom** (`act_3292969264212775`) vía `facebook-business` SDK.

- **Función:** `get_insights(date_preset, since, until, level)` — async (ejecuta en executor)
- **Campos:** `impressions`, `reach`, `clicks`, `spend`, `cpc`, `cpm`, `ctr`, `actions`
- **Conversaciones WhatsApp:** extrae `onsite_conversion.total_messaging_connection` de `actions`
- **Niveles:** `campaign` / `adset` / `ad` — seleccionable desde el dashboard
- **Init del SDK:** solo con `access_token`, sin `app_secret` — evita conflicto de `appsecret_proof` con otras apps del entorno

**Endpoint:** `GET /admin/meta-insights?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&level=campaign`

### Caso B — Conversions API / CAPI (`integrations/meta/conversions.py`)

Envía eventos de conversión a Meta para optimización del algoritmo de anuncios.

**Pixel:** `1654668329217239` (Pixel de Portabilidad — business "Portabilidad Secundaria Callcom")

**Eventos:**
- **`Purchase`** → cuando `job_bitrix_sync` detecta transición a `C90:WON`. Incluye teléfono hasheado SHA-256, `ctwa_clid` (si existe) y recarga como valor de conversión
- **`Lead`** → cuando `job_bitrix_sync` detecta transición a `C90:PROSPECTO`

**Flujo automático:**
```
Asesor mueve deal a C90:WON en Bitrix
        ↓
job_bitrix_sync (cada 30 min) detecta el cambio de stage
        ↓
_fire_capi_if_needed() → lee telefono + ctwa_clid desde leads
        ↓
send_purchase_event() → POST /v20.0/{pixel_id}/events (CAPI)
```

**Deduplicación:** `event_id = "won_{deal_id}"` — Meta descarta duplicados con el mismo `event_id` en 7 días.

**Endpoint de prueba:**
```bash
curl -X POST https://portabilidad.callcomcc.io/admin/capi-test \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"telefono":"521XXXXXXXXXX","deal_id":"12345","evento":"Purchase","recarga":200}'

# simulate=true para validar sin enviar a Meta
```

---

## Integración Megacable (BD externa)

El dashboard incluye una sección de KPIs para el agente Megacable que vive en una BD PostgreSQL separada (`bot_megacable`, host `147.79.78.75:5433`).

**Módulo:** `integrations/megacable_db.py` — `fetch_megacable(query, *args)` abre una conexión asyncpg por consulta (sin pool — solo lectura, baja frecuencia).

**Tablas consultadas:** `conversations`, `conversation_history`, `agent_runs`

**Endpoint:** `GET /admin/megacable-data?desde=YYYY-MM-DD&hasta=YYYY-MM-DD`

**Nota:** el cliente asyncpg de la BD interna (Telcel) requiere objetos `datetime` como parámetros, no strings. Los endpoints que filtran por fecha convierten `date` → `datetime(year, month, day, tzinfo=utc)` antes de pasar a la query.

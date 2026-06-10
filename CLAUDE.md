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
| Base de datos | PostgreSQL 16 | Leads, conversaciones, base de conocimiento |
| Caché / Cola | Redis 7 + arq | Contexto de sesión y cola de mensajes |
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
│   │   ├── client.py        # BitrixClient — webhook REST (crear lead, mover etapa)
│   │   ├── oauth.py         # OAuth tokens — exchange, refresh, Redis-backed
│   │   └── connector.py     # imconnector API — mirror de mensajes en Open Lines
│   ├── telegram/
│   │   ├── client.py        # TelegramClient.send_message()
│   │   └── handlers.py      # parse_update() — extrae chat_id, text, phone
│   └── postgres/
│       └── client.py        # Pool asyncpg — execute/fetch/fetchrow parametrizados
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
| `BITRIX_STAGE_LISTO` | Stage ID para "Listo para Portabilidad" (ej. `C90:NEW`) |
| `BITRIX_CLIENT_ID` | Client ID de la app local OAuth de Bitrix24 |
| `BITRIX_CLIENT_SECRET` | Client Secret de la app local OAuth |
| `BITRIX_CONNECTOR_ID` | ID del conector imconnector registrado en el portal (`telegram_ai_agent`) |
| `BITRIX_CONNECTOR_LINE_ID` | ID del Open Channel en Bitrix24 (actualmente `542`) |
| `BITRIX_PUBLIC_URL` | URL pública del servidor para el callback OAuth de Bitrix |
| `ANTHROPIC_API_KEY` | API key de Claude (Anthropic) |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `REDIS_URL` | URL de conexión a Redis |
| `DEBOUNCE_WINDOW_MS` | Ventana de debounce en ms (0 = desactivado, producción: `5000`) |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (canal de pruebas) |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para validar webhooks de Telegram (X-Telegram-Bot-Api-Secret-Token) |

---

## Pipeline operativo de Bitrix (pipeline ID 90 — deals, no leads)

El pipeline usa `crm.deal.*` con `CATEGORY_ID=90`. Las etapas siguen el formato `C90:*`.

| Etapa | Stage ID | Significado | Regla automática |
|---|---|---|---|
| Pipeline IA Porta | `C90:NEW` | Deal en manos del bot | 24h sin Venta Exitosa → Recuperación |
| Listo para Portabilidad | `C90:PREPARATION` | Datos completos, listo para asesor | — |
| Venta | `C90:WON` | Solo leads con Venta Exitosa | — |
| Recuperación | `C90:8` | Lead a reactivar | 72h sin Venta Exitosa → Caído |
| Caído | `C90:LOSE` | Lead perdido (con tipificación) | — |

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
[objeciones] → RAG en tabla objeciones (max 3 rebates)
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

Los archivos usan placeholders `{NOMBRE}` que `render_prompt()` (`agents/portabilidad/utils.py`) sustituye en tiempo de ejecución con las constantes de `context.py` y variables dinámicas (monto de recarga, promos, etc.).

---

## Integración Bitrix24 Open Lines (imconnector)

El espejeo de mensajes usa la API `imconnector` vía OAuth (no el webhook REST básico).

### Flujo bidireccional

```
Usuario (Telegram/WhatsApp)
    │  mensaje
    ▼
webhook → send_user_message() → imconnector.send.messages → Open Lines 542
    │
    ▼  (debounce + agente)
send_bot_message() → imconnector.send.messages → mismo chat en Open Lines
    
Asesor responde en Bitrix Open Lines
    │
    ▼  (polling cada 30s — connector_poll.py)
im.dialog.messages.get → _forward_to_user() → Telegram o WhatsApp
```

### Claves Redis del conector

| Clave Redis | Contenido |
|---|---|
| `connector_ext_chat:{phone}` | external_chat_id para la sesión activa (TTL 24h) |
| `connector_session:{phone}` | session_id de Open Lines devuelto por Bitrix |
| `connector_chat:{phone}` | chat_id interno de Bitrix (para im.dialog.messages.get) |
| `connector_last_msg:{phone}` | cursor: ID del último mensaje procesado del asesor |
| `connector_delivered:{msg_id}` | deduplicación de mensajes ya reenviados (TTL 24h) |

### Notas críticas de imconnector

- **Auth:** el token OAuth va en el **body JSON** como `"auth": token`, NO como header `Authorization: Bearer`.
- **Estructura de mensajes:** claves **lowercase** (`user`, `message`, `chat`). Uppercase (`USER`, `MESSAGE`) no funciona.
- **Conector activo:** `telegram_ai_agent` (ya registrado en el portal b24-ahyle8.bitrix24.mx, activado en línea 542). No usar conectores nuevos — registrar uno nuevo con una app local requiere placement handler de marketplace.
- **Registro OAuth:** flujo en `GET /bitrix/auth` → Bitrix redirige a `BITRIX_PUBLIC_URL/bitrix/app` → tokens en Redis `bitrix:oauth_tokens`. Re-ejecutar si expira el refresh_token.

---

## Notas de desarrollo

- **Promos:** configuración versionada en tabla `promos`. Cuando Telcel publique nuevas, actualizar `load_promos.py` y correr `make seed`. NUNCA hardcodear precios en el agente.
- **LADAs:** tabla técnica, no parte del guion. El bot la consulta internamente para decidir si continúa el flujo o deriva a CAC.
- **Versiones de prompt:** editar los archivos en `prompts/` directamente. Para historial de versiones usar git. La carpeta `knowledge/prompts/` es para specs de auditoría, no para los prompts activos.
- **Jobs timezone:** siempre `America/Monterrey` explícito. El horario de portabilidad es L-S 9am–9pm; sin domingos.
- **Debounce:** configurar `DEBOUNCE_WINDOW_MS` en `.env`. Valor actual en producción: `5000` ms. Poner `0` solo en pruebas unitarias o entornos donde cada mensaje debe procesarse de forma independiente.
- **Telegram:** canal de pruebas que corre el mismo agente y el mismo debounce que WhatsApp. El `thread_id` de LangGraph es `str(chat_id)` en Telegram y `phone` en WhatsApp. El `phone` en Telegram tiene prefijo `tg_` (ej. `tg_8211184685`).
- **Bitrix deals vs leads:** el pipeline 90 es de **deals** (`crm.deal.*`). No usar `crm.lead.*` — son entidades distintas con etapas distintas.
- **Connector poll:** `connector_poll.py` corre como `asyncio.Task` en el lifespan de FastAPI (no como job de APScheduler). Intervalo: 30 segundos.

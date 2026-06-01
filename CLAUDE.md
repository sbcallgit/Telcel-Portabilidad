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
| Escalamiento | Chatwoot | Handoff al asesor humano |

---

## Estructura de carpetas

```
bot_telcel_portabilidad/
├── agents/                  # Agente de venta (LangGraph)
│   └── portabilidad/
│       ├── state.py         # Estado del agente (PortabilidadState TypedDict)
│       ├── graph.py         # Grafo LangGraph — conecta todos los nodos
│       └── nodes/
│           ├── validacion.py    # Valida LADA/región (primer filtro)
│           ├── sondeo.py        # Conoce al cliente: recarga, uso, necesidad
│           ├── clasificacion.py # Temperatura: caliente/tibio/frío
│           ├── oferta.py        # Presenta la promo correcta
│           ├── objeciones.py    # Rebate objeciones (max 3 intentos)
│           ├── cierre.py        # Captura datos para handoff
│           └── escalate.py      # Transfiere a Chatwoot con contexto completo
│
├── integrations/            # Conexiones con servicios externos
│   ├── exceptions.py        # WhatsAppError, BitrixError, ChatwootError, DatabaseError
│   ├── whatsapp/
│   │   ├── client.py        # WhatsAppClient.send_message() — httpx + tenacity
│   │   └── handlers.py      # verify_webhook_signature() — HMAC-SHA256
│   ├── bitrix/
│   │   └── client.py        # BitrixClient — crear lead, mover etapa, tipificar
│   ├── chatwoot/
│   │   └── client.py        # ChatwootClient — create_conversation, send_message
│   └── postgres/
│       └── client.py        # Pool asyncpg — execute/fetch/fetchrow parametrizados
│
├── api/                     # Endpoints HTTP
│   ├── main.py              # App FastAPI — lifespan, middleware de logging
│   └── routes/
│       ├── health.py        # GET /health — status ok/degraded + check de DB
│       └── webhooks.py      # POST/GET /webhooks/telcel — entry point de WhatsApp
│
├── db/                      # Capa de datos
│   ├── models.py            # Modelos Pydantic: Lead, Lada, Promo, CAC, Objecion
│   └── migrations.py        # DDL CREATE TABLE para todas las tablas
│
├── jobs/                    # Tareas programadas
│   └── seguimientos.py      # Cadencia de seguimientos automáticos (APScheduler)
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
| `BITRIX_WEBHOOK_URL` | URL del webhook entrante de Bitrix24 |
| `CHATWOOT_API_KEY` | Token para la API de Chatwoot |
| `ANTHROPIC_API_KEY` | API key de Claude (Anthropic) |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `REDIS_URL` | URL de conexión a Redis |

---

## Pipeline operativo de Bitrix (5 etapas)

| Etapa | Significado | Regla automática |
|---|---|---|
| Pipeline IA Porta | Lead en manos del bot | 24h sin Venta Exitosa → Recuperación |
| Listo para Portabilidad | Datos completos, listo para asesor | — |
| Venta | Solo leads con Venta Exitosa | — |
| Recuperación | Lead a reactivar | 72h sin Venta Exitosa → Caído |
| Caído | Lead perdido (con tipificación) | — |

---

## Seguridad y privacidad (LFPDPPP)

- **SQL injection:** SOLO queries parametrizadas (`$1`, `$2`). NUNCA f-strings con datos de usuario.
- **Logs:** teléfonos y nombres siempre enmascarados (`mask_phone()`). Nunca datos completos.
- **WhatsApp:** NIP NUNCA se pide ni procesa. La firma HMAC-SHA256 valida cada webhook.
- **Datos sensibles:** solo en PostgreSQL/Bitrix, con política de retención. Sin INE/CURP/bancarios por WhatsApp.
- **Solicitudes ARCO:** "borra mis datos" se canaliza al proceso de derechos ARCO, nunca se ignora.

---

## Flujo del agente (embudo)

```
WhatsApp (lead Meta Ads)
        │
        ▼
[webhook] → cola Redis (arq)
        │
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
[escalate] → Chatwoot (asesor humano) + Bitrix: etapa "Listo para Portabilidad"
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

## Notas de desarrollo

- **Promos:** configuración versionada en tabla `promos`. Cuando Telcel publique nuevas, actualizar `load_promos.py` y correr `make seed`. NUNCA hardcodear precios en el agente.
- **LADAs:** tabla técnica, no parte del guion. El bot la consulta internamente para decidir si continúa el flujo o deriva a CAC.
- **Versiones de prompt:** guardar en `knowledge/prompts/` con tag de versión y hallazgos de auditoría que resuelve cada una.
- **Jobs timezone:** siempre `America/Monterrey` explícito. El horario de portabilidad es L-S 9am–9pm; sin domingos.

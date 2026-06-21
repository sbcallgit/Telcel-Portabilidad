# Manual de Implementación: Canal WhatsApp ↔ Bitrix24 vía imconnector / Open Lines

**Versión:** 1.0  
**Proyecto de referencia:** Bot Telcel Portabilidad — Vera  
**Portal Bitrix24:** `b24-ahyle8.bitrix24.mx`  
**Open Channel activo:** Línea 542  
**Conector registrado:** `whatsapp_vera`

---

## Índice

1. [Conceptos clave](#1-conceptos-clave)
2. [Prerrequisitos](#2-prerrequisitos)
3. [Variables de entorno necesarias](#3-variables-de-entorno-necesarias)
4. [Paso 1 — Crear la App Local en Bitrix24](#4-paso-1--crear-la-app-local-en-bitrix24)
5. [Paso 2 — Flujo OAuth (autorización inicial)](#5-paso-2--flujo-oauth-autorización-inicial)
6. [Paso 3 — Registrar y activar el conector (setup único)](#6-paso-3--registrar-y-activar-el-conector-setup-único)
7. [Paso 4 — Flujo de mensajes de entrada (usuario → Bitrix)](#7-paso-4--flujo-de-mensajes-de-entrada-usuario--bitrix)
8. [Paso 5 — Flujo de mensajes de salida (bot → Bitrix, mismo chat)](#8-paso-5--flujo-de-mensajes-de-salida-bot--bitrix-mismo-chat)
9. [Paso 6 — Polling de mensajes del asesor (Bitrix → usuario)](#9-paso-6--polling-de-mensajes-del-asesor-bitrix--usuario)
10. [Gestión de sesiones con Redis](#10-gestión-de-sesiones-con-redis)
11. [Reglas críticas — errores frecuentes](#11-reglas-críticas--errores-frecuentes)
12. [Diagrama completo del canal](#12-diagrama-completo-del-canal)
13. [Comandos de diagnóstico](#13-comandos-de-diagnóstico)

---

## 1. Conceptos clave

| Término | Descripción |
|---|---|
| **imconnector** | API propietaria de Bitrix24 para conectar canales externos (WhatsApp, Telegram, etc.) a Open Lines. Distinta del webhook REST básico. |
| **Open Lines (imopenlines)** | Módulo de Bitrix24 de atención al cliente multicanal. Cada canal externo conectado recibe y envía mensajes en un chat unificado para el asesor. |
| **Open Channel** | Configuración de una línea de atención dentro de Open Lines (colas, asignación de asesores, horarios). Identificado por un `LINE_ID` numérico. |
| **Conector personalizado** | Identificador único (`CONNECTOR_ID`) que representa el canal externo ante Bitrix. Debe estar registrado y activado en el Open Channel antes de usarse. |
| **external_chat_id** | ID que el servidor externo asigna a cada conversación. Bitrix lo usa para agrupar todos los mensajes de un mismo usuario en un solo chat. Si cambia, Bitrix abre una sesión nueva y crea un deal nuevo. |
| **session_id / chat_id** | IDs que Bitrix devuelve al crear la sesión. `chat_id` se usa para leer mensajes del asesor vía `im.dialog.messages.get`. |
| **App Local** | Aplicación registrada en el portal Bitrix24 que habilita el flujo OAuth. Necesaria para obtener tokens con permisos de `imconnector`. |

---

## 2. Prerrequisitos

- Servidor con **URL pública HTTPS** (requerida por Bitrix24 para OAuth y webhooks).
- **Redis** disponible para almacenar tokens OAuth y sesiones.
- Acceso de administrador al portal Bitrix24.
- Open Channel creado en Bitrix24 (Contact Center → Open Lines → Nueva Línea). Anotar el `LINE_ID`.

---

## 3. Variables de entorno necesarias

```env
# Bitrix24 — App Local OAuth
BITRIX_CLIENT_ID=local.xxxxxxxxxxxxxxxxxx
BITRIX_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Bitrix24 — Conector y línea
BITRIX_CONNECTOR_ID=whatsapp_vera          # ID único del conector (tú lo defines)
BITRIX_CONNECTOR_LINE_ID=542               # ID del Open Channel en Bitrix

# URL pública del servidor (para el callback OAuth)
BITRIX_PUBLIC_URL=https://tu-dominio.com

# Redis
REDIS_URL=redis://redis:6379
```

> **Nota:** `BITRIX_CONNECTOR_ID` es un string arbitrario que defines tú. Debe ser único dentro del portal. Una vez registrado, no cambiarlo — Bitrix lo usa para enrutar todos los mensajes de esa fuente.

---

## 4. Paso 1 — Crear la App Local en Bitrix24

Una App Local habilita OAuth sin necesidad de publicar la app en el Marketplace.

1. Ir a **Bitrix24 → Aplicaciones → Desarrollador → Otras → App Local**.
2. Crear nueva aplicación con los siguientes parámetros:

   | Campo | Valor |
   |---|---|
   | Título | `WhatsApp Vera Bot` (o el nombre de tu canal) |
   | Tipo | **Servidor** |
   | URL del handler | `https://tu-dominio.com/bitrix/install` |
   | URL de inicio | `https://tu-dominio.com/bitrix/app` |
   | Permisos (scopes) | `imopenlines`, `imconnector`, `crm`, `im` |

3. Guardar y copiar **Client ID** y **Client Secret** al `.env`.

**Endpoint en el servidor (FastAPI):**

```python
# GET /bitrix/app — recibe el ?code= del redirect OAuth
@router.get("/bitrix/app", response_class=HTMLResponse)
async def bitrix_oauth_callback(code: str = Query(default="")) -> str:
    await exchange_code(code)   # intercambia code → access_token + refresh_token
    return "<h3>✅ Autorización exitosa.</h3>"

# POST /bitrix/install — hook requerido por Bitrix al instalar la app
@router.post("/bitrix/install")
async def bitrix_install_hook() -> dict:
    return {"status": "ok"}
```

---

## 5. Paso 2 — Flujo OAuth (autorización inicial)

El flujo solo se ejecuta **una vez** (o cuando el refresh_token expira).

### 5.1 Autorizar

Abrir en el navegador como administrador del portal:

```
https://{BITRIX_DOMAIN}/oauth/authorize/
    ?client_id={BITRIX_CLIENT_ID}
    &response_type=code
    &redirect_uri=https://tu-dominio.com/bitrix/app
```

Bitrix redirige a `https://tu-dominio.com/bitrix/app?code=XXXX`. El endpoint intercambia el código y guarda los tokens en Redis bajo la clave `bitrix:oauth_tokens`.

### 5.2 Estructura de tokens en Redis

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_at": 1719000000,
  "domain": "https://b24-ahyle8.bitrix24.mx"
}
```

### 5.3 Renovación automática

La función `get_token()` renueva automáticamente el `access_token` si faltan menos de 5 minutos para que expire, usando el `refresh_token`:

```python
async def get_token() -> str:
    data = json.loads(await redis.get("bitrix:oauth_tokens"))
    if time.time() >= data["expires_at"] - 300:
        data = await refresh_tokens(data["refresh_token"])
    return data["access_token"]
```

> **Importante:** el `refresh_token` de Bitrix24 tiene una vigencia larga pero **no es infinita**. Si el servidor está apagado por semanas, puede expirar y se debe re-autorizar manualmente.

### 5.4 Autenticación en llamadas imconnector

A diferencia de la REST API estándar de Bitrix, **imconnector requiere el token en el body JSON**, no como header `Authorization: Bearer`:

```python
# CORRECTO — token en el body
await client.post(url, json={**params, "auth": token})

# INCORRECTO — no funciona con imconnector
headers = {"Authorization": f"Bearer {token}"}
```

---

## 6. Paso 3 — Registrar y activar el conector (setup único)

Solo se ejecuta una vez. Con los tokens OAuth ya guardados en Redis:

```bash
python scripts/setup_imconnector.py
```

El script ejecuta 4 pasos en orden:

### Paso 3.1 — Registrar el conector

```python
await _call("imconnector.register", {
    "ID": settings.bitrix_connector_id,     # ej. "whatsapp_vera"
    "NAME": "WhatsApp Vera Bot",
    "ICON": {"COLOR": "#25D366"},           # verde WhatsApp
})
```

### Paso 3.2 — Activar en el Open Channel

```python
await _call("imconnector.activate", {
    "CONNECTOR": settings.bitrix_connector_id,
    "LINE": settings.bitrix_connector_line_id,   # ej. "542"
    "ACTIVE": True,
})
```

### Paso 3.3 — Configurar datos del conector

```python
await _call("imconnector.set.data", {
    "CONNECTOR": settings.bitrix_connector_id,
    "LINE": settings.bitrix_connector_line_id,
    "DATA": {
        "NAME": "WhatsApp Vera Bot",
        "TITLE": "WhatsApp",
    }
})
```

### Paso 3.4 — Suscribir evento (opcional)

Si se quiere recibir mensajes del asesor por webhook en lugar de polling:

```python
await _call("event.bind", {
    "event": "ONIMCONNECTORMESSAGEADD",
    "handler": f"{settings.bitrix_public_url}/webhooks/connector",
})
```

> En este proyecto se usa **polling** cada 30s en lugar de webhook para simplificar la infraestructura y evitar configurar un endpoint público adicional.

### Listar Open Channels disponibles

```bash
python scripts/setup_imconnector.py --list-lines
```

### Verificar estado del conector

```bash
python scripts/setup_imconnector.py --status
```

---

## 7. Paso 4 — Flujo de mensajes de entrada (usuario → Bitrix)

Cada mensaje de WhatsApp que llega al webhook se espeja en Bitrix vía `imconnector.send.messages`.

### 7.1 Generar o reutilizar el external_chat_id

```python
async def _get_or_create_external_chat_id(phone: str) -> str:
    redis = await get_redis()
    key = f"connector_ext_chat:{phone}"
    existing = await redis.get(key)
    if existing:
        return existing                          # sesión existente → mismo deal
    new_id = f"{phone}_{int(time.time())}"       # nueva sesión → Bitrix crea deal nuevo
    await redis.setex(key, 90 * 86_400, new_id) # TTL 90 días
    return new_id
```

**Regla fundamental:** mientras el `external_chat_id` sea el mismo, Bitrix mantiene la conversación en el mismo chat y el mismo deal. Si cambia (o se usa un ID nuevo), Bitrix abre una sesión nueva y crea un deal duplicado.

### 7.2 Llamada a imconnector.send.messages

```python
result = await _call("imconnector.send.messages", {
    "CONNECTOR": "whatsapp_vera",
    "LINE": "542",
    "MESSAGES": [{
        "user": {
            "id": phone,                        # identificador único del usuario
            "name": f"WhatsApp *{phone[-4:]}",  # nombre visible para el asesor
            "phone": phone,
        },
        "message": {
            "id": f"wa_{phone}_{timestamp}",    # ID único del mensaje
            "date": timestamp,                  # Unix timestamp
            "text": text,
        },
        "chat": {
            "id": external_chat_id,             # ID de sesión (generado arriba)
            "name": f"WA {phone}",
        },
    }],
})
```

> **Las claves deben ser lowercase** (`user`, `message`, `chat`). Uppercase (`USER`, `MESSAGE`, `CHAT`) hace que imconnector ignore silenciosamente el mensaje.

### 7.3 Extraer y guardar datos de la sesión

Bitrix devuelve en la respuesta el `session_id`, `chat_id` y opcionalmente el `deal_id`:

```python
items = result.get("result", {}).get("DATA", {}).get("RESULT", [])
session_data = items[0].get("session", {}) if items else {}

session_id = str(session_data.get("ID", ""))
chat_id    = str(session_data.get("CHAT_ID", ""))
deal_id    = str(session_data.get("CRM_ENTITY_ID", "")) \
             if session_data.get("CRM_ENTITY_TYPE") == "DEAL" else ""
```

Se guardan en Redis con TTL de 24h:

```
connector_session:{phone}  → session_id
connector_chat:{phone}     → chat_id      (para polling de mensajes del asesor)
connector_deal:{phone}     → deal_id      (para actualizar el deal en el CRM)
```

### 7.4 Deal asíncrono — caso frecuente

Bitrix crea el deal de forma asíncrona al abrir la sesión imconnector. La respuesta de `imconnector.send.messages` **no siempre incluye el `deal_id`**. Si es una sesión nueva y no viene el deal_id, se lanza una tarea en background que espera 3 segundos y lo busca:

```python
if is_new_session and not deal_id:
    asyncio.create_task(_fetch_openlines_deal_async(phone))

async def _fetch_openlines_deal_async(phone: str) -> None:
    await asyncio.sleep(3)
    deal_id = await bitrix_client.buscar_deal_por_telefono(phone)
    if deal_id:
        await redis.setex(f"connector_deal:{phone}", 86_400, deal_id)
```

Esto asegura que el `deal_id` esté disponible en Redis antes de que el agente LLM comience a procesar el mensaje (con debounce de ~10s).

---

## 8. Paso 5 — Flujo de mensajes de salida (bot → Bitrix, mismo chat)

Las respuestas del bot deben aparecer en el **mismo chat** que los mensajes del usuario en Bitrix.

### 8.1 La regla de oro: mismo user.id

```python
async def send_bot_message(phone: str, text: str) -> None:
    ext_chat_id = await redis.get(f"connector_ext_chat:{phone}")
    if not ext_chat_id:
        return   # sesión no inicializada, no enviar

    await _call("imconnector.send.messages", {
        "CONNECTOR": "whatsapp_vera",
        "LINE": "542",
        "MESSAGES": [{
            "user": {
                "id": phone,              # MISMO user.id que el usuario real
                "name": f"WhatsApp *{phone[-4:]}",
                "phone": phone,
            },
            "message": {
                "id": f"bot_{phone}_{timestamp}",
                "date": timestamp,
                "text": f"🤖 Vera | {text}",   # prefijo para distinguir al bot
            },
            "chat": {
                "id": ext_chat_id,        # MISMO external_chat_id
                "name": f"WA {phone}",
            },
        }],
    })
```

> **Por qué mismo `user.id`:** si se usa un ID diferente (ej. `"bot_{phone}"`), imconnector interpreta que es un usuario distinto y abre una **segunda sesión de Open Lines**, lo que genera un **deal duplicado** en el CRM. El prefijo `"🤖 Vera |"` en el texto es lo que distingue visualmente al bot del cliente en la pantalla del asesor.

> **Por qué no usar `im.message.add`:** esta API no funciona en chats de Open Lines — devuelve `CANCELED: No puede enviar mensajes al chat especificado`. La única forma correcta de espejear mensajes del bot es vía `imconnector.send.messages`.

---

## 9. Paso 6 — Polling de mensajes del asesor (Bitrix → usuario)

Cuando un asesor humano responde en Bitrix Open Lines, el mensaje debe llegar al usuario de WhatsApp. Esto se implementa con polling periódico.

### 9.1 Inicio del polling (lifespan de FastAPI)

```python
# api/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_connector_poll()    # inicia el loop de polling
    yield
    await stop_connector_poll()     # cancela el task al apagar
```

### 9.2 Loop de polling

```python
async def _poll_loop() -> None:
    while True:
        await _poll_once()
        await asyncio.sleep(30)     # intervalo: 30 segundos
```

### 9.3 Lectura de mensajes nuevos

```python
result = await _call_poll("im.dialog.messages.get", {
    "DIALOG_ID": f"chat{chat_id}",
    "LIMIT": 20,
})
messages = result.get("result", {}).get("messages", [])
```

### 9.4 Filtros para identificar mensajes del asesor

```python
for msg in reversed(messages):
    msg_id    = int(msg.get("id", 0))
    author_id = msg.get("author_id", 0)
    params    = msg.get("params", {})

    if author_id == 0:
        continue   # mensajes del sistema

    # Los mensajes del cliente (y del bot espejado) tienen CONNECTOR_MID
    if isinstance(params, dict) and params.get("CONNECTOR_MID"):
        continue   # son del canal externo, no del asesor

    text = (msg.get("text") or "").strip()
    if text:
        # Este es un mensaje real del asesor → reenviar al usuario
        await _forward_to_user(phone, text)
```

### 9.5 Cursor y deduplicación

```python
# Cursor por teléfono — evita re-procesar mensajes ya vistos
last_id = int(await redis.get(f"connector_last_msg:{phone}") or "0")

# Primera vez: sembrar el cursor sin reenviar el histórico
if last_id == 0 and messages:
    max_id = max(int(m["id"]) for m in messages)
    await redis.setex(f"connector_last_msg:{phone}", 86_400, str(max_id))
    return []

# Deduplicación adicional por message_id
dedup_key = f"connector_delivered:{msg_id}"
if await redis.get(dedup_key):
    continue
await redis.setex(dedup_key, 86_400, "1")
```

---

## 10. Gestión de sesiones con Redis

### Claves y TTLs

| Clave Redis | TTL | Contenido | Propósito |
|---|---|---|---|
| `bitrix:oauth_tokens` | Sin TTL | JSON con access/refresh token + expires_at | Tokens OAuth persistentes |
| `connector_ext_chat:{phone}` | **90 días** | `{phone}_{timestamp}` | Vínculo teléfono↔sesión Bitrix. TTL largo para preservar el chat entre visitas del usuario |
| `connector_session:{phone}` | 24h | session_id de Open Lines | Referencia a la sesión activa |
| `connector_chat:{phone}` | 24h | chat_id interno de Bitrix | Usado en `im.dialog.messages.get` para el polling |
| `connector_deal:{phone}` | 24h | deal_id del CRM | Para actualizar el deal con KPIs en el nodo de escalamiento |
| `connector_last_msg:{phone}` | 24h | ID del último mensaje procesado del asesor | Cursor del polling |
| `connector_delivered:{msg_id}` | 24h | `"1"` | Deduplicación de mensajes reenviados al usuario |

### Consideraciones de TTL

- **90 días en `connector_ext_chat`:** si el TTL fuera corto (ej. 24h) y el usuario regresa a los 2 días, se generaría un nuevo `external_chat_id` → nueva sesión → deal duplicado. Con 90 días, el usuario regresa al mismo chat durante 3 meses.
- **24h en session/chat/deal:** son datos operativos de la sesión activa. Si expiran, el siguiente mensaje del usuario regenera la sesión automáticamente (siempre que `connector_ext_chat` siga vigente).

---

## 11. Reglas críticas — errores frecuentes

### R1: Token en body, no en header

```python
# CORRECTO
json={**params, "auth": token}

# INCORRECTO — imconnector ignora el header Authorization
headers={"Authorization": f"Bearer {token}"}
```

### R2: Claves de mensaje en lowercase

```python
# CORRECTO
{"user": {...}, "message": {...}, "chat": {...}}

# INCORRECTO — imconnector ignora silenciosamente
{"USER": {...}, "MESSAGE": {...}, "CHAT": {...}}
```

### R3: Mismo user.id para mensajes del bot

```python
# CORRECTO — mismo ID que el usuario
"user": {"id": phone, ...}

# INCORRECTO — genera segunda sesión y deal duplicado
"user": {"id": f"bot_{phone}", ...}
```

### R4: No usar im.message.add en chats de Open Lines

`im.message.add` devuelve `CANCELED: No puede enviar mensajes al chat especificado` cuando el chat pertenece a Open Lines. Siempre usar `imconnector.send.messages`.

### R5: Un solo conector por canal

No registrar varios conectores para el mismo canal. Si se necesita un conector nuevo, requiere un placement handler de Marketplace. Reutilizar siempre el conector existente con el mismo `CONNECTOR_ID`.

### R6: external_chat_id estable

Nunca generar un `external_chat_id` aleatorio en cada mensaje. Debe ser estable por sesión de usuario. El patrón `{phone}_{timestamp}` genera uno nuevo solo en la primera vez (sesión nueva); luego se reutiliza el guardado en Redis.

### R7: Rebuild obligatorio tras cambios de código

`docker compose restart api` NO recarga el código (la imagen está horneada en build time). Siempre usar:

```bash
docker compose build api && docker compose up -d api
```

---

## 12. Diagrama completo del canal

```
USUARIO (WhatsApp)
        │  mensaje
        ▼
POST /webhooks/telcel
        │
        ├─ Valida firma HMAC-SHA256
        ├─ Deduplica por message_id (Redis 60s)
        ├─ mark_as_read(msg_id) → doble check azul + typing indicator
        │
        ├─ send_user_message(phone, text)
        │       ├─ _get_or_create_external_chat_id(phone)
        │       │       └─ Redis: connector_ext_chat:{phone} (90 días)
        │       │
        │       └─ POST imconnector.send.messages
        │               CONNECTOR: "whatsapp_vera"
        │               LINE: "542"
        │               user.id: phone
        │               chat.id: external_chat_id
        │               │
        │               └─ Bitrix abre sesión / crea deal en pipeline
        │                   → session_id, chat_id, deal_id → Redis (24h)
        │                   (si deal_id no viene → _fetch_openlines_deal_async +3s)
        │
        └─ debounce.enqueue(phone, text)   ← retorna 200 a Meta de inmediato
                │  espera DEBOUNCE_WINDOW_MS ms sin nuevos mensajes
                ▼
        _process_message(phone, combined_text)
                │
                └─ agente LangGraph (Claude)
                        │
                        ▼  respuesta del agente
                ┌────────────────────┐
                │ wa.send_message()  │  → usuario en WhatsApp
                └────────────────────┘
                ┌──────────────────────────────┐
                │ send_bot_message(phone, text) │  → mismo chat en Bitrix
                │   user.id = phone (mismo)     │     "🤖 Vera | {texto}"
                └──────────────────────────────┘


ASESOR (Bitrix Open Lines)
        │  escribe un mensaje en el chat
        ▼
connector_poll (asyncio.Task — cada 30s)
        │
        ├─ im.dialog.messages.get (por chat_id)
        ├─ Filtra mensajes sin CONNECTOR_MID (son del asesor)
        ├─ Deduplica: connector_delivered:{msg_id} (24h)
        │
        └─ _forward_to_user(phone, text)
                └─ wa.send_message(phone, text)  → usuario en WhatsApp
```

---

## 13. Comandos de diagnóstico

### Verificar estado del conector

```bash
docker compose exec api python scripts/setup_imconnector.py --status
```

### Listar Open Channels disponibles

```bash
docker compose exec api python scripts/setup_imconnector.py --list-lines
```

### Re-autorizar OAuth (si los tokens expiraron)

Abrir en el navegador:

```
https://b24-ahyle8.bitrix24.mx/oauth/authorize/
    ?client_id={BITRIX_CLIENT_ID}
    &response_type=code
    &redirect_uri=https://tu-dominio.com/bitrix/app
```

### Verificar tokens guardados en Redis

```bash
docker compose exec redis redis-cli get bitrix:oauth_tokens
```

### Ver sesiones activas de Open Lines

```bash
docker compose exec redis redis-cli keys "connector_chat:*"
```

### Verificar que el polling esté corriendo

```bash
docker compose logs api --tail=50 | grep connector_poll
```

### Re-ejecutar el setup del conector

```bash
docker compose exec api python scripts/setup_imconnector.py
```

---

## Notas para nuevas integraciones

Al replicar este patrón en otro proyecto o canal (SMS, Instagram, etc.):

1. **Crear una App Local diferente** en Bitrix24 con el scope apropiado. No reutilizar el `CLIENT_ID` de otro proyecto.
2. **Definir un `CONNECTOR_ID` único** por canal/proyecto. Ej: `sms_bot_proyecto_x`.
3. **Crear o seleccionar un Open Channel** diferente si la atención debe ser en colas separadas.
4. **El `external_chat_id` debe ser estable** por sesión de usuario. El patrón `{identificador_usuario}_{timestamp}` funciona bien.
5. **Nunca cambiar el `CONNECTOR_ID`** una vez registrado en producción — Bitrix no tiene forma limpia de migrar el histórico de sesiones a un conector nuevo.
6. **El polling es suficiente** para proyectos de volumen bajo/medio. Para alto volumen (>500 chats simultáneos), evaluar el webhook `ONIMCONNECTORMESSAGEADD`.
7. **Los tokens OAuth se renuevan solos** siempre que el servidor esté activo. Si el servidor estuvo apagado más de ~30 días, re-autorizar manualmente.

# Manual de Configuración — Integración Telegram + Bitrix24

Guía paso a paso para conectar el agente de Telegram con Bitrix24 usando un conector personalizado (imconnector). Al finalizar, cada mensaje de Telegram crea un deal vinculado al canal "Telegram AI Agent" y el asesor puede ver la conversación en vivo desde Bitrix y responder directamente desde el chat.

---

## Arquitectura final

```
Usuario Telegram
      │
      ▼
/webhooks/telegram  (nuestro servidor mantiene el webhook)
      │
      ├─► run_agent()  ──────────────────► respuesta al usuario por Telegram
      │
      └─► imconnector.send.messages  ───► Bitrix crea sesión + deal
                (OAuth)                   Canal: "Telegram AI Agent"
                                          Mensaje del usuario visible en Open Lines

Asesor escribe en Bitrix
      │
      ▼
OnImConnectorMessageAdd → /webhooks/connector ──► reenvía a Telegram (webhook push)
      │
      └─► poll_connector_asesor cada 30 s ────► fallback si Cloudflare bloquea el push
                                                (con deduplicación — no duplica si el webhook funcionó)
```

> **Nota sobre el mirror del agente:** `im.message.add` devuelve `CANCELED` para chats de conector (restricción de Bitrix — el bot OAuth no tiene membresía). `imconnector.send.messages` con usuario secundario crea deals duplicados. `imopenlines.session.message.add` retorna 404 en esta instalación. El mirror de respuestas del agente en Bitrix está **pendiente** de solución mediante IM Bot (`imbot`) u otro mecanismo.

---

## Prerrequisitos

- Servidor con dominio público con TLS (ej. `telegram.callcomcc.io`)
- Stack levantado: `docker compose up -d`
- Variables base de Bitrix ya configuradas en `.env`:
  ```env
  BITRIX_WEBHOOK_URL=https://tu-dominio.bitrix24.mx/rest/USER_ID/TOKEN
  BITRIX_DEAL_CATEGORY_ID=92
  BITRIX_STAGE_MAP=C92:2,C92:3,C92:4,C92:5,C92:6,C92:8,C92:10,C92:18
  ```

---

## Paso 1 — Crear la App Local en Bitrix24

Una "app local" es una aplicación OAuth propia que vive en tu instancia de Bitrix24 y permite hacer llamadas autenticadas a la REST API.

### 1.1 Abrir el menú de desarrollador

En tu instancia de Bitrix24 (`https://tu-dominio.bitrix24.mx`):

1. Ir a **Recursos de desarrollador** → **Otras aplicaciones**
2. Clic en **Agregar** → **Aplicación local**

> Si no ves "Recursos de desarrollador": actívalo en **Aplicaciones** → **Mercado** → **Recursos de desarrollador**.

### 1.2 Completar los datos de la app

| Campo | Valor |
|---|---|
| **Nombre** | `Telegram AI Agent` |
| **App URL** | `https://telegram.callcomcc.io/bitrix/app` |
| **Install URL** | `https://telegram.callcomcc.io/bitrix/install` |
| **Redirect URI** | `https://telegram.callcomcc.io/bitrix/app` |

### 1.3 Asignar permisos (scopes)

Marcar los siguientes permisos:

- `imconnector` — gestión del conector personalizado
- `imopenlines` — Open Lines (sesiones de chat)
- `imbot` — bots de mensajería interna (necesario para mirror futuro del agente)
- `crm` — contactos y deals
- `im` — mensajería interna

### 1.4 Guardar y copiar credenciales

Bitrix24 generará:
- **Client ID** (`local.XXXXXXXXXX.YYYYYY`)
- **Client Secret** (cadena larga)

Guardarlos — se necesitan en el siguiente paso.

---

## Paso 2 — Configurar variables de entorno

Agregar al archivo `.env`:

```env
# Bitrix24 — OAuth + Conector personalizado
BITRIX_CLIENT_ID=local.6a20d83fa52ab0.29191233
BITRIX_CLIENT_SECRET=TuClientSecretAqui
BITRIX_CONNECTOR_ID=telegram_ai_agent
BITRIX_CONNECTOR_LINE_ID=              # se completa en el Paso 4
```

`BITRIX_CONNECTOR_ID` es el identificador interno del conector — puede quedarse como `telegram_ai_agent` o personalizarlo. **No usar espacios ni caracteres especiales.**

Después de editar `.env`, reconstruir y reiniciar el contenedor:

```bash
docker compose build api
docker compose up -d api
```

> **Importante:** `docker compose restart api` NO aplica cambios de código. Siempre usar `build` + `up -d` al modificar código o variables que afecten la imagen.

---

## Paso 3 — Autorizar la App (OAuth flow)

Este paso intercambia el Client ID + Secret por un `access_token` + `refresh_token` que se guardan en Redis y se renuevan automáticamente cada hora.

### 3.1 Iniciar el flujo de autorización

Abrir en el navegador (ya autenticado en Bitrix24):

```
https://tu-dominio.bitrix24.mx/oauth/authorize/?client_id=local.TU_CLIENT_ID&response_type=code&redirect_uri=https://telegram.callcomcc.io/bitrix/app
```

Reemplazar `local.TU_CLIENT_ID` con el Client ID real.

### 3.2 Autorizar la app

Bitrix24 mostrará una pantalla pidiendo confirmar los permisos. Hacer clic en **Permitir**.

### 3.3 Verificar que los tokens se guardaron

Bitrix24 redirige a `/bitrix/app?code=XXXX`. El servidor intercambia el código automáticamente. Verificar en Redis:

```bash
docker exec bot_megacable_redis redis-cli GET "bitrix:oauth_tokens"
```

Debe devolver un JSON con `access_token`, `refresh_token` y `expires_at`. Si está vacío, revisar los logs:

```bash
docker compose logs api --tail=30 | grep -E "bitrix_oauth|bitrix_app"
```

---

## Paso 4 — Identificar el Open Channel (línea)

El conector necesita asociarse a un Open Channel existente en Bitrix24. Listar los disponibles:

```bash
docker compose exec api python scripts/setup_imconnector.py --list-lines
```

Salida esperada:

```
=== Open Channels disponibles ===
  ID: 546 | Nombre: Telegram AI Agent | Activo: Y
  ID: 212 | Nombre: WhatsApp | Activo: Y
Total: 2 líneas
```

Copiar el ID del canal deseado y agregarlo al `.env`:

```env
BITRIX_CONNECTOR_LINE_ID=546
```

Reconstruir el contenedor:

```bash
docker compose build api && docker compose up -d api
```

> Si no existe ningún Open Channel, crearlo en Bitrix24: **Contact Center** → **Canales** → **Agregar canal** → **Open Channel**.

---

## Paso 5 — Registrar el conector en Bitrix24

Este script se ejecuta **una sola vez** (o cuando se necesite restablecer la conexión) y realiza 4 operaciones en Bitrix24:

1. Registra el conector `telegram_ai_agent`
2. Lo activa en el Open Channel configurado
3. Configura los datos del conector
4. Suscribe el evento `ONIMCONNECTORMESSAGEADD` al endpoint del servidor

```bash
docker compose exec api python scripts/setup_imconnector.py
```

Salida esperada:

```
[1/4] Registrando conector 'telegram_ai_agent'...
   Resultado: True
[2/4] Activando en línea 546...
   Resultado: True
[3/4] Configurando datos del conector...
   Resultado: True
[4/4] Suscribiendo ONIMCONNECTORMESSAGEADD → https://telegram.callcomcc.io/webhooks/connector...
   Resultado: True

✅ Setup completo. El conector 'Telegram AI Agent' está activo en Bitrix24.
```

> **Nota:** El paso 4 puede fallar con `Handler already binded` si el evento ya estaba registrado. Esto es normal — los pasos 1-3 son suficientes para restablecer la conexión.

> **Nota Cloudflare:** Las peticiones push de Bitrix24 (`OnImConnectorMessageAdd`) son bloqueadas por Cloudflare cuando el dominio tiene proxy activo (nube naranja). Ver Paso 7 para la solución definitiva y el Paso 8 para el fallback de polling.

Verificar el estado del conector:

```bash
docker compose exec api python3 -c "
import asyncio, sys; sys.path.insert(0, '/app')
from integrations.bitrix.connector import _call
async def check():
    r = await _call('imconnector.status', {'CONNECTOR': 'telegram_ai_agent', 'LINE': '546'})
    print(r)
asyncio.run(check())
"
```

Debe mostrar `CONFIGURED: True, STATUS: True, ERROR: False`.

---

## Paso 6 — Verificar el flujo Telegram → Bitrix

Enviar un mensaje de prueba desde la cuenta de Telegram configurada. En los logs del API deben aparecer en orden:

```
connector_user_msg_sent  → session_id: XXXXXX, chat_id: YYYYYY
bitrix_contact_created   → contact_id: XXXXXXX   (o bitrix_contact_found si ya existe)
bitrix_deal_created      → deal_id: XXXXXXX, stage_id: C92:2
telegram_sent            → message_id: XXXX (parte 1)
```

En Bitrix24:
- **CRM → Deals**: debe aparecer un nuevo deal con título `Bot Megacable · Telegram {phone}` y canal "Telegram AI Agent"
- **Contact Center → Open Lines → Línea 546 → Cola**: debe aparecer el chat con el mensaje del cliente

```bash
# Ver logs en tiempo real
docker compose logs api -f | grep -E "connector|bitrix|telegram_sent"
```

> **Dónde buscar el chat en Bitrix:** Los mensajes del conector aparecen en **Contact Center → Línea 546 → Cola** (si no hay operador asignado) o en **Mis Chats** si ya fueron aceptados. No buscar en el chat regular de IM.

---

## Paso 7 — Configurar bypass en Cloudflare (webhook push)

Para que Bitrix24 pueda enviar eventos push directamente al servidor (en lugar de depender del polling), es necesario crear una regla en Cloudflare que permita el tráfico de los IPs de Bitrix24.

**En el dashboard de Cloudflare:**

1. Seleccionar el dominio → **Security** → **WAF** → **Custom Rules**
2. Crear nueva regla:
   - **Nombre:** `Allow Bitrix webhook`
   - **Expresión:** `http.request.uri.path eq "/webhooks/connector"`
   - **Acción:** `Skip` (bypass all security checks)
3. Guardar y desplegar

Con esta regla activa, los eventos `OnImConnectorMessageAdd` de Bitrix llegarán directamente al servidor sin pasar por el polling de 30 segundos.

Verificar que el webhook push funciona:

```bash
docker compose logs api -f | grep "connector_incoming\|connector_asesor_message\|connector_forwarded"
```

Si el asesor escribe en Bitrix y aparecen esas entradas, el push está funcionando.

---

## Paso 8 — Polling del asesor (fallback del push)

Cuando Cloudflare bloquea los eventos push de Bitrix24, el servidor detecta mensajes del asesor mediante **polling cada 30 segundos** usando `im.dialog.messages.get`.

El polling incluye **deduplicación**: si el mensaje ya fue entregado por el webhook push (registrado en Redis), el polling lo omite y no lo reenvía. Esto evita duplicados cuando ambos mecanismos funcionan simultáneamente.

El job `poll_connector_asesor` se activa automáticamente al iniciar el API. Verificar que está corriendo:

```bash
docker compose logs api --tail=20 | grep -E "poll_connector|scheduler_started"
```

Cuando el asesor escribe en Bitrix y el push no llegó, el log mostrará (hasta 30 s después):

```
connector_poll_forwarded → phone: 8211184685
```

---

## Gestión de sesiones

### Reiniciar la conversación (crear nuevo deal)

Cada conversación tiene un `external_chat_id` único (`{phone}_{timestamp}`) almacenado en Redis. Mientras exista esa clave, los nuevos mensajes se acumulan en el mismo deal. Para forzar un deal nuevo, eliminar todas las claves del usuario:

```bash
# Ver claves activas del usuario
docker exec bot_megacable_redis redis-cli KEYS "*{phone}*"

# Eliminar todas (reemplazar {phone} con el número real)
docker exec bot_megacable_redis redis-cli DEL \
  "connector_last_msg:{phone}" \
  "connector_session:{phone}" \
  "connector_chat:{phone}" \
  "connector_ext_chat:{phone}" \
  "connector_delivered:{phone}" \
  "session:{phone}"
```

El próximo mensaje de Telegram creará un contacto, deal y sesión nuevos.

### Eliminar deals y contacto de un número (vía Python)

```bash
docker compose exec api python3 -c "
import asyncio, httpx
from config.settings import settings

BASE = settings.bitrix_webhook_url.rstrip('/')

async def main():
    async with httpx.AsyncClient() as c:
        # Obtener contacto del deal
        r = await c.post(f'{BASE}/crm.deal.get', json={'ID': DEAL_ID})
        contact_id = r.json().get('result', {}).get('CONTACT_ID')
        print(f'contact_id: {contact_id}')

        # Eliminar deal
        r = await c.post(f'{BASE}/crm.deal.delete', json={'ID': DEAL_ID})
        print(f'deal eliminado: {r.json()}')

        # Eliminar contacto
        if contact_id:
            r = await c.post(f'{BASE}/crm.contact.delete', json={'ID': contact_id})
            print(f'contacto eliminado: {r.json()}')

asyncio.run(main())
"
```

### Restablecer la conexión del canal

```bash
# 1. Limpiar sesiones Redis
docker exec bot_megacable_redis redis-cli KEYS "*" | grep -vE "bitrix:oauth|tool_calls" | xargs docker exec -i bot_megacable_redis redis-cli DEL

# 2. Reregistrar el conector
docker compose exec api python scripts/setup_imconnector.py
```

---

## Variables de entorno — referencia completa

| Variable | Descripción | Ejemplo |
|---|---|---|
| `BITRIX_WEBHOOK_URL` | URL webhook REST (CRM + lectura de chats) | `https://b24-xxx.bitrix24.mx/rest/1480402/token` |
| `BITRIX_CLIENT_ID` | Client ID de la app local OAuth | `local.6a20d83fa52ab0.29191233` |
| `BITRIX_CLIENT_SECRET` | Client Secret de la app local OAuth | `FtG6OVN...` |
| `BITRIX_CONNECTOR_ID` | Identificador del conector (sin espacios) | `telegram_ai_agent` |
| `BITRIX_CONNECTOR_LINE_ID` | ID del Open Channel en Bitrix24 | `546` |
| `BITRIX_DEAL_CATEGORY_ID` | ID del embudo de CRM donde se crean los deals | `92` |
| `BITRIX_STAGE_MAP` | Mapa de niveles 1-9 a etapas del embudo | `C92:2,C92:3,...` |

---

## Diagnóstico rápido

| Síntoma | Causa probable | Solución |
|---|---|---|
| No aparece deal nuevo en Bitrix | Sesión activa en Redis reutiliza el chat | Limpiar claves Redis del número |
| Se crean dos deals (uno "Agente") | `_mirror_agent_response` usa `imconnector.send.messages` con usuario secundario | Verificar que `_mirror_agent_response` está desactivado en `run.py` |
| Mensajes de Telegram no aparecen en Open Lines | Buscando en chat regular en lugar de Open Lines | Ir a Contact Center → Línea 546 → Cola |
| Asesor escribe pero no llega a Telegram (inmediato) | Push bloqueado por Cloudflare | Configurar regla bypass en Cloudflare (Paso 7) |
| Asesor escribe pero no llega a Telegram (30 s) | Polling no corre | Verificar job `poll_connector_asesor` en logs |
| OAuth tokens vacíos al arrancar | El flujo de autorización no se completó | Repetir Paso 3 |
| `imconnector.status` muestra `ERROR: True` | Conector deregistrado o línea incorrecta | Repetir Paso 5 |
| `event.bind` falla con `Handler already binded` | El handler ya estaba registrado | Normal — pasos 1-3 del setup son suficientes |
| Mensajes históricos reenviados a Telegram al reiniciar | `connector_last_msg` fue eliminado de Redis | Normal — el puntero se siembra en el primer poll sin reenviar |

---

## Limitaciones conocidas de la API de Bitrix24

| Método | Estado | Motivo |
|---|---|---|
| `im.message.add` en chats de conector | ❌ CANCELED | El bot OAuth no es miembro del chat de conector |
| `imopenlines.session.message.add` | ❌ 404 | Método no disponible para sesiones de imconnector |
| `imopenlines.session.finish/close` | ❌ 404 | No expuesto en la versión actual |
| `imconnector.send.messages` con usuario secundario | ⚠️ Funciona pero crea deal extra | Bitrix crea contacto+deal para cada usuario nuevo |
| `imbot.message.add` | 🔜 Pendiente probar | App tiene scope `imbot` — solución potencial para mirror del agente |

---

## Reconstruir desde cero

Si es necesario rehacer toda la integración:

```bash
# 1. Limpiar tokens OAuth en Redis
docker exec bot_megacable_redis redis-cli DEL "bitrix:oauth_tokens"

# 2. Editar .env con las nuevas credenciales
# 3. Reconstruir
docker compose build api && docker compose up -d api

# 4. Re-autorizar la app (Paso 3)
# 5. Re-ejecutar el setup del conector (Paso 5)
docker compose exec api python scripts/setup_imconnector.py
```

# Bitácora de Cambios — Bot Telcel Portabilidad

---

## 2026-06-19

### Seguimientos: registro de lead desde el primer mensaje

**Archivos modificados:** `agents/portabilidad/nodes/validacion.py`

**Problema:** el lead solo se creaba en la tabla `leads` cuando el usuario proporcionaba su número de 10 dígitos y la LADA era válida. Cualquier usuario que contactara al bot sin dar su número (solo "hola", preguntas de precio, etc.) nunca quedaba registrado y quedaba fuera del flujo de seguimientos automáticos.

**Solución:**
- Nueva función `_upsert_lead_primer_contacto(sender_phone, deal_id)`: inserta el lead con `telefono = sender_phone` (teléfono del remitente WhatsApp/Telegram) al primer mensaje, usando `ON CONFLICT DO UPDATE` para idempotencia.
- `_upsert_lead(numero, sender_phone)`: modificada para ya no insertar un registro nuevo con el número portado, sino actualizar `numero_a_portar` en la fila existente del remitente.
- `validacion_node`: llama `_upsert_lead_primer_contacto` en cada mensaje, justo después de `_crear_deal_primer_contacto`, usando `state.get("session_id")` como teléfono del remitente.

**Resultado:** cualquier usuario que contacte al bot queda registrado para seguimientos desde el primer mensaje, sin importar en qué etapa quede la conversación.

---

### Seguimientos: Rescate 3 requiere 2 horas en C90:2

**Archivos modificados:** `jobs/seguimientos.py`

- `MIN_RESCATE3` aumentado de 60 a **120 minutos** — el job ahora espera 2 horas desde que el lead entró a C90:2 antes de disparar la llamada a Vicidial.

---

### Prueba de flujo completo Rescate 1 → 2 → 3

- Validado el flujo completo end-to-end: Rescate 1 (mensaje WhatsApp + deal a C90:1), Rescate 2 (mensaje WhatsApp + deal a C90:2), Rescate 3 (llamada Vicidial real confirmada con `SUCCESS: add_lead`).
- Vicidial acepta el número como los últimos 10 dígitos del teléfono (`phone[-10:]`).
- Endpoint `/admin/vicidial-test` con `simulate=false` operativo.

---

### Skill `/reset-test` — limpieza de teléfonos de prueba

**Archivos modificados:** `.claude/commands/reset-test.md`, `scripts/reset_test_phone.py`

- Nueva skill `/reset-test <telefono>` que limpia Redis, checkpoints PostgreSQL, leads, deals y contacto en Bitrix en un solo comando.
- El script corre dentro del contenedor `api` con `docker compose exec -w /app api python scripts/reset_test_phone.py <telefono>`.
- Soporta variantes del teléfono (con/sin prefijo 52, con/sin 1) para borrar checkpoints de cualquier formato.
- Los tokens OAuth de Bitrix (`bitrix:oauth_tokens`) no se tocan.

---

## 2026-06-16

### Seguridad: externalizar credenciales hardcodeadas a variables de entorno

**Archivos modificados:** `Caddyfile`, `config/settings.py`, `.env`, `.env.example`

#### Caddyfile
- Bearer token del RAG API (`rag-portabilidad.callcomcc.io`) reemplazado por `{env.RAG_BEARER_TOKEN}`
- Hash bcrypt del dashboard Qdrant (`qdrant-portabilidad.callcomcc.io`) reemplazado por `{env.QDRANT_ADMIN_PASSWORD_HASH}`

#### config/settings.py
- `vicidial_url`, `vicidial_user`, `vicidial_pass`, `vicidial_list_id`, `vicidial_campaign_id`: defaults cambiados a string vacío — los valores reales se leen exclusivamente del `.env`

#### .env (solo en servidor, no en repo)
- `VICIDIAL_PASS` agregada con valor correcto
- `VICIDIAL_URL`, `VICIDIAL_USER`, `VICIDIAL_LIST_ID`, `VICIDIAL_CAMPAIGN_ID` agregadas
- `DB_PASSWORD` rotada a contraseña generada aleatoriamente (32 bytes, `secrets.token_urlsafe`)
- `ADMIN_TOKEN` rotado a token generado aleatoriamente (32 bytes, `secrets.token_urlsafe`)
- `RAG_BEARER_TOKEN` agregada (antes hardcodeada en Caddyfile)
- `QDRANT_ADMIN_PASSWORD` y `QDRANT_ADMIN_PASSWORD_HASH` agregadas (antes hardcodeadas en Caddyfile)

#### .env.example
- Agregadas secciones: Vicidial, Caddy RAG bearer token, Caddy Qdrant dashboard
- `VICIDIAL_PASS` y `QDRANT_ADMIN_PASSWORD` en blanco (no exponer valores reales)

#### Acciones ejecutadas en servidor
- `ALTER USER bot PASSWORD '...'` ejecutado en PostgreSQL — password sincronizado
- API reconstruida y levantada: `docker compose build api && docker compose up -d api`
- Caddy recargado con nuevas variables de entorno

---

### Infraestructura: Caddy SMART-CC — credenciales y red Docker

**Archivos modificados:** `/root/SMART-CC/Caddyfile`, `/root/SMART-CC/docker-compose.yml`, `/root/SMART-CC/.env`

#### SMART-CC/Caddyfile
- `qdrant.callcomcc.io` basic_auth: hash hardcodeado → `{env.QDRANT_ADMIN_PASSWORD_HASH}`
- `qdrant-portabilidad.callcomcc.io` basic_auth: hash hardcodeado → `{env.QDRANT_PORTABILIDAD_ADMIN_PASSWORD_HASH}`

#### SMART-CC/docker-compose.yml
- Servicio `caddy`: agregado `env_file: .env` para inyectar variables de entorno
- Servicio `caddy`: agregada red `portabilidad_net` (externa: `telcel-portabilidad_portabilidad_net`) — resuelve error 502 al no poder resolver `telcel-portabilidad-api-1` desde la red `megacable_net`

#### SMART-CC/.env
- Agregados `QDRANT_ADMIN_PASSWORD_HASH` y `QDRANT_PORTABILIDAD_ADMIN_PASSWORD_HASH` con hashes bcrypt

---

### Infraestructura: SSL portabilidad.callcomcc.io

- Dominio `portabilidad.callcomcc.io` configurado en Cloudflare DNS apuntando al servidor (`147.79.78.75`)
- Certificado SSL de Let's Encrypt obtenido exitosamente vía HTTP-01 challenge
- Cloudflare puesto temporalmente en modo DNS-only (nube gris) para permitir el challenge; reactivar proxy (nube naranja) una vez obtenido el cert
- Rate limit de Let's Encrypt: 5 autorizaciones fallidas por reintentos con Cloudflare en modo proxy — se resolvió al pasar a modo DNS-only
- Caddy en contenedor `smart-cc-caddy-1` sirve los dominios: `portabilidad.callcomcc.io`, `telegram-portabilidad.callcomcc.io`, `rag-portabilidad.callcomcc.io`, `qdrant-portabilidad.callcomcc.io`
- Stack Telcel Portabilidad operativo y respondiendo en `https://portabilidad.callcomcc.io/health`

# Bitácora de Cambios — Bot Telcel Portabilidad

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

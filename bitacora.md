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

#### Acciones pendientes en servidor
- Ejecutar `ALTER USER bot PASSWORD '...'` en PostgreSQL para sincronizar la nueva `DB_PASSWORD`
- Exportar `RAG_BEARER_TOKEN` y `QDRANT_ADMIN_PASSWORD_HASH` al entorno del proceso Caddy y ejecutar `caddy reload`
- Hacer rebuild de la API: `docker compose build api && docker compose up -d api`

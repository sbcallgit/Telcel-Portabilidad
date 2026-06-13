# Auditoría Técnica — Bot Telcel Portabilidad R4

**Modo:** Read-only · **Rama:** `auditoria-tecnica` · **Fecha:** 2026-06-13
**Auditor:** Fabe 5 (arquitecto principal) + 10 frentes especializados + revisión adversarial Codex Senior
**Alcance:** Diagnóstico estático del repositorio. No se modificó código, no se ejecutaron servicios, no se publicaron secretos.

> Documento espejo del plan de acción en [`../plan-remediacion/plan-remediacion-2026-06-13.md`](../plan-remediacion/plan-remediacion-2026-06-13.md).

---

## A. Resumen ejecutivo

**Estado general.** Producto funcional y bastante completo para una v1: agente conversacional LangGraph con checkpointer en Postgres, espejeo bidireccional a Bitrix Open Lines, sistema de rescates en 3 niveles y export de KPIs. La arquitectura de aplicación es razonable. **El problema no es la lógica de negocio: es la postura de seguridad y la disciplina de despliegue.** Hay secretos vivos en el repositorio, endpoints sin autenticar que permiten enviar mensajes desde el número de negocio a cualquier usuario, y el `.env` real se hornea dentro de la imagen Docker.

**Riesgo global: ALTO.** No es "Crítico" porque no se encontró RCE ni SQL injection (las queries sí están parametrizadas), pero la combinación de secretos commiteados + endpoints abusables + imagen con credenciales bloquea un despliegue seguro tal cual está.

**Top 5 riesgos:**

1. **Secretos reales en el repo** — Bearer token en claro en `Caddyfile:9`, password Vicidial y hash bcrypt de Qdrant, más defaults peligrosos (`admin_token="changeme"`, `db_password="botpassword"`).
2. **Sin `.dockerignore` + `COPY . .`** → el `.env` (todas las llaves) y `reporteskpi/` (CSVs con PII de clientes) quedan dentro de la imagen.
3. **`/webhooks/connector` sin autenticación** → cualquiera puede enviar mensajes arbitrarios a clientes vía el WhatsApp/Telegram del negocio (phishing/suplantación).
4. **Endpoints Telegram `/setup` e `/info` sin auth** → un atacante puede secuestrar el webhook del bot (redirigir mensajes a su servidor).
5. **Verificación de firma de WhatsApp opcional** — se omite por completo si `WHATSAPP_APP_SECRET` está vacío; combinado con `ADMIN_TOKEN` default abre la puerta a inyección de mensajes y disparo de llamadas Vicidial.

**¿Listo para producción?** No sin una Fase 0 de contención (rotar secretos, cerrar endpoints, `.dockerignore`). La parte funcional sí está madura; la operativa/seguridad no.

**Recomendación:** **Congelar el deploy actual, ejecutar contención de seguridad, y NO tocar la lógica de negocio todavía.** El código de aplicación está sano; lo que falla es perímetro y manejo de secretos. Auditar adicionalmente los 6 archivos que no entraron en profundidad (ver §G).

---

## B. Mapa técnico del proyecto

**Propósito.** Bot de WhatsApp (canal de pruebas Telegram) que califica leads de portabilidad Telcel R4 provenientes de Meta Ads, los conduce por un embudo de venta conversacional y los entrega a un asesor humano vía Bitrix24 Open Lines, con rescates automáticos (mensajes LLM + llamada Vicidial).

**Arquitectura.** Monolito FastAPI asíncrono. Un único proceso corre: API (webhooks + admin) + agente LangGraph + APScheduler (3 jobs) + tarea de polling. Sin worker separado real pese a declarar `arq`.

| Capa | Componentes |
|---|---|
| Entrada | `api/routes/*` — webhooks WhatsApp/Telegram/connector, OAuth Bitrix, admin, health |
| Agente | `agents/portabilidad/` — grafo LangGraph de 7 nodos (validacion→sondeo→oferta→objeciones→cierre→escalate→fin) |
| Integraciones | Bitrix (REST webhook + OAuth imconnector), WhatsApp Graph API, Telegram, Vicidial, Qdrant, Postgres, Redis |
| Jobs | `seguimientos` (5 min), `bitrix_sync` (30 min), `kpi_export` (3am), `connector_poll` (30 s) |
| Datos | PostgreSQL 16 (leads, knowledge base, checkpoints LangGraph, kpi_conversaciones), Redis 7 (debounce, sesiones connector, OAuth tokens), Qdrant (RAG objeciones) |

**Stack.** Python 3.12, FastAPI, LangGraph, `langchain-openai` apuntando a **OpenRouter** (no SDK Anthropic — ver F-19), asyncpg, redis.asyncio, httpx+tenacity, APScheduler, Docker Compose + Caddy.

**Puntos de entrada.** `api/main.py` (FastAPI lifespan) inicializa pool PG, Redis, checkpointer, grafo, scheduler y polling. `thread_id` del agente = teléfono (WhatsApp) o `str(chat_id)` (Telegram).

**Servicios externos.** Meta Graph API, Bitrix24 (`b24-ahyle8.bitrix24.mx`, hardcodeado), Vicidial (`189.209.207.222`, hardcodeado), OpenRouter, Qdrant.

**Auth/Autz.** WhatsApp: HMAC-SHA256 (condicional). Telegram: secret header (igualdad simple). Admin: `X-Admin-Token` (igualdad simple). Bitrix: OAuth en Redis. Connector webhook: **ninguna**. No hay roles/RBAC; el modelo es "un solo operador confiable".

**Build/deploy.** `Dockerfile` single-stage como root; `docker-compose.yml` (Postgres y Qdrant expuestos a host); Caddy como reverse proxy con TLS y un bearer estático.

**Datos sensibles.** Teléfonos, nombres, compañía donante, municipio. Enmascarados en logs (`mask_phone`, aunque los routes usan `phone[-4:]` manual). NIP nunca se procesa (✓). Aviso de privacidad incluido en cierre (✓).

---

## C. Tabla priorizada de hallazgos

| ID | Sev | Frente | Archivo | Evidencia | Impacto | Recomendación |
|---|---|---|---|---|---|---|
| F-01 | **P0** | Seguridad/DevOps | `Caddyfile:9`, `settings.py:63` | Bearer `a3f8…a8f1` en claro; `vicidial_pass="key2-Fit"`; bcrypt Qdrant | Secretos vivos versionados | Rotar TODO, mover a env/secret manager, purgar de git |
| F-02 | **P0** | DevOps | sin `.dockerignore` + `Dockerfile:17` | `COPY . .` sin exclusiones | `.env` + CSVs PII + `.git` dentro de la imagen | Crear `.dockerignore`, rebuild, rotar llaves |
| F-03 | **P1** | Seguridad | `webhooks.py:94` | `if settings.whatsapp_app_secret:` | Si vacío, se omite firma → mensajes forjados | Hacer la firma obligatoria; fallar cerrado |
| F-04 | **P1** | Seguridad | `telegram.py:95-113`, `bitrix.py:38` | `/setup`, `/info`, `/install` sin token | Secuestro de webhook Telegram / fuga | Exigir `X-Admin-Token` o quitar de prod |
| F-05 | **P1** | Seguridad | `connector.py:44` | Endpoint sin firma/auth Bitrix | Enviar WhatsApp arbitrario a cualquier víctima | Validar firma/IP de Bitrix; allowlist |
| F-06 | **P1** | Seguridad | `admin.py:16-18`, `settings.py:57` | `!=` no constante; default `changeme` | Admin abierto si no se cambia token | `compare_digest` + arrancar-falla si default |
| F-07 | **P1** | Seguridad | `vicidial/client.py:32` | `verify=False` + `pass` en query GET | MITM captura credenciales + teléfonos | TLS verify, mover a POST, rotar pass |
| F-08 | **P1** | DevOps | `docker-compose.yml:28-29` | `5434:5432` expuesto, creds débiles | DB accesible desde host con `bot/botpassword` | No exponer puerto; password fuerte |
| F-09 | **P2** | Datos | `bitrix/client.py:48` | Match por `*{telefono[-4:]}` | Colisión últimos-4-dígitos → deal equivocado | Vincular por contacto/teléfono completo |
| F-10 | **P2** | Seguridad | `bitrix.py:35`, `oauth.py:64` | `<pre>{exc}</pre>` y `resp.text` en error | Fuga de info/tokens en respuesta/logs | No reflejar excepciones; loggear genérico |
| F-11 | **P2** | Backend/Producto | `validacion.py:199-493` | `any(w in lower …)` substring | Falsos positivos y guardrails evadibles | Tokenizar/regex con límites; tests adversariales |
| F-12 | **P2** | Arquitectura | `seguimientos.py:6-114` | `_CADENCIAS`/`_mensaje` muertos; docstring obsoleto | Confusión y deuda | Borrar código muerto; corregir docstring |
| F-13 | **P2** | DevOps/QA | `Makefile:worker` | `jobs.worker.WorkerSettings` inexistente | `make worker` falla; `arq` fantasma | Eliminar target/dep o implementar worker |
| F-14 | **P2** | DevOps | `Dockerfile` | Root, single-stage, gcc en runtime | Superficie de ataque mayor | `USER` no-root, multi-stage |
| F-15 | **P2** | QA | `tests/scenarios/test_flujos.py:18-26` | Fixture usa LLM real + DB viva | Tests E2E no deterministas, no corren en CI | Mockear LLM/IO; unit tests deterministas |
| F-16 | **P2** | Performance | `health.py:33` | `asyncpg.connect` por request | Conexión nueva por health-check | Usar el pool existente |
| F-17 | **P3** | Seguridad | `telegram.py:64`, `webhooks.py:82` | Comparaciones `!=` no constantes | Timing attack (bajo) | `hmac.compare_digest` |
| F-18 | **P3** | Backend | `graph.py:261-263` | `get_event_loop().run_until_complete` | Falla si hay loop corriendo | Inicialización explícita en lifespan |
| F-19 | **P3** | Docs | `CLAUDE.md` vs `agents/llm.py` | "Claude/Anthropic" vs OpenRouter | Documentación engañosa; `make health` puerto 8000 vs 8001 | Alinear docs con realidad |
| F-20 | **P3** | Backend | `webhooks.py:131`, `validacion.py:184` | `asyncio.create_task` sin referencia | Tareas GC-ables / perdidas en restart | Guardar refs; cola durable |
| F-21 | **P3** | DevOps | `Caddyfile:5` | `reverse_proxy api:8001` | Posible mismatch (contenedor escucha 8000) | Verificar red de Caddy |
| F-22 | INFO | Seguridad | `oauth.py:48` | Tokens en Redis sin cifrar/TTL, Redis sin password | Exposición si Redis se compromete | Cifrar en reposo / password Redis |
| F-23 | INFO | Backend | `connector.py:70` vs `routes/connector.py:34` | chat-id `{phone}_{ts}` vs handler espera `wa_` | Push handler nunca extrae phone (poll lo cubre) | Unificar formato o eliminar handler |

---

## D. Hallazgos críticos detallados (P0/P1)

### F-01 · Secretos reales versionados en el repositorio — P0

**Problema.** Hay credenciales vivas en archivos commiteados.

**Evidencia:**
- `Caddyfile:9` — `Bearer a3f8c2e1…a8f1` (token de la API RAG, en claro).
- `Caddyfile:39` — hash bcrypt `$2a$14$4SgG…` del admin de Qdrant.
- `settings.py:63` — `vicidial_pass: str = "key2-Fit"` como default en código.
- `settings.py:34,57,46` — `db_password="botpassword"`, `admin_token="changeme"`, `telegram_webhook_secret="tg_webhook_secret_dev"`.

**Impacto.** Cualquiera con acceso al repo (o a la imagen) obtiene acceso al gateway RAG, a Vicidial, y los defaults débiles se vuelven la config real si no se sobrescriben. Quedan en el historial de git aunque se borren hoy.

**Escenario.** Repo se comparte con un contratista / se filtra → bearer válido → acceso directo al backend RAG sin pasar por la app.

**Corrección.** Rotar las tres credenciales reales **ya**. Sacar el bearer del Caddyfile a una variable. Eliminar defaults sensibles de `settings.py` (dejar `""` y fallar si faltan en prod). Purgar del historial (`git filter-repo`) o, si el repo es privado y controlado, al menos rotar y documentar.

**Pruebas.** Test que verifique que `settings` lanza error en `ENVIRONMENT=production` si `admin_token`/`db_password` son los defaults. Scan con `gitleaks`/`trufflehog` en CI.

### F-02 · `.env` y PII horneados en la imagen Docker — P0

**Problema.** No existe `.dockerignore` y el `Dockerfile:17` hace `COPY . .`. Si hay un `.env` en el contexto de build (lo normal) o CSVs en `reporteskpi/`, terminan dentro de la imagen.

**Evidencia.** `ls .dockerignore` → no existe. `reporteskpi/` está en `.gitignore` pero **no** excluido del build; contiene exports KPI con teléfonos/nombres.

**Impacto.** Quien obtenga la imagen (registry, `docker save`, host comprometido) extrae todas las llaves y PII de clientes con `docker history`/`cat`.

**Escenario.** Push a un registry con permisos laxos → exfiltración total de secretos + datos personales (incidente LFPDPPP).

**Corrección.** Crear `.dockerignore` con `.env*`, `.git`, `reporteskpi/`, `tests/`, `*.md`, caches. Rebuild. Rotar llaves (asumir comprometidas).

**Pruebas.** CI: `docker build` + `docker run img sh -c '! test -f /app/.env'`. Verificar ausencia de `reporteskpi` en la imagen.

### F-03 · Verificación de firma WhatsApp es opcional — P1

**Problema.** `webhooks.py:94`: `if settings.whatsapp_app_secret:`. Con el secret vacío (default `""`), **se omite la validación HMAC** y se procesa cualquier POST.

**Evidencia.** El `verify_webhook_signature` en sí es correcto (`hmac.compare_digest`, F-17 aparte), pero está detrás de un `if` que falla **abierto**.

**Impacto.** Un atacante POSTea payloads de WhatsApp falsos → dispara el agente (costo LLM), envía mensajes reales desde el número, crea deals basura, contamina KPIs.

**Escenario.** Deploy con `WHATSAPP_APP_SECRET` sin setear (fácil de olvidar) → webhook público sin protección.

**Corrección.** Si `ENVIRONMENT=production` y no hay secret → fallar al arrancar. Nunca procesar sin firma válida.

**Pruebas.** Test: POST sin firma → 401. POST con firma inválida → 401. Arranque en prod sin secret → error.

### F-04 · Endpoints Telegram de administración sin autenticación — P1

**Problema.** `POST /webhooks/telegram/setup` (cambia la URL del webhook en Telegram) y `GET /webhooks/telegram/info` (datos del bot) no exigen token. `POST /bitrix/install` tampoco.

**Evidencia.** `telegram.py:95-113` — solo validan que `telegram_bot_token` exista.

**Impacto.** Un atacante llama `/webhooks/telegram/setup?url=https://evil/…` → **secuestra el webhook**: todos los mensajes del bot van a su servidor. `/info` filtra metadata del bot.

**Escenario.** Reconocimiento del dominio público → `setup` apuntando a infra del atacante → intercepción/MITM conversacional.

**Corrección.** Proteger ambos con `X-Admin-Token`, o moverlos a un script de operación fuera de la API pública.

**Pruebas.** Test: `/setup` sin token → 403. Con token inválido → 403.

### F-05 · Webhook del connector sin autenticación → mensajería arbitraria — P1

**Problema.** `connector.py:44` (`POST /webhooks/connector`) no valida origen. El único filtro es `connector == settings.bitrix_connector_id` (valor conocido/adivinable, p.ej. `whatsapp_vera`).

**Evidencia.** Construye `phone` desde el chat-id del payload y llama `_forward_to_user(phone, text)` → `WhatsAppClient.send_message`.

**Impacto.** Cualquiera que conozca la URL puede enviar **mensajes arbitrarios desde el WhatsApp del negocio a cualquier número**:
```json
{"data":{"CONNECTOR":"whatsapp_vera","MESSAGES":[{"id":"1","text":"…"}],"CHAT":{"id":"wa_521…_…"}}}
```
Phishing con la identidad de Telcel.

**Escenario.** Suplantación masiva / smishing usando el número verificado del negocio → daño reputacional y legal.

**Corrección.** Validar firma/token de Bitrix (event handler `application_token`), o restringir por IP/allowlist, o requerir secret compartido. *(Nota: ver F-23 — el extractor de phone probablemente ya está roto para el formato real de chat-id, lo que reduce la explotabilidad efectiva HOY, pero el endpoint sigue siendo no autenticado y debe cerrarse.)*

**Pruebas.** Test: POST sin firma válida → 401. Fuzz del payload no debe disparar `send_message`.

### F-06 · Token admin con default `changeme` y comparación no constante — P1

**Problema.** `admin.py:16-18` usa `x_admin_token != settings.admin_token`; default `"changeme"`.

**Evidencia.** Endpoints protegidos: `kpi-export`, `seguimiento-test` (envía WhatsApp + mueve deals), `vicidial-test` (puede disparar **llamadas reales** con `simulate=false`).

**Impacto.** Si no se cambia el token, cualquiera dispara llamadas Vicidial y mensajes a leads. La comparación `!=` además es vulnerable a timing (menor).

**Corrección.** `hmac.compare_digest`; abortar arranque en prod si el token es el default; rate-limit.

**Pruebas.** 403 con token incorrecto; arranque falla con default en prod.

### F-07 · Cliente Vicidial: TLS deshabilitado + credenciales en URL — P1

**Problema.** `vicidial/client.py:32`: `verify=False, follow_redirects=True` y `pass=settings.vicidial_pass` viaja como query param en un GET a una IP por HTTP que redirige a HTTPS con cert inválido.

**Impacto.** MITM trivial captura usuario/password de Vicidial y los teléfonos de los leads. El password además está hardcodeado (F-01).

**Escenario.** Red comprometida entre el host y `189.209.207.222` → robo de credenciales del marcador predictivo.

**Corrección.** Pinning/cert válido y `verify=True`; mover credenciales a POST body; rotar la pass; resolver el 403 de whitelist documentado sin desactivar TLS.

**Pruebas.** Integración con servidor mock TLS; verificar que no se hace request si falta config; verificar que la pass no aparece en logs.

### F-08 · Puerto Postgres expuesto al host con credenciales débiles — P1

**Problema.** `docker-compose.yml:28-29` mapea `5434:5432`; `DB_PASSWORD` default `botpassword`.

**Impacto.** Si el host es accesible, la base con PII queda expuesta con credenciales adivinables. Redis (bien) no se expone; Qdrant sí (`6334`).

**Corrección.** Quitar el mapeo de puerto de Postgres (acceso solo intra-red Docker); password fuerte; si se necesita acceso, túnel SSH. Revisar exposición de Qdrant.

**Pruebas.** `nmap` post-deploy: 5432/6333 no accesibles desde fuera.

---

## E. Plan de remediación (resumen)

> Detalle accionable, criterios de aceptación y checklists en
> [`../plan-remediacion/plan-remediacion-2026-06-13.md`](../plan-remediacion/plan-remediacion-2026-06-13.md).

- **Fase 0 — Contención inmediata:** rotar secretos, `.dockerignore`, cerrar/autenticar endpoints, quitar puerto Postgres.
- **Fase 1 — Seguridad y datos:** firma WhatsApp obligatoria, `compare_digest`, Vicidial TLS, no reflejar excepciones, deals por contacto completo.
- **Fase 2 — Estabilidad funcional:** endurecer routing/guardrails, tareas durables, arreglar `make worker`.
- **Fase 3 — Pruebas:** unit deterministas + matriz de auth + gitleaks en CI.
- **Fase 4 — Performance:** health usa pool, índices.
- **Fase 5 — Limpieza:** código muerto, docs, Dockerfile no-root.

---

## F. Plan de pruebas recomendado

- **Unit (deterministas, sin red):** `_extract_phone`/`_is_phone_attempt`, `_extract_all_kpis` (incl. inputs basura → no nombre falso), `mask_phone`, `verify_webhook_signature`, `_resolve_stage`, `_mensaje_contacto_asesor` con `freezegun` por franja horaria, `_en_ventana`.
- **Integración (DB de prueba, LLM mockeado):** upserts de leads idempotentes, transiciones del grafo con LLM stub, dedup de webhooks, drenado de debounce.
- **Seguridad:** matriz de auth por endpoint (sin token / token malo → 401/403); firma WhatsApp inválida; fuzz de `/webhooks/connector`; `gitleaks` en CI; assert `.env` ausente en imagen.
- **Regresión:** los 13 patrones del bot anterior como casos fijos (emoji≠número ✓ ya existe).
- **Manual/smoke:** `/health` 200; un mensaje WhatsApp real → respuesta + espejo Bitrix; un ciclo de rescate con `seguimiento-test`.
- **Pre-deploy checklist:** firma obligatoria activa, tokens != default, puertos DB cerrados, `.dockerignore` presente, OAuth Bitrix válido.

---

## G. Preguntas abiertas (no confirmables solo con el código)

1. ¿El repo es privado y los secretos de F-01 ya fueron rotados? Determina si F-01 es P0 efectivo o histórico.
2. ¿En producción `WHATSAPP_APP_SECRET` y `ADMIN_TOKEN` están realmente seteados? Si sí, F-03/F-06 están mitigados en la práctica (pero siguen siendo fallo-abierto en diseño).
3. ¿Caddy corre en la misma red Docker? `reverse_proxy api:8001` vs contenedor en `8000` (F-21) sugiere mismatch o un compose de Caddy aparte que no está en el repo.
4. ¿Hay un `.env` real en el contexto de build al construir la imagen? Confirma el alcance de F-02.
5. ¿El endpoint `/webhooks/connector` se usa en prod o todo va por polling? (F-23 sugiere que el push está roto para extraer phone.)

---

## H. Revisión adversarial de Codex Senior

**Falsos positivos descartados (para no inflar el reporte):**

- **SQL injection: NO existe.** `postgres/client.py` y todos los call-sites usan parámetros (`$1,$2`). El f-string en `seguimientos.py:471` solo inyecta el literal estático `AND telefono = $1`, sin datos de usuario. La afirmación del CLAUDE.md se sostiene.
- **HMAC en sí es correcto** (`compare_digest`); el problema es el `if` que lo envuelve, no el algoritmo.
- **`bitrix_sync` NO thrashea el timer de rescates:** el `AND bitrix_stage != $1` (línea 71) evita bumpear `updated_at` cuando el stage no cambió. Diseño correcto; no es bug.
- **Emoji tratado como número: ya resuelto** (`validacion.py` + test existente).

**Riesgos que el equipo podría subestimar:**

- **F-05 + F-02 juntos** son peores que por separado: imagen con secretos + endpoint abusable = compromiso completo, no incidente aislado.
- **F-11 (guardrails por substring)** es de seguridad, no solo de UX: la detección de fraude/ingeniería social se evade con reformular ("un conocido en la empresa me comentó…" no matchea). El bot podría dar credibilidad a solicitudes fraudulentas — justo el defecto #8 que el diseño dice haber resuelto.
- **F-09 (match por últimos 4 dígitos)** puede mezclar conversaciones de dos clientes distintos → fuga de datos personales entre leads. Riesgo LFPDPPP silencioso.

**Lo que NO se auditó a profundidad (evidencia insuficiente — requiere segunda pasada):**
`sondeo.py`, `oferta.py`, `objeciones.py` (RAG Qdrant), `context.py`, `state.py`, `kpi_export.py` (457 líneas, maneja PII y LLM), `qdrant/client.py`, `telegram/handlers.py` y los loaders de `knowledge/`. Se leyó su forma e interfaces, no su lógica línea por línea. **No se declaran estos archivos sanos** — quedan pendientes para la siguiente ronda. En particular `kpi_export.py` toca PII + LLM y merece su propio frente.

**Riesgos al desplegar tal cual:**

- Si `WHATSAPP_APP_SECRET`/`ADMIN_TOKEN` no están seteados → API esencialmente abierta.
- Imagen con `.env` → un pull basta para comprometer todo.
- `make worker` roto → si algún runbook depende de él, falla operativa.

**Recomendación final antes de modificar código:** ejecutar **Fase 0 de contención** (rotación + `.dockerignore` + cerrar endpoints), confirmar las 5 preguntas abiertas de §G, y autorizar una **segunda pasada de lectura** sobre los 6 archivos no auditados — especialmente `kpi_export.py` y los nodos de venta. No tocar la lógica del agente hasta cerrar el perímetro.

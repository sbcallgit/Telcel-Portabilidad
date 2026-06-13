# Plan de Remediación — Bot Telcel Portabilidad R4

**Fecha:** 2026-06-13 · **Rama base:** `auditoria-tecnica`
**Origen:** [`../diagnostico/auditoria-tecnica-2026-06-13.md`](../diagnostico/auditoria-tecnica-2026-06-13.md)
**Estado:** Propuesta — pendiente de aprobación. **Aún no se ha modificado código.**

---

## Cómo leer este plan

- Las fases están **ordenadas por riesgo**, no por esfuerzo. Fase 0 primero, siempre.
- Cada ítem referencia su hallazgo (`F-xx`) del diagnóstico.
- `Aceptación` = condición verificable que cierra el ítem (evidencia antes que afirmación).
- No se ejecuta ningún cambio hasta tu OK. Sugerencia: una rama por fase, PRs chicos.

**Leyenda de esfuerzo:** S = <1h · M = media jornada · L = 1+ día.

---

## Fase 0 — Contención inmediata (seguridad de perímetro)

> Objetivo: que el sistema deje de filtrar secretos y de aceptar tráfico no autenticado.
> **Bloquea cualquier deploy nuevo hasta completarse.**

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 0.1 | F-01 | Rotar bearer RAG (Caddy), password Vicidial, hash Qdrant; rotar `ADMIN_TOKEN`, `DB_PASSWORD`, `TELEGRAM_WEBHOOK_SECRET` en prod | M | Credenciales viejas inválidas; nuevas solo en gestor de secretos / `.env` no versionado |
| 0.2 | F-01 | Sacar el bearer de `Caddyfile` a variable de entorno de Caddy; quitar defaults sensibles de `settings.py` (dejar `""`) | S | `grep` del repo no devuelve secretos; `settings.py` sin valores reales |
| 0.3 | F-02 | Crear `.dockerignore` (`.env*`, `.git`, `reporteskpi/`, `tests/`, `*.md`, caches, `.venv`) | S | `docker build` + `docker run img sh -c '! test -f /app/.env'` pasa |
| 0.4 | F-02 | Rebuild + redeploy de imagen limpia; asumir imágenes previas comprometidas | M | Nueva imagen sin `.env` ni `reporteskpi/` (`docker history` limpio) |
| 0.5 | F-04 | Proteger `/webhooks/telegram/setup`, `/webhooks/telegram/info`, `/bitrix/install` con `X-Admin-Token` o sacarlos de la API pública | S | Test: sin token → 403 |
| 0.6 | F-05 | Autenticar `/webhooks/connector` (token/firma de Bitrix o allowlist de IP) | M | Test: POST sin credencial válida → 401; no dispara `send_message` |
| 0.7 | F-08 | Quitar mapeo `5434:5432` de Postgres en compose; revisar exposición de Qdrant `6334` | S | `nmap` al host: 5432 no accesible desde fuera |

**Decisión requerida:** ¿purgamos los secretos del historial de git (`git filter-repo`, reescribe historia → requiere coordinación con todos los clones) o basta con rotar y asumir el historial como quemado? **(Necesito tu llamada antes de tocar historia de git.)**

---

## Fase 1 — Seguridad y datos (fallo-cerrado)

> Objetivo: que las protecciones existentes no se puedan saltar por configuración u omisión.

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 1.1 | F-03 | Firma WhatsApp **obligatoria**: si `ENVIRONMENT=production` y no hay `WHATSAPP_APP_SECRET` → abortar arranque; nunca procesar sin firma válida | S | Test: arranque prod sin secret → error; POST sin firma → 401 |
| 1.2 | F-06 | `hmac.compare_digest` en `admin` y `telegram`; abortar en prod si tokens == default; rate-limit básico en `/admin/*` | M | Test: 403 con token malo; arranque prod con default → error |
| 1.3 | F-07 | Vicidial: `verify=True` (cert válido o CA pinning), credenciales en POST body, no en URL | M | Request no se emite sin TLS válido; pass ausente de logs |
| 1.4 | F-10 | No reflejar excepciones en `/bitrix/app` (`<pre>{exc}</pre>`); loggear genérico sin `resp.text` con tokens | S | Respuesta de error no contiene stack/token; log sanitizado |
| 1.5 | F-09 | Vincular deals por `CONTACT_ID`/teléfono completo, no por `*{telefono[-4:]}` | L | Dos teléfonos con mismos últimos 4 → deals distintos (test) |
| 1.6 | F-17 | Comparaciones constantes en todos los checks de token/secret | S | Revisión: ningún `!=` directo sobre secretos |
| 1.7 | F-22 | (Opcional) Password en Redis; evaluar cifrado de tokens OAuth en reposo | M | Redis exige auth; tokens no en claro |

---

## Fase 2 — Estabilidad funcional

> Objetivo: cerrar bugs de lógica y deuda que afecta operación.

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 2.1 | F-11 | Endurecer routing de `validacion.py`: matching por límites de palabra/regex, no `substring in`; reforzar guardrails de fraude/ingeniería social | L | Suite adversarial: reformulaciones de fraude no pasan; "cuando" no fuerza ruta horarios |
| 2.2 | F-20 | Tareas de background con referencia retenida o cola durable; decidir política ante restart (pérdida aceptada vs reintento) | M | No hay `create_task` huérfano; comportamiento documentado |
| 2.3 | F-13 | Eliminar `make worker` + dependencia `arq` (fantasma) o implementar el worker real | S | `make worker` funciona o no existe; `requirements` sin deps muertas |
| 2.4 | F-18 | Inicialización explícita del grafo en lifespan; quitar `get_event_loop().run_until_complete` | S | No hay init lazy con loop; arranque limpio |
| 2.5 | F-23 | Unificar formato de chat-id (`wa_`/`{phone}_`) entre `connector.py` y el handler, o eliminar el push si poll lo cubre | M | Push extrae phone correctamente o se retira |

---

## Fase 3 — Pruebas (red de seguridad)

> Objetivo: poder validar el sistema de forma determinista antes de cada cambio.

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 3.1 | F-15 | Separar unit (sin red, LLM mockeado) de E2E; mockear OpenRouter/WhatsApp/Bitrix en la suite de scenarios | L | `pytest` corre offline en CI sin API keys |
| 3.2 | — | Tests unit deterministas: `_extract_phone`, `_extract_all_kpis`, `mask_phone`, `verify_webhook_signature`, `_resolve_stage`, `_mensaje_contacto_asesor` (freezegun), `_en_ventana` | M | Cobertura real de funciones puras |
| 3.3 | — | Matriz de auth por endpoint (sin token / token malo → 401/403) | M | Test parametrizado verde |
| 3.4 | F-01/F-02 | `gitleaks`/`trufflehog` + assert `.env` ausente en imagen, en CI | S | Pipeline falla si reaparece secreto o `.env` en build |

---

## Fase 4 — Performance

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 4.1 | F-16 | `health.py` usa el pool existente, no `asyncpg.connect` por request | S | Health no abre conexión nueva (revisión + carga) |
| 4.2 | — | Índices: `seguimientos_log(lead_id)`; validar índice en `checkpoints(thread_id)` | S | `EXPLAIN` sin seq-scan en las queries calientes |

---

## Fase 5 — Limpieza y mantenibilidad

| # | Hallazgo | Acción | Esfuerzo | Aceptación |
|---|---|---|---|---|
| 5.1 | F-12 | Borrar código muerto en `seguimientos.py` (`_CADENCIAS`, `_cadencia`, `_siguiente_envio`, `_mensaje` no usados); corregir docstring obsoleto | S | `ruff`/grep sin referencias muertas; docstring describe la lógica real |
| 5.2 | F-14 | Dockerfile multi-stage + `USER` no-root; quitar gcc del runtime | M | Imagen corre como no-root; tamaño reducido |
| 5.3 | F-19 | Alinear `CLAUDE.md` (OpenRouter, no Anthropic), `make health` (puerto 8001), `make export_kpi` (ruta real) | S | Docs coinciden con el código |
| 5.4 | — | Mover los `.md` sueltos del root (`Informe_*`, `Plan_*`, `Script_*`, `VERA_*`) a `docs/` | S | Root limpio; navegación por `docs/` |

---

## Segunda pasada de auditoría (pendiente, read-only)

No incluida en las fases de fix porque es **lectura**, no cambio. Archivos sin auditar a profundidad:
`sondeo.py`, `oferta.py`, `objeciones.py`, `context.py`, `state.py`, `kpi_export.py`, `qdrant/client.py`, `telegram/handlers.py`, `knowledge/loaders/*`.
**Prioridad: `kpi_export.py`** (PII + LLM) y los nodos de venta.

---

## Preguntas a resolver antes de arrancar (de §G del diagnóstico)

1. ¿Repo privado y secretos ya rotados? → define urgencia real de F-01.
2. ¿`WHATSAPP_APP_SECRET` y `ADMIN_TOKEN` seteados en prod hoy?
3. ¿Caddy en la misma red Docker? (`api:8001` vs `8000`).
4. ¿Hay `.env` en el contexto de build?
5. ¿`/webhooks/connector` se usa en prod o todo va por polling?
6. ¿Purgamos historia de git o solo rotamos? (decisión de 0.x).

---

## Orden de ejecución sugerido

```
Fase 0  → (deploy congelado) → confirmar preguntas 1-6
Fase 1  → Fase 3.1/3.4 (CI + auth tests en paralelo)
Fase 2  → Fase 3.2/3.3
Fase 4  → Fase 5
Segunda pasada de auditoría (puede correr en paralelo desde el inicio)
```

Cada fase = una rama feature + PR chico. Nada va directo a `main`.
**No se inicia ningún fix sin tu aprobación explícita de esta lista.**

# Auditoría — 2ª pasada (archivos no cubiertos a fondo)

**Modo:** Read-only · **Rama:** `auditoria-tecnica` · **Fecha:** 2026-06-13
**Auditor:** Codex (codex:rescue), revisado por Claude.
**Alcance:** archivos que no se leyeron línea por línea en las pasadas previas —
`kpi_export.py`, nodos `oferta/sondeo/objeciones`, `context.py`, `connector.py`
(poll), `qdrant/client.py`, `telegram/handlers.py`.

> Sin SQLi/RCE nuevos. El riesgo nuevo es **confiabilidad, integridad de datos y
> precisión comercial**. Claude verificó P-09, P-13, P-16 contra el código (reales).

## Hallazgos

| ID | Sev | Archivo:línea | Problema | Recomendación |
|---|---|---|---|---|
| P-01 | P1 | `connector.py:252,281` · `connector_poll.py:45` | El cursor del poll avanza antes de confirmar entrega → mensajes del asesor se pueden perder | Avanzar cursor solo tras entrega confirmada; apoyarse en `connector_delivered:{id}` |
| P-04 | P1 | `kpi_export.py:279` | Resumen KPI manda PII (teléfonos/nombres/asesor) al LLM sin minimizar | Redactar PII antes de resumir; flag para desactivar |
| P-05 | P2 | `kpi_export.py:286` | Texto de usuario concatenado al prompt → prompt injection contamina BI | Delimitar como datos no confiables + anti-override + validar salida |
| P-06 | P2 | `kpi_export.py:62` | Fallback a `MemorySaver` en export standalone → sobrescribe KPIs con vacíos | Fail-closed: abortar si no hay checkpointer PG |
| P-07 | P2 | `kpi_export.py:442` | Loggea `thread_id` completo (= teléfono) → PII en logs | Enmascarar / hash |
| P-09 | P2 ✓ | `kpi_export.py:153` | `split("+")[0]` + `replace(tzinfo=UTC)` corrompe `CLOSEDATE` con offset | Parsear ISO preservando offset y `.astimezone(UTC)` |
| P-13 | P2 ✓ | `objeciones.py:19` | `_BUY_WORDS` con `"sí"`/`"ok"` por substring → cierre falso ("así no", "ok pero caro") | Word boundaries (reusar `_word_match`) |
| P-14 | P2 | `sondeo.py:260` | Ingeniería social se evalúa después de extraer recarga → fraude llega a oferta | Mover detección de fraude antes de extracción |
| P-03 | P2 | `connector.py:67` | `get`+`setex` no atómico de `connector_ext_chat` → deal/sesión duplicados | `SET NX`/lock por teléfono |
| P-11 | P2 | `qdrant/client.py:45` | Reindex borra colección y luego `add`; si falla, RAG sin corpus | Colección temporal + swap/alias |
| P-02 | P2 | `connector.py:143,210` | IDs de mensaje por `int(time.time())` → colisión en mismo segundo | `message_id` real / ms+contador / UUID |
| P-08 | P2 | `kpi_export.py:92` | `LIMIT 500` sin paginar → BI incompleto si hay más | Paginar por fecha/checkpoint |
| P-10 | P3 | `kpi_export.py:185` | Open Lines `LIMIT 50` sin paginar → tiempos KPI incorrectos en chats largos | Paginar hasta el inicio del chat |
| P-12 | P3 | `qdrant/client.py:31` | `ensure_collection` traga cualquier excepción como "no existe" | Capturar solo "not found"; propagar auth/timeout |
| P-15 | P3 | `oferta.py:75` · `sondeo.py:50` | `"tiempo"` en `_HORARIO_Q` → "no tengo tiempo" responde calendario | Separar "tiempo de portación" de la objeción |
| P-16 | P3 ✓ | `context.py:8,18` vs `sondeo.py:242` | Claro Drive "desde $10/todos" vs "desde $100" → respuesta contradictoria | **Decisión de negocio**: unificar a la fuente correcta |
| P-17 | P3 | `telegram/handlers.py:25` | `text.get(...).strip()` asume string → 500 con payload raro | `isinstance(text, str)` |

## Dictamen
Sin inyección clásica nueva. Prioridad: PII del export (P-04/P-07), corrupción de
tiempos (P-09), cierres falsos (P-13/P-14), y fiabilidad del poll (P-01).
`S-03` (CSV injection) ya quedó remediado en esta rama (`_sanitize_csv_row`).

## Estado de remediación (Fase 6)
- **Claude:** P-04, P-05, P-06, P-07, P-09 (`kpi_export.py`).
- **Codex:** P-13, P-14, P-15 (nodos de venta), P-17 (telegram), P-11, P-12 (qdrant).
- **Diferido:** P-01/P-02/P-03 (fiabilidad connector — requiere pruebas con Bitrix),
  P-08/P-10 (paginación), P-16 (decisión comercial: $10 vs $100).

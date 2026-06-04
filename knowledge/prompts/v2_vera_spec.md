# Prompt Version v2 — Alineado a VERA_Bot_Specification.md v1.0

**Fecha:** 2026-06-04
**Documento fuente:** `VERA_Bot_Specification.md v1.0`
**Archivos modificados:**
- `agents/portabilidad/context.py`
- `agents/portabilidad/nodes/validacion.py`
- `agents/portabilidad/nodes/sondeo.py`
- `agents/portabilidad/nodes/oferta.py`
- `agents/portabilidad/nodes/objeciones.py`
- `agents/portabilidad/nodes/cierre.py`
- `agents/portabilidad/nodes/escalate.py`

---

## Correcciones sobre v1

### Datos del catálogo ASL (errores críticos)

| Paquete | Error v1 | Corrección v2 |
|---|---|---|
| $30 | Bolsa redes: solo FB, Messenger, X | Bolsa redes: IG, FB, Messenger, X, Snapchat — 1 GB |
| $50 | Bolsa redes: 1 GB, solo FB, Messenger, X | Bolsa redes: IG, FB, Messenger, X, Snapchat — 1.5 GB |
| $80 | Bolsa 1.5 GB, NO ilimitadas | **6 redes ILIMITADAS** |
| $400 | "sin dato de GB publicado" | **5.5 GB** |
| Claro Drive | "Desde $100" | Incluido en TODOS los paquetes desde $10 |

### Identidad

- v1: "agente de inteligencia artificial de Telcel Región 4"
- v2: "Vera, asistente de Telcel" — sin ninguna mención a IA o tecnología
- Si preguntan "¿eres robot?": redirige a función sin confirmar ni negar

### Saludo (validacion.py)

- v1: Saludo genérico, sin hook de valor
- v2: Hook explícito de spec sec. 6.2: "triple de beneficios en tus recargas por 12 meses"
- Variantes deterministas para: "info", "me interesa", "cuánto cuesta", "¿eres robot?", "¿qué ofreces?"

### Flujo de sondeo

- v1: 2 preguntas (recarga + red social/uso)
- v2: 1 pregunta (recarga) → comparativa inmediata de beneficios Telcel vs. situación actual

### Objeciones

- v1: Solo lookup en BD por categoría
- v2: OBJECTIONS_BANK con top-10 objeciones oficiales + 4 extras (spec sec. 7) embebido en system prompt; el lookup en BD es complementario

### KPI de cierre

- v1: 5 campos bloqueantes (nombre, número, compañía, municipio, equipo_liberado)
- v2: 3 campos KPI bloqueantes (nombre, número, compañía — spec sec. 3.3); municipio es datos de payload no bloqueante

### Mensajes de handoff

- v1: Mensajes por motivo simples
- v2: Protocolo de 4 pasos (spec sec. 10.2): explica por qué, confirma datos, expectativa de tiempo, pregunta si hay duda

### Nuevas secciones en context.py

| Constante | Contenido |
|---|---|
| `OBJECTIONS_BANK` | Top-10 objeciones oficiales + extras con texto exacto de spec sec. 7 |
| `GREETING_VARIANTS` | Saludos por disparador de spec sec. 6.2 |
| `OFFER_TEMPLATE` | Plantilla de presentación de oferta de spec sec. 6.5 |
| `HANDOFF_SCRIPT` | Protocolo de escalamiento de spec sec. 10.2 |

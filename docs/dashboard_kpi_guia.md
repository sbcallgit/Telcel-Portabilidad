# Dashboard KPI — Guía de análisis

**URL:** `https://kpi.callcomcc.io/dashboard`  
**Acceso:** correo + contraseña (JWT 8h)  
**Fuente de datos:** PostgreSQL — tablas `kpi_conversaciones`, `bitrix_eventos`, `bitrix_deal_timeline`, `leads`

---

## Sección: Telcel Portabilidad

### Cards de resumen

| Card | Qué mide | Cómo interpretarlo |
|---|---|---|
| **Total conversaciones** | Leads que iniciaron contacto con el bot | Volumen bruto de la campaña |
| **Conversiones (Venta)** | Deals en stage `C90:WON` | Tasa = Ventas / Total. Meta: >10% |
| **Tiempo 1ª respuesta** | Segundos entre primer mensaje del cliente y primera respuesta del bot | Debe ser <30s. Valores altos indican problema de debounce o carga |
| **Escalados a asesor** | Deals que llegaron a `C90:UC_8WB2DT` o `C90:PROSPECTO` | Carga real de trabajo para el equipo de asesores |

---

### Gráfica: Funnel de conversión

**Fuente:** tabla `bitrix_deal_timeline` (una fila por deal, una columna por stage).  
**Tipo:** barras horizontales. El ancho de cada barra es proporcional al número de deals que llegaron a ese stage.

#### Cómo leer las barras

```
IA Porta     ████████████████████  16 deals  (100% — el máximo)
Prospecto    ████                   3 deals  (19%)
Escalamiento ███                    2 deals  (13%)
Rescate 1    █████████              9 deals  (56%)
Rescate 2    ████████               8 deals  (50%)
Rescate 3    ████████               8 deals  (50%)
Venta        ██                     2 deals  (13%)
Caído        ███                    3 deals  (19%)
```

- La barra roja (**IA Porta**) es siempre la más larga — es el 100% de referencia.
- Las barras azules son etapas intermedias.
- La barra verde (**Venta**) y gris (**Caído**) son los resultados finales.

#### Tooltip al pasar el mouse

Al pasar el mouse sobre cualquier barra aparece:

```
9 deals (56%) · prom. 52m 06s
```

- **9 deals** = cuántos deals llegaron a ese stage
- **56%** = porcentaje respecto a IA Porta
- **prom. 52m 06s** = tiempo promedio que los deals permanecieron en esa etapa antes de avanzar

#### Lectura por etapa

| Etapa | Qué indica si es alta | Qué indica si es baja |
|---|---|---|
| **IA Porta** | Volumen de leads entrantes (siempre 100%) | — |
| **Prospecto** | Bot cerrando KPIs correctamente | Bot no captura nombre/número/compañía |
| **Escalamiento** | Leads que piden asesor antes de completar KPIs | — |
| **Rescate 1/2/3** | Muchos leads se enfrían sin responder | Bot no genera suficiente interés |
| **Venta** | Asesores convirtiendo bien | Asesores no dan seguimiento oportuno |
| **Caído** | Alta rotación / leads de mala calidad | — |

#### Señales de alerta

- **Rescate 1 > 50% de IA Porta** — más de la mitad de los leads se enfrían. Revisar el nodo de sondeo u oferta del bot.
- **Prospecto < 15%** — el bot no está completando KPIs. Revisar el nodo de cierre.
- **Venta < 10% de Prospecto** — los asesores no están convirtiendo. Revisar tiempo de contacto después del escalamiento.
- **Tiempo promedio en Escalamiento > 2h** — los asesores tardan demasiado en contactar al lead después de que el bot lo escala.

---

### Tabla: Transiciones de etapa recientes

**Fuente:** tabla `bitrix_eventos` (tipo `sistema`) + JOIN con `bitrix_deal_timeline` para el asesor actual.  
**Muestra:** últimas 50 transiciones de stage, ordenadas por fecha descendente.

#### Columnas

| Columna | Descripción |
|---|---|
| **Deal** | ID del deal en Bitrix. Clic en Bitrix para ver el deal completo |
| **Teléfono** | Número del lead. Vacío = deal creado manualmente por asesor sin pasar por el bot |
| **Transición** | Movimiento del deal: `etapa anterior → etapa nueva` |
| **Duración en etapa** | Tiempo que el deal estuvo en la etapa anterior antes de moverse. `—` = primer movimiento sin historial previo |
| **Fecha** | Cuándo ocurrió el cambio de stage (hora local Monterrey) |
| **Asesor** | ID del asesor asignado al deal en ese momento (ID numérico de Bitrix) |
| **Último mensaje cliente** | Último texto del lead justo antes del cambio de stage |
| **Última resp. Vera** | Última respuesta del bot antes del cambio de stage |

#### Cómo usar esta tabla en análisis

**Ejemplo de fila:**
```
Deal: 2305454
Teléfono: 593991053639
Transición: Lead Nuevo / IA Porta → Prospecto
Duración: 3m 37s
Último cliente: "Leandro José Paredes Chala, 8121234567, unefon"
Última Vera:    "¡Listo, Leandro! Ya tengo todo lo que necesito..."
```

**Lectura:** en 3 minutos y 37 segundos, el bot capturó nombre, número a portar y compañía donante y escaló correctamente al asesor.

**Casos de uso:**

- **Diagnosticar por qué un deal cayó** — ver el último mensaje del cliente antes de `→ Caído`. Si dice "no me interesa" el lead era frío. Si dice "qué promoción tienen" y cayó, el asesor nunca lo contactó.
- **Medir velocidad del bot** — la duración en `IA Porta` muestra cuánto tarda el bot en completar el flujo. Menos de 5 minutos es buena señal.
- **Auditar asesores** — filtrar por asesor y ver qué deals convierte vs. cuáles deja caer.
- **Detectar loops de rescate** — si el mismo deal aparece varias veces (`Rescate 1 → Caído → Rescate 1 → Caído`), hay un problema de sincronización en `job_bitrix_sync`.

---

## Sección: Meta Ads — Portabilidad 2 Callcom

> **Próximamente — en desarrollo**

Visualizará las métricas de inversión publicitaria de la cuenta `act_3292969264212775` vía Meta Ads Insights API.

### Gráficas planeadas

| Gráfica | Descripción |
|---|---|
| **Gasto vs Conversaciones** | Línea doble: gasto diario en MXN e iniciaciones de conversación WhatsApp. Permite ver si el CPL sube o baja con el tiempo |
| **Distribución por campaña** | Barras apiladas por campaña: impresiones, clics, conversaciones WA, ventas atribuidas |
| **CPL histórico** | Tendencia del Costo Por Lead (conversación WhatsApp iniciada) día a día |

### Cards planeadas

| Card | Métrica |
|---|---|
| Gasto total | MXN invertidos en el período |
| CPL WhatsApp | Gasto / Conversaciones WA iniciadas |
| CTR promedio | Clics / Impresiones |
| Conversaciones WA | `onsite_conversion.total_messaging_connection` |

---

## Sección: Atribución UTM

> **Próximamente — en desarrollo**

Conecta los leads del bot con los anuncios de Meta que los originaron, usando los campos UTM capturados en el webhook Click-to-WhatsApp.

### Gráficas planeadas

| Gráfica | Descripción |
|---|---|
| **Leads por fuente** | Dona o barras: cuántos leads vienen de cada `utm_source` (Facebook, Instagram, etc.) |
| **Tasa de conversión por campaña** | Tabla: campana → leads → ventas → tasa. Identifica qué campaña tiene mejor ROI |
| **Leads por Ad ID** | Tabla detallada por anuncio individual con leads y ventas atribuidas |

### Cards planeadas

| Card | Métrica |
|---|---|
| Leads con UTM | % de leads con atribución completa |
| Ventas atribuidas | Ventas que tienen `ctwa_clid` vinculado |
| Mejor campaña | Campaña con mayor tasa de conversión |

---

## Sección: Megacable

> **En producción — datos desde BD externa `bot_megacable`**

KPIs del agente conversacional de Megacable. Fuente independiente: BD PostgreSQL en `147.79.78.75:5433`.

### Gráficas planeadas

| Gráfica | Descripción |
|---|---|
| **Estado de conversaciones** | Dona: abiertas / cerradas / escaladas |
| **Mensajes por actor** | Barras: cliente vs bot vs humano — muestra cuánto automatiza el bot |
| **Tiempo de primera respuesta** | Histograma de tiempos de respuesta del bot |

---

## Filtros globales

Todas las secciones respetan el filtro de fecha **Desde / Hasta** en la parte superior. Al aplicar el filtro, todas las gráficas y tablas se recalculan con el rango seleccionado.

El filtro **Stage** y **Buscar** aplican únicamente a la tabla de conversaciones de Telcel, no al funnel.

---

## Notas técnicas

- **`bitrix_deal_timeline`** se popula automáticamente con cada cambio de stage en Bitrix (webhook `POST /bitrix/stage-event`). Datos disponibles desde la fecha de activación del webhook.
- **`bitrix_eventos`** registra todos los eventos (mensajes + cambios de stage) desde el inicio de la campaña.
- El funnel solo incluye deals cuya `fecha_new` cae dentro del rango de fechas seleccionado. Deals sin `fecha_new` (creados manualmente sin pasar por el bot) no aparecen en el conteo de IA Porta pero sí pueden aparecer en otras etapas.
- Los IDs de asesor son numéricos (Bitrix). Para ver el nombre completo, buscar el ID en `Bitrix24 > Empleados`.

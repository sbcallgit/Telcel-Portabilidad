# Manual: Dashboard KPI + Integración con Bitrix24

**Versión:** 2026-06-26  
**Aplica a:** Bot Telcel Portabilidad — Región 4

---

## Índice

1. [Acceso al Dashboard KPI](#1-acceso-al-dashboard-kpi)
2. [Secciones del Dashboard](#2-secciones-del-dashboard)
3. [Detalle de Conversación](#3-detalle-de-conversación)
4. [Pestañas embebidas en el deal de Bitrix24](#4-pestañas-embebidas-en-el-deal-de-bitrix24)
5. [Botón de control del bot (Pausar / Activar)](#5-botón-de-control-del-bot-pausar--activar)
6. [Configuración inicial del embed en Bitrix24](#6-configuración-inicial-del-embed-en-bitrix24)
7. [Re-autorización y mantenimiento](#7-re-autorización-y-mantenimiento)
8. [Preguntas frecuentes](#8-preguntas-frecuentes)

---

## 1. Acceso al Dashboard KPI

### URL de acceso

```
https://portabilidad.callcomcc.io/dashboard/
```

### Credenciales

| Usuario | Contraseña |
|---|---|
| sbecerra@callcom.mx | Callcom.2025 |
| passpace04@gmail.com | Callcom.2025 |
| mbecerra@callcom.mx | Callcom.2025 |

La sesión dura **8 horas**. Al expirar, el sistema redirige automáticamente al login.

### Primer ingreso

1. Abre la URL en el navegador
2. Ingresa correo y contraseña
3. El dashboard carga automáticamente con los datos del mes en curso

---

## 2. Secciones del Dashboard

### 2.1 Telcel Portabilidad

Sección principal con KPIs operativos del bot y los asesores.

**KPI Cards superiores:**

| Card | Qué mide |
|---|---|
| Total Conversaciones | Conversaciones únicas registradas en el período |
| Ventas (WON) | Deals marcados como Venta por el asesor en Bitrix24 |
| 1ª Respuesta Promedio | Tiempo promedio desde el primer mensaje del cliente hasta la primera respuesta del bot |
| Automatización | % de conversaciones resueltas sin intervención de asesor humano |
| Con Asesor Humano | Número de conversaciones que llegaron a escalamiento |
| Tiempo de Cierre | Tiempo promedio desde el primer contacto hasta que el deal avanza a Prospecto o WON |

**Filtros disponibles:**
- **Desde / Hasta:** rango de fechas (por defecto mes actual)
- **Etapa:** filtra la tabla de conversaciones por stage de Bitrix24
- **Buscar:** búsqueda por teléfono en la tabla

**Gráficas:**

| Gráfica | Descripción |
|---|---|
| Distribución por Etapa | Doughnut — muestra cuántos deals están en cada stage. La leyenda muestra `Etapa: N (X%)` |
| Mensajes por Actor | Barras — total de mensajes de bot vs usuario vs asesor. La línea secundaria muestra el promedio por conversación |
| Funnel de Conversión | Barras verticales con línea de % de conversión acumulada desde el primer stage |

**Tabla de conversaciones:**

Muestra todas las conversaciones del período con columnas: teléfono, stage actual, asesor asignado, fecha, mensajes cliente/bot/asesor y motivo de escalamiento.

> Cada fila es clickeable — al hacer clic navega al **Detalle de Conversación**.

---

### 2.2 Meta Ads — Portabilidad 2 Callcom

Métricas de la cuenta de anuncios de Meta directamente desde la API de Ad Insights.

**KPI Cards:** Gasto total, impresiones, alcance, clics, CTR, conversaciones WhatsApp iniciadas, CPL (costo por lead).

**Filtros:** rango de fechas + nivel de agregación (campaña / conjunto de anuncios / anuncio individual).

**Gráfica:** barras horizontales con gasto vs conversaciones WhatsApp por campaña (nombres completos, sin truncar).

---

### 2.3 Atribución UTM

Análisis de origen de leads capturados desde Click-to-WhatsApp de Meta Ads.

Muestra qué campañas, fuentes y anuncios específicos generaron leads y cuáles resultaron en ventas.

---

### 2.4 Megacable

KPIs del agente Megacable (base de datos externa). Funciona con filtro de fechas independiente.

---

## 3. Detalle de Conversación

Al hacer clic en cualquier fila de la tabla de conversaciones, el dashboard navega a:

```
https://portabilidad.callcomcc.io/dashboard/conversation/{telefono}
```

### Qué muestra

**Encabezado:**
- Número de teléfono del lead
- Badge con el stage actual del deal (color según etapa)
- Asesor asignado y fecha del primer mensaje

**KPI Cards:**

| Card | Descripción |
|---|---|
| Mensajes Bot | Total de mensajes enviados por Vera en esta conversación |
| Mensajes Usuario | Total de mensajes del cliente |
| Mensajes Asesor | Total de mensajes del asesor humano (si intervino) |
| Costo Total (USD) | Costo acumulado de los mensajes del bot (tokens × precio Claude) con desglose de tokens entrada/salida |
| 1ª Respuesta | Tiempo desde el primer mensaje del cliente hasta la primera respuesta del bot |
| Tiempo de Cierre | Tiempo desde el primer contacto hasta el cierre del deal |

**Resumen:**

Párrafo generado por IA (3 oraciones) que describe: qué quería el cliente, cómo respondió el agente y el resultado de la conversación. Incluye el motivo de escalamiento si aplica.

**Tabla de mensajes:**

Cronología completa de la conversación ordenada por hora. Columnas:

| Columna | Descripción |
|---|---|
| Hora | Fecha y hora exacta del mensaje (dd/mm HH:MM:SS) |
| Actor | Badge de color: azul = Usuario, rojo = Bot, amarillo = Asesor |
| Mensaje | Texto completo del mensaje |
| Costo | Costo en USD del mensaje (solo mensajes del bot) |
| Tokens | Tokens consumidos: entrada↑ salida↓ (solo mensajes del bot) |

**Trazabilidad del Pipeline:**

Tarjetas horizontales scrolleables que muestran cada cambio de stage del deal con:
- Nombre de la etapa
- Fecha y hora de entrada a la etapa
- Tiempo que el deal estuvo en la etapa anterior

Debajo de las tarjetas hay una tabla detallada con las mismas transiciones.

### Navegación

El botón **← Volver** regresa a la tabla principal del dashboard conservando los filtros activos.

---

## 4. Pestañas embebidas en el deal de Bitrix24

Cada deal del pipeline 90 tiene **dos pestañas** disponibles, con acceso diferenciado según el rol:

| Pestaña | Para quién | Contenido |
|---|---|---|
| **"Vera · Conversación"** | Supervisores | Historial completo: KPIs, mensajes, costos, resumen AI, pipeline + botón toggle |
| **"Control Bot"** | Asesores | Solo el botón Pausar/Activar — sin datos sensibles |

---

### 4.1 Pestaña "Vera · Conversación" (supervisores)

Muestra la misma información del Detalle de Conversación del dashboard, embebida directamente en el deal:

- **Botón toggle** en el header — Pausar/Activar el bot para ese lead
- **KPI cards:** mensajes bot/usuario/asesor, costo total con tokens
- **Resumen AI** de la conversación y motivo de escalamiento
- **Tabla cronológica de mensajes** con timestamps, badges por actor, costo y tokens del bot
- **Trazabilidad del pipeline** con tarjetas y tabla de transiciones de stage

### 4.2 Pestaña "Control Bot" (asesores)

Vista minimalista — solo lo necesario para controlar el bot:

```
┌──────────────────────────────┐
│     Deal #2302394            │
│   Control del Bot Vera       │
│                              │
│   ● Bot Activo               │
│                              │
│   [ ⏸ Pausar Bot ]          │
└──────────────────────────────┘
```

- **Punto verde + "Bot Activo"** → el bot responde normalmente
- **Punto rojo + "Bot Pausado"** → el bot ignora mensajes entrantes; el asesor gestiona el chat

El cambio es inmediato y no recarga la página. Sin acceso a mensajes, costos ni resúmenes.

---

## 5. Botón de control del bot (Pausar / Activar)

Disponible en ambas pestañas. Funciona igual en las dos.

### Cómo usarlo

1. Abrir el deal en Bitrix24 y hacer clic en **"Control Bot"** (o "Vera · Conversación")
2. El estado actual se muestra al cargar — no requiere acción previa
3. Para pausar: clic en **"⏸ Pausar Bot"** → botón cambia a rojo "▶ Activar Bot"
4. Para reactivar: clic en **"▶ Activar Bot"** → botón vuelve a verde

### Cuándo pausar el bot

- Cuando el asesor toma el control de la conversación directamente en Open Lines
- Cuando el cliente está en proceso de portabilidad activa (NIP, validación con el asesor)

### Notas

- La pausa persiste aunque el asesor cierre la pestaña o el deal
- Si el deal pasa a **Caído** (`C90:LOSE`), el bot se reactiva automáticamente
- El polling del asesor sigue activo aunque el bot esté pausado — los mensajes del asesor llegan al cliente normalmente vía WhatsApp

---

## 6. Configuración inicial del embed en Bitrix24  

Este proceso se hace **una sola vez** al configurar el sistema por primera vez, o cuando se cambian los scopes de la app en Bitrix24.

### Paso 1 — Agregar el scope `placement` a la app local

1. Inicia sesión en el portal: `https://b24-ahyle8.bitrix24.mx`
2. Ve a **Aplicaciones → Mis aplicaciones** (o "Developer resources")
3. Encuentra la app local del bot y haz clic en **Editar**
4. En la sección de **permisos/scopes**, busca y activa **`placement`**
5. Guarda los cambios

> El scope `placement` no está disponible en webhooks entrantes de Bitrix24 — solo funciona con apps OAuth. No intentar via webhook.

---

### Paso 2 — Autorizar la app (obtener token OAuth con scope placement)

Abre esta URL en el navegador **con tu sesión de Bitrix24 activa**:

```
https://telegram-portabilidad.callcomcc.io/bitrix/auth
```

El sistema redirige al portal de Bitrix24. Aparece una pantalla de autorización pidiendo aprobar los permisos de la app (incluyendo `placement`).

Haz clic en **"Permitir"** o **"Autorizar"**.

Si todo va bien, el navegador muestra:

```
✅ Autorización exitosa.
Los tokens de Bitrix24 se guardaron correctamente.
Puedes cerrar esta ventana.
```

---

### Paso 3 — Registrar el placement en Bitrix24

Una vez que el token está guardado, ejecuta este comando desde una terminal (o usa curl desde cualquier máquina):

```bash
curl -X POST https://portabilidad.callcomcc.io/admin/bitrix-placement-bind \
  -H "X-Admin-Token: <ADMIN_TOKEN>"
```

Respuesta esperada:

```json
{
  "status": "ok",
  "handler": "https://telegram-portabilidad.callcomcc.io/bitrix/deal-embed",
  "bitrix_result": {
    "result": true
  }
}
```

Si `"result": true` → el placement quedó registrado.

---

### Paso 4 — Verificar en Bitrix24

1. Abre cualquier deal del pipeline 90 en Bitrix24
2. Busca la pestaña **"Vera · Conversación"** junto a las pestañas estándar
3. Haz clic — debe cargar el historial de la conversación del lead

> Si la pestaña no aparece de inmediato, recarga la página del deal con F5.

---

## 7. Re-autorización y mantenimiento

### Cuándo re-autorizar

| Situación | Acción requerida |
|---|---|
| El token OAuth expiró (refresh_token vencido, ~60 días) | Repetir Pasos 2 y 3 |
| Se agregaron nuevos scopes a la app en Bitrix24 | Repetir Pasos 1, 2 y 3 |
| La pestaña del deal muestra "Token de Bitrix inválido o expirado" | Repetir Paso 2 (el Paso 3 no es necesario si el placement ya está registrado) |
| Se migra a un nuevo servidor o dominio | Actualizar la URL del handler en Bitrix24 y repetir Paso 3 |

### Verificar el estado del token

Para comprobar qué scopes tiene el token activo:

```bash
# Desde el servidor (dentro del contenedor API):
docker exec telcel-portabilidad-api-1 python3 -c "
import asyncio, httpx
async def main():
    from integrations.bitrix.oauth import get_token
    token = await get_token()
    async with httpx.AsyncClient() as hx:
        r = await hx.get('https://b24-ahyle8.bitrix24.mx/rest/scope', params={'auth': token})
        print('Scopes activos:', r.json().get('result'))
asyncio.run(main())
"
```

Debe incluir `placement` en la lista. Si no aparece, repetir el Paso 1 y 2.

### Ver los placements registrados

```bash
docker exec telcel-portabilidad-api-1 python3 -c "
import asyncio, httpx
async def main():
    from integrations.bitrix.oauth import get_token
    token = await get_token()
    async with httpx.AsyncClient() as hx:
        r = await hx.post('https://b24-ahyle8.bitrix24.mx/rest/placement.list', params={'auth': token})
        print(r.json())
asyncio.run(main())
"
```

---

## 8. Preguntas frecuentes

**¿Por qué la pestaña no aparece en el deal?**

Verificar en orden:
1. El deal pertenece al pipeline 90 — los placements solo aplican al pipeline configurado
2. El placement está registrado — ejecutar el comando de verificación de placements
3. Refrescar la página del deal en Bitrix24

---

**¿Por qué la pestaña muestra "Token de Bitrix inválido"?**

El token OAuth expiró. Abrir `https://telegram-portabilidad.callcomcc.io/bitrix/auth` en el navegador con sesión de Bitrix activa.

---

**¿Por qué la pestaña carga pero no muestra mensajes?**

La conversación existe en Bitrix24 pero no tiene eventos registrados en `bitrix_eventos`. Esto ocurre con deals muy antiguos (antes de que se activara el sistema de trazabilidad). Los datos del resumen (si existen en `kpi_conversaciones`) sí se mostrarán.

---

**¿La pestaña funciona igual para todos los asesores?**

Sí. Cualquier asesor que tenga acceso al deal en Bitrix24 puede ver la pestaña. La autenticación usa el token OAuth del usuario de Bitrix que abre la pestaña — no requiere credenciales del dashboard.

---

**¿Con qué frecuencia se actualizan los datos del dashboard?**

| Dato | Frecuencia de actualización |
|---|---|
| Tabla de conversaciones | Diaria (job nocturno a las 3am) o manual via `/admin/kpi-export` |
| Stages en Bitrix24 | Cada 30 minutos (job `bitrix_sync`) |
| Meta Ads Insights | En tiempo real al cargar la sección (consulta directa a Meta API) |
| Datos Megacable | En tiempo real al cargar la sección |

---

**¿Cómo forzar la actualización del dashboard manualmente?**

```bash
curl -X POST https://portabilidad.callcomcc.io/admin/kpi-export \
  -H "X-Admin-Token: <ADMIN_TOKEN>"
```

Retorna `{"status": "started"}` inmediatamente y corre en background. En ~2-3 minutos los datos se actualizan.

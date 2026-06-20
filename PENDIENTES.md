# Pendientes — Bot Telcel Portabilidad

---

## Alta prioridad

### 1. Guardia `MAX_SEGUIMIENTOS` en Rescate 2 y 3
**Archivo:** `jobs/seguimientos.py`

`_procesar_rescate2` y `_procesar_rescate3` no verifican `seguimientos_enviados < MAX_SEGUIMIENTOS`.
Si `job_bitrix_sync` sincroniza un stage que vuelve a poner el lead en `C90:1` o `C90:2`
(por movimiento manual del asesor en Bitrix), los rescates 2 y 3 se dispararían de nuevo
indefinidamente. Agregar la misma guardia que ya tiene `_procesar_lead`.

### 2. Verificación ventana 24h de Meta (riesgo de ban)
**Archivo:** `jobs/seguimientos.py` / `integrations/whatsapp/client.py`

WhatsApp Business Platform solo permite mensajes de texto libre dentro de las 24 horas
posteriores al último mensaje del usuario. Después de 24h, Meta exige plantilla aprobada (HSM).
El bot actualmente envía texto libre sin verificar el tiempo transcurrido, lo que viola la
política y puede generar ban del número.

Opciones:
- Omitir el seguimiento si `minutos_desde_ultimo_mensaje > 1440` (24h)
- O enviar usando una plantilla HSM aprobada para rescates fuera de ventana

---

## Media prioridad

### 3. Dashboard KPI (HTML/CSS/JS)
**Archivos nuevos:** `api/routes/admin.py` (endpoint) + `dashboard.html`

Visualización de `kpi_conversaciones` en el navegador. Requiere:
- Endpoint `GET /admin/kpi-data` que exponga los datos como JSON (protegido con `X-Admin-Token`)
- Archivo `dashboard.html` estático con Chart.js (sin dependencias adicionales):
  - Tarjetas: total conversaciones, conversiones (C90:WON), tasa de conversión, tiempo promedio primera respuesta
  - Gráfica de distribución por stage (`estado_actual`)
  - Gráfica de mensajes por actor (bot / cliente / asesor)
  - Tabla de conversaciones recientes con paginación

---

## Notas

- Los pendientes resueltos se mueven a `bitacora.md` con fecha y descripción del cambio.
- Prioridad revisada en cada sesión de desarrollo.

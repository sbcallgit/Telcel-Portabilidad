# Reporte de Actividades — Bot Telcel Portabilidad

**Periodo:** 18 de junio al 30 de junio de 2026

---

| Fecha | Actividades principales |
|---|---|
| 2026-06-19 | Registro de lead desde primer mensaje (cubre todos los seguimientos); ajuste de espera de Rescate 3 a 2h antes de llamada Vicidial; fix de limpieza de `seguimientos_log`/`seguimientos_fallidos` en reset de prueba |
| 2026-06-20 | Nuevo dashboard KPI (Angular + Looker Studio); corrección de URL embed de Looker Studio (page ID y sandbox); creación de `PENDIENTES.md` con tareas de seguimientos y dashboard |
| 2026-06-21 | Manual de implementación imconnector WhatsApp↔Bitrix24 (OAuth, registro del conector, flujo de mensajes) |
| 2026-06-22 | Reporte KPI diario y mensual acumulado por correo (múltiples destinatarios); autenticación por email/contraseña en el dashboard; captura de UTMs y referral Click-to-WhatsApp en `leads`; secciones de Atribución UTM y Meta Ads Insights en dashboard; Meta Conversions API (CAPI) con match rate mejorado; módulo y estilos del dashboard Megacable; trazabilidad de etapas del deal en `kpi_conversaciones`; fixes de reactivación/pausa automática del bot |
| 2026-06-23 | Tablas `bitrix_eventos` y `bitrix_deal_timeline` para trazabilidad completa de stages por webhook de automatización; snapshot de últimos mensajes por actor en cada cambio de stage; comandos del asesor en chat Bitrix para pausar/activar el bot; tracking de costo de tokens LLM por nodo/conversación; funnel de conversión con tiempos promedio en el dashboard; guía de análisis del dashboard KPI |
| 2026-06-24 | Campo `motivo_escalacion` en KPIs y campos personalizados (UF) en deals de Bitrix; detección de "telcel a telcel" desde el primer mensaje en `validacion_node`; reactivación automática de deals Caídos a Recuperación en nuevo contacto; corrección de lógica de seguimientos automáticos; documento `estructura_tablas.md` con esquema completo de PostgreSQL |
| 2026-06-26 | Página de detalle de conversación en el dashboard; embed de conversación en pestaña del deal de Bitrix24 vía OAuth placement; endpoint `GET /bitrix/auth`; manual completo de dashboard KPI e integración Bitrix24; 6 cotizaciones de agentes de voz IA (ElevenLabs+SIP, SIP propio self-hosted, NVIDIA Riva, AMD ROCm, vLLM+Llama 70B, plataforma multi-cliente) con tabla comparativa y ruta progresiva |
| 2026-06-29 | Sección ROI de campaña en dashboard y reporte de correo — CPL, CPA y % de conversión por campaña |
| 2026-06-30 | Botón Pausar/Activar bot en pestañas de Bitrix24, incluyendo nueva pestaña "Control Bot" para asesores; modal de información contextual (ⓘ) para gráficas del dashboard |

**Nota:** no hubo commits registrados el 25, 27 y 28 de junio de 2026. El 31 de junio no existe en el calendario (junio tiene 30 días).

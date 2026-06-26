# Cotizaciones — Agentes IA Smart

**Proyecto:** Bot Telcel Portabilidad — Expansión a Voz  
**Fecha:** 2026-06-26  
**Tarifa desarrollador:** $7.50 USD/hora

---

## Cotización #1 — Agente de Voz con ElevenLabs SDK + SIP Trunk

### Alcance del desarrollo

| Módulo | Descripción | Días |
|---|---|---|
| Configuración ElevenLabs Agent | System prompt en español, voz, personalidad de Vera, idioma, detección de fin de turno | 0.5 |
| SDK integration + pipeline WebSocket | Conexión en tiempo real audio → ElevenLabs → audio, manejo de errores y reconexión | 1.5 |
| SIP trunk integration | Integración con proveedor seleccionado vía TeXML/API sin Asterisk | 1.5 |
| Endpoint `POST /admin/voice-call` | Recibe `deal_id`, valida, obtiene teléfono, dispara llamada, retorna estado | 0.5 |
| Trigger desde Bitrix24 | Botón en el deal (placement) que llama al endpoint | 1.0 |
| Contexto del lead al agente | Extrae historial de `bitrix_eventos`, nombre, compañía donante, objeción, recarga — se inyecta como contexto al agente antes de marcar | 1.0 |
| Transcripción + resultado en BD | Guarda transcripción completa, duración y resultado en `bitrix_eventos` + actualiza deal en Bitrix | 1.0 |
| Manejo de concurrencia y cola | Redis queue para miles de llamadas simultáneas, rate limiting, reintentos | 1.0 |
| Testing QA end-to-end | Pruebas con llamadas reales, latencia, casos edge (no contesta, número inválido, colgado abrupto) | 1.0 |
| **Total** | | **9 días hábiles** |

### Costo de desarrollo

| Concepto | Horas | Tarifa | Total |
|---|---|---|---|
| Desarrollo backend (Python/FastAPI) | 48 h | $7.50 USD/h | $360 |
| Integración SIP + ElevenLabs | 16 h | $7.50 USD/h | $120 |
| QA + pruebas en producción | 8 h | $7.50 USD/h | $60 |
| **Total desarrollo (única vez)** | **72 h** | | **$540 USD** |

### Costo por minuto — desglose por componente

| Componente | Telnyx | Vonage | Twilio |
|---|---|---|---|
| ElevenLabs Conversational AI | $0.1000/min | $0.1000/min | $0.1000/min |
| SIP Trunk — MX móvil | $0.0045/min | $0.0270/min | $0.0400/min |
| SIP Trunk — MX fijo | $0.0030/min | $0.0260/min | $0.0280/min |
| **Total/min (móvil)** | **$0.1045** | **$0.1270** | **$0.1400** |
| **Total/min (fijo)** | **$0.1030** | **$0.1260** | **$0.1280** |

> ElevenLabs representa el 95.7% del costo por minuto con Telnyx. La elección del proveedor SIP impacta poco el costo total.

### Costo por llamada según duración (Telnyx, móvil)

| Duración | ElevenLabs | SIP Telnyx | **Total** |
|---|---|---|---|
| 2 min | $0.20 | $0.009 | **$0.209** |
| 4 min | $0.40 | $0.018 | **$0.418** |
| 6 min | $0.60 | $0.027 | **$0.627** |
| 8 min | $0.80 | $0.036 | **$0.836** |

### Infraestructura mensual (Telnyx + ElevenLabs Business $825/mes)

| Volumen | Llamadas/día | Min/mes | ElevenLabs | SIP Telnyx | **Total/mes** |
|---|---|---|---|---|---|
| Bajo | 100 | 12,000 | $2,025 | $54 | **$2,079** |
| Medio | 500 | 60,000 | $6,825 | $270 | **$7,095** |
| Alto | 1,000 | 120,000 | $12,825 | $540 | **$13,365** |
| Masivo | 5,000 | 600,000 | $60,825 | $2,700 | **$63,525** |

### Resumen ejecutivo

| Concepto | Monto |
|---|---|
| **Desarrollo (única vez)** | **$540 USD** |
| **Costo por minuto (Telnyx + ElevenLabs)** | **$0.1045 USD/min** |
| **Costo por llamada promedio 4 min (Telnyx)** | **$0.418 USD** |
| Plataforma ElevenLabs Business | $825 USD/mes |
| Infraestructura mensual — 100 llamadas/día | ~$2,079 USD/mes |
| Infraestructura mensual — 1,000 llamadas/día | ~$13,365 USD/mes |
| **Tiempo de entrega** | **9 días hábiles** |

### Proveedores SIP comparados

| Proveedor | MX Móvil/min | DID/mes | Setup | Ventaja principal |
|---|---|---|---|---|
| **Telnyx** *(recomendado)* | $0.0045 | $1.00 | $0 | Más barato, API moderna, Caller ID flexible |
| Vonage | $0.0270 | $0.90 | $0 | Buena cobertura, API estable |
| Twilio | $0.0400 | $1.15 | $0 | Integración nativa con ElevenLabs, mejor documentación |

---

<!-- Las siguientes cotizaciones se agregarán aquí al ser aceptadas -->

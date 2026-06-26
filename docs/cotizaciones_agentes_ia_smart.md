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

---

## Cotización #2 — SIP Trunk Propio (Self-Hosted)

### Variación respecto a Cotización #1

En lugar de pagar a Telnyx/Vonage/Twilio por minuto, se monta infraestructura SIP propia conectada a un proveedor mayorista de terminación en México.

| Componente | Cotización #1 | Cotización #2 |
|---|---|---|
| Media server | Telnyx (incluido) | Asterisk / FreeSWITCH (propio) |
| Enrutamiento PSTN | Telnyx API | Configuración propia |
| Control de llamadas | TeXML/API REST | AGI/ARI de Asterisk |
| Failover | Automático (Telnyx) | Manual / configurado |
| Números (DID) | Telnyx portal | Proveedor mayorista |
| Mantenimiento | Telnyx lo opera | Operación propia |
| Costo/min SIP | $0.0045 (retail) | $0.0010–0.0015 (mayorista) |

### Stack adicional necesario

| Componente | Software | Costo |
|---|---|---|
| SIP Server | Asterisk o FreeSWITCH | Open source ($0) |
| SIP Proxy (alta carga) | Kamailio | Open source ($0) |
| Servidor dedicado | VPS 4 cores / 8 GB RAM | $50–100 USD/mes |
| Proveedor mayorista México | Limecom / Telintel / ASOLTEL | Contrato + mínimo mensual |

### Proveedores mayoristas México

| Proveedor | Tarifa/min | Setup | Mínimo mensual |
|---|---|---|---|
| **Limecom** | ~$0.0010 | $200–300 USD | ~$100 USD |
| **Telintel** | ~$0.0012 | $200 USD | ~$100 USD |
| **ASOLTEL** | ~$0.0008–0.0015 | Variable | Variable |

### Costo por minuto — comparativa

| Componente | Cotización #1 (Telnyx) | Cotización #2 (SIP propio) |
|---|---|---|
| ElevenLabs | $0.1000/min | $0.1000/min |
| SIP / terminación | $0.0045/min | $0.0010/min |
| **Total/min** | **$0.1045** | **$0.1010** |
| **Ahorro/min** | — | **$0.0035** |

### Punto de equilibrio vs Cotización #1

| Volumen | Ahorro SIP/mes | Costo servidor | **Ahorro neto/mes** |
|---|---|---|---|
| 100 llamadas/día (12K min) | $42 | $75 | **-$33** (pierde) |
| 500 llamadas/día (60K min) | $210 | $75 | **+$135** |
| 1,000 llamadas/día (120K min) | $420 | $75 | **+$345** |
| 5,000 llamadas/día (600K min) | $2,100 | $150 | **+$1,950** |

> El punto de equilibrio está en ~**400 llamadas/día**. Por debajo, Telnyx es más económico.

### Costo de desarrollo

| Concepto | Horas | Tarifa | Total |
|---|---|---|---|
| Base Cotización #1 | 72 h | $7.50/h | $540 |
| Asterisk + integración AGI/ARI | 36 h | $7.50/h | $270 |
| Configuración trunk mayorista + QA | 8 h | $7.50/h | $60 |
| **Total desarrollo (única vez)** | **116 h** | | **$870 USD** |

### Infraestructura mensual comparada

| Volumen | C#1 Telnyx | C#2 SIP Propio | Ahorro mensual |
|---|---|---|---|
| 100 llamadas/día | $2,079 | $2,121 | **-$42** |
| 500 llamadas/día | $7,095 | $6,960 | **+$135** |
| 1,000 llamadas/día | $13,365 | $13,020 | **+$345** |
| 5,000 llamadas/día | $63,525 | $61,575 | **+$1,950** |

### Pros y Contras

| ✅ Pros | ❌ Contras |
|---|---|
| Tarifa mayorista 4.5× más barata que Telnyx | Requiere operar y mantener Asterisk |
| Control total del enrutamiento y caller ID | Mayor tiempo de desarrollo (+5.5 días) |
| Sin dependencia de tercero para la telefonía | Contratos con mínimos mensuales |
| Escalable sin cambiar de proveedor | Failover manual si cae el servidor SIP |
| Número de WhatsApp como CLI sin verificación | Más puntos de falla en la arquitectura |
| Infraestructura reutilizable para otros proyectos | Requiere conocimiento SIP para operar |

### Resumen ejecutivo

| Concepto | Monto |
|---|---|
| **Desarrollo (única vez)** | **$870 USD** |
| **Costo por minuto (SIP propio + ElevenLabs)** | **$0.1010 USD/min** |
| **Costo por llamada promedio 4 min** | **$0.404 USD** |
| Servidor SIP | $75–150 USD/mes |
| Setup mayorista (única vez) | $200–300 USD |
| Infraestructura mensual — 1,000 llamadas/día | ~$13,020 USD/mes |
| **Tiempo de entrega** | **14.5 días hábiles** |
| **Punto de equilibrio vs Cotización #1** | **~400 llamadas/día** |

---

<!-- Cotización #3 se agregará aquí al ser aceptada -->

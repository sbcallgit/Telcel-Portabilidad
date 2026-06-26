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

## Cotización #3 — Agente de Voz Self-Hosted con NVIDIA Riva + LLM

### Concepto

Eliminar completamente ElevenLabs. El ASR (voz → texto), TTS (texto → voz) y el LLM corren en infraestructura propia con GPU NVIDIA. ElevenLabs pasa de ser un servicio a ser un costo operativo eliminado.

### Stack completo

| Componente | Tecnología | Propósito |
|---|---|---|
| **ASR** | NVIDIA Riva (Conformer-CTC español) | Transcribe audio del lead en tiempo real, streaming por palabras |
| **TTS** | NVIDIA Riva (FastPitch + HiFiGAN español) | Sintetiza voz de Vera con modelos locales |
| **LLM** | Claude Haiku (API) o NVIDIA NIM local | Genera respuestas conversacionales |
| **Orquestación** | Pipeline Python (gRPC ↔ Riva) | Loop en tiempo real ASR → LLM → TTS |
| **SIP** | Asterisk + trunk mayorista | Llamadas salientes a México (igual que C#2) |
| **Trigger** | FastAPI endpoint + Bitrix24 | Disparar llamada desde el deal |

### Flujo de audio en tiempo real

```
Lead habla
    ↓
Asterisk captura RTP
    ↓
Riva ASR (gRPC streaming) → texto parcial por palabras
    ↓
Detección fin de turno (VAD)
    ↓
Claude Haiku API → respuesta texto
    ↓
Riva TTS (gRPC streaming) → audio chunk por chunk
    ↓
Asterisk reproduce al lead
    ↓
(loop hasta fin de llamada)
```

### Costo de desarrollo

| Módulo | Días | Horas |
|---|---|---|
| NVIDIA Riva setup + configuración GPU | 1.5 | 12 |
| Modelos ASR español (descarga + tuning) | 1.0 | 8 |
| Modelos TTS español + voz personalizada Vera | 1.0 | 8 |
| Pipeline ASR streaming (gRPC) | 2.0 | 16 |
| Pipeline TTS streaming (gRPC) | 1.5 | 12 |
| Integración LLM (Claude Haiku) | 1.0 | 8 |
| Orquestación ASR → LLM → TTS en tiempo real | 2.0 | 16 |
| Asterisk + SIP trunk mayorista | 2.0 | 16 |
| FastAPI endpoint + trigger Bitrix24 | 0.5 | 4 |
| Contexto del lead al agente | 1.0 | 8 |
| Optimización de latencia (< 800ms E2E) | 1.0 | 8 |
| Testing QA end-to-end | 2.0 | 16 |
| **Total** | **17.5 días** | **132 h** |

| Concepto | Horas | Tarifa | Total |
|---|---|---|---|
| **Total desarrollo (única vez)** | **132 h** | **$7.50/h** | **$990 USD** |

### GPU requerida — opciones de infraestructura

#### Opción A — GPU en la nube (sin inversión inicial)

| Instancia | GPU | VRAM | Llamadas simultáneas | Costo/mes (reserved) |
|---|---|---|---|---|
| AWS G5.xlarge | A10G | 24 GB | ~20–30 | ~$360 |
| AWS G5.2xlarge | A10G | 24 GB | ~30–50 | ~$520 |
| AWS P3.2xlarge | V100 | 16 GB | ~15–25 | ~$720 |
| GCP A2 (A100 40GB) | A100 | 40 GB | ~80–120 | ~$1,200 |

> Para 1,000 llamadas/día el pico real simultáneo es ~15–20 llamadas. Una instancia G5.xlarge (~$360/mes) es suficiente.

#### Opción B — Hardware propio (inversión única)

| Hardware | VRAM | Llamadas simultáneas | Costo único | Servidor/mes |
|---|---|---|---|---|
| RTX 4090 | 24 GB | ~20–30 | $1,800 USD | $80 |
| A10G (enterprise) | 24 GB | ~30–50 | $3,500 USD | $80 |
| A100 40GB | 40 GB | ~80–120 | $12,000 USD | $100 |

### Costo por minuto — desglose

| Componente | Costo/min |
|---|---|
| Riva ASR (local) | $0 |
| Riva TTS (local) | $0 |
| Claude Haiku (~6K tokens/llamada) | ~$0.002 |
| SIP trunk mayorista (Limecom) | $0.001 |
| GPU amortizada (A10G cloud, 60K min/mes) | ~$0.006 |
| **Total/min** | **~$0.009** |

### Comparativa de costo por minuto — las 3 cotizaciones

| Cotización | Tecnología | Costo/min | Costo llamada 4 min |
|---|---|---|---|
| #1 ElevenLabs + Telnyx | Cloud | $0.1045 | $0.418 |
| #2 ElevenLabs + SIP propio | Cloud + SIP | $0.1010 | $0.404 |
| **#3 NVIDIA Riva self-hosted** | **Self-hosted** | **$0.009** | **$0.036** |

> Cotización #3 es ~11× más barata por minuto que las alternativas con ElevenLabs.

### Infraestructura mensual comparada (Opción A — GPU cloud G5.xlarge)

| Volumen | C#1 ElevenLabs | C#2 SIP propio | **C#3 NVIDIA** |
|---|---|---|---|
| 100 llamadas/día (12K min) | $2,079 | $2,121 | **$504** |
| 500 llamadas/día (60K min) | $7,095 | $6,960 | **$660** |
| 1,000 llamadas/día (120K min) | $13,365 | $13,020 | **$936** |
| 5,000 llamadas/día (600K min) | $63,525 | $61,575 | **$3,060** |

> A 1,000 llamadas/día C#3 cuesta ~$936/mes vs ~$13,365 de C#1 — ahorro de **$12,429/mes**.

### Punto de equilibrio vs C#1

Inversión extra vs C#1: $990 − $540 = **$450 USD adicionales**  
Ahorro mensual a 500 llamadas/día: $7,095 − $660 = **$6,435/mes**  
Recuperación de la inversión adicional: **< 3 días de operación**

### Pros y Contras

| ✅ Pros | ❌ Contras |
|---|---|
| 11× más barato por minuto que ElevenLabs | Requiere GPU NVIDIA (CUDA — no AMD sin cambiar stack) |
| Costo prácticamente fijo independiente del volumen | Mayor complejidad de desarrollo (+8.5 días vs C#1) |
| Voz 100% personalizable (entrenas la voz de Vera) | Requiere operar Riva, Asterisk y GPU |
| Sin costo por minuto de plataforma tercera | Latencia puede subir si GPU está saturada |
| Audio nunca sale de tu infraestructura (privacidad total) | Curva de aprendizaje para operar Riva en producción |
| Escalable horizontalmente agregando GPUs | |
| Reutilizable para cualquier otro proyecto de voz | |

### Resumen ejecutivo

| Concepto | Opción A (GPU cloud) | Opción B (hardware propio) |
|---|---|---|
| **Desarrollo (única vez)** | **$990 USD** | **$990 USD** |
| **Inversión hardware GPU** | $0 | $1,800–12,000 USD |
| **Costo por minuto** | **~$0.009** | **~$0.003** |
| **Costo llamada promedio 4 min** | **$0.036** | **$0.012** |
| Infraestructura mensual — 1,000 llamadas/día | **~$936** | **~$216** |
| Infraestructura mensual — 5,000 llamadas/día | **~$3,060** | **~$720** |
| **Tiempo de entrega** | **17.5 días hábiles** | **17.5 días hábiles** |
| GPU mínima requerida | AWS G5.xlarge | RTX 4090 / A10G |

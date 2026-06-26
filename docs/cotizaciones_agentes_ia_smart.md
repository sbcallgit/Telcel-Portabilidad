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

### Escalabilidad horizontal de C#3

Una sola GPU A10G (24 GB) soporta ~20–30 llamadas simultáneas. Para escalar más allá de ese umbral se requiere orquestación multi-instancia.

#### Capacidad por instancia GPU

| GPU | VRAM | Llamadas simultáneas | Costo cloud/mes |
|---|---|---|---|
| A10G (24 GB) | 24 GB | 20–30 | $360 |
| A100 (40 GB) | 40 GB | 80–120 | $1,200 |
| H100 (80 GB) | 80 GB | 200–300 | $2,800 |

#### Llamadas simultáneas en pico por volumen diario

> Fórmula: `(llamadas/día × duración_promedio_min) ÷ (horas_operación × 60)`  
> Ejemplo: 1,000 llamadas × 4 min ÷ (8h × 60) = **~8 simultáneas promedio**, pico 2× = **~16**

| Volumen | Pico simultáneo | GPUs A10G necesarias | Costo GPU/mes |
|---|---|---|---|
| 500 llamadas/día | ~8 | 1 | $360 |
| 1,000 llamadas/día | ~16 | 1 | $360 |
| 3,000 llamadas/día | ~50 | 2 | $720 |
| 5,000 llamadas/día | ~83 | 3–4 | $1,080–1,440 |
| 10,000 llamadas/día | ~166 | 6–8 | $2,160–2,880 |

#### Arquitectura de escalabilidad horizontal (desarrollo adicional)

Para escalar más allá de 1 GPU se requiere:

| Componente | Tecnología | Propósito |
|---|---|---|
| Orquestador de contenedores | Kubernetes (EKS/GKE) | Auto-scaling de pods Riva + Asterisk |
| GPU node pool | AWS G5 / GCP A2 autoscaling | Suma/resta GPUs según carga |
| Load balancer SIP | Kamailio | Distribuye llamadas entre instancias Asterisk |
| Health checks | Prometheus + Grafana | Monitoreo de ocupación GPU y latencia |
| Cola de llamadas | Redis + arq | Buffer cuando todos los slots están ocupados |

**Costo de desarrollo adicional para arquitectura escalable:**

| Módulo | Días | Horas | Costo |
|---|---|---|---|
| Kubernetes + GPU node pool | 2.0 | 16 | $120 |
| Load balancer SIP (Kamailio) | 1.5 | 12 | $90 |
| Monitoreo GPU + alertas | 1.0 | 8 | $60 |
| Cola de llamadas + retry | 1.0 | 8 | $60 |
| **Total adicional** | **5.5 días** | **44 h** | **$330 USD** |

> Con este módulo adicional, C#3 pasa de escala fija a escala ilimitada horizontal, con costo lineal en GPU cloud conforme crece el volumen.

#### Infraestructura mensual con escalabilidad horizontal (C#3)

| Volumen | GPUs | GPU cloud/mes | SIP mayorista | LLM Haiku | **Total/mes** |
|---|---|---|---|---|---|
| 500 llamadas/día | 1× A10G | $360 | $36 | $120 | **$516** |
| 1,000 llamadas/día | 1× A10G | $360 | $72 | $240 | **$672** |
| 3,000 llamadas/día | 2× A10G | $720 | $216 | $720 | **$1,656** |
| 5,000 llamadas/día | 4× A10G | $1,440 | $360 | $1,200 | **$3,000** |
| 10,000 llamadas/día | 8× A10G | $2,880 | $720 | $2,400 | **$6,000** |

> A 10,000 llamadas/día C#3 escalable cuesta **$6,000/mes** vs **$133,650/mes** de C#1. Ahorro: **$127,650/mes**.

---

## Cotización #4 — Agente de Voz Self-Hosted con AMD ROCm

### Concepto

Misma arquitectura self-hosted que C#3 pero con GPU AMD en lugar de NVIDIA. El stack ASR/TTS cambia porque NVIDIA Riva requiere CUDA — se usa `faster-whisper` (ASR) + Coqui XTTS (TTS) + Ollama (LLM local), todos compatibles con ROCm.

**Ventaja principal:** una RX 7900 XTX cuesta ~$800 USD vs ~$1,800 de una RTX 4090 — **55% menos en hardware**.

### Stack completo

| Componente | C#3 NVIDIA | C#4 AMD |
|---|---|---|
| ASR | NVIDIA Riva (Conformer-CTC) | faster-whisper (Whisper large-v3) |
| TTS | NVIDIA Riva (FastPitch + HiFiGAN) | Coqui XTTS-v2 |
| LLM | Claude Haiku (API) | Ollama (Llama 3.1 8B) — local, $0 |
| GPU requerida | NVIDIA CUDA | AMD ROCm (RX 7900 XTX / MI250) |
| Protocolo ASR/TTS | gRPC streaming | HTTP / WebSocket streaming |
| SIP | Asterisk + trunk mayorista | Asterisk + trunk mayorista (igual) |

### Diferencias técnicas clave

| Aspecto | C#3 NVIDIA Riva | C#4 AMD ROCm |
|---|---|---|
| Latencia ASR | ~150–250ms | ~200–350ms (Whisper no es streaming nativo) |
| Latencia TTS | ~100–200ms | ~300–500ms (Coqui más lento que Riva) |
| Latencia E2E estimada | 600–800ms | 900–1,200ms |
| Calidad de voz | Alta (modelos Riva entrenados) | Muy alta (XTTS con clonación de voz) |
| Voz personalizada Vera | Requiere fine-tuning Riva | Clonación en 6 segundos de audio (XTTS) |
| Ecosistema | Maduro, soporte NVIDIA | En crecimiento, menos documentación |
| LLM local incluido | No (Claude API) | Sí (Ollama Llama 3.1 8B) |

### GPU requerida — hardware AMD propio

| Hardware | VRAM | Llamadas simultáneas | Costo único | ROCm soporte |
|---|---|---|---|---|
| **RX 7900 XTX** *(recomendado)* | 24 GB | ~15–20 | $800 USD | ✅ Estable |
| RX 7900 XT | 20 GB | ~12–16 | $650 USD | ✅ Estable |
| MI250 (enterprise) | 128 GB | ~100–150 | $8,000 USD | ✅ Maduro |
| RX 6900 XT | 16 GB | ~8–12 | $400 USD | ⚠️ Parcial |

> AMD no ofrece instancias GPU en cloud comparables al precio de AWS G5. La ventaja de AMD es el **hardware propio** a menor costo.

### Costo de desarrollo

| Módulo | Días | Horas |
|---|---|---|
| AMD ROCm setup + Docker con PyTorch ROCm | 2.0 | 16 |
| faster-whisper en ROCm + pipeline ASR streaming | 2.0 | 16 |
| Coqui XTTS-v2 en ROCm + clonación de voz Vera | 2.0 | 16 |
| Ollama + Llama 3.1 8B en español (fine-tuning/quantización) | 2.5 | 20 |
| Orquestación ASR → LLM → TTS en tiempo real | 2.0 | 16 |
| Asterisk + SIP trunk mayorista | 2.0 | 16 |
| FastAPI endpoint + trigger Bitrix24 | 0.5 | 4 |
| Contexto del lead al agente | 1.0 | 8 |
| Optimización latencia (ROCm más impredecible que CUDA) | 2.0 | 16 |
| Testing QA end-to-end | 2.0 | 16 |
| **Total** | **20 días** | **144 h** |

| Concepto | Horas | Tarifa | Total |
|---|---|---|---|
| **Total desarrollo (única vez)** | **144 h** | **$7.50/h** | **$1,080 USD** |

### Costo por minuto — desglose

| Componente | C#3 NVIDIA | C#4 AMD |
|---|---|---|
| ASR (faster-whisper local) | $0 | $0 |
| TTS (Coqui XTTS local) | $0 | $0 |
| LLM (Claude Haiku API) | ~$0.002 | $0 (Ollama local) |
| SIP trunk mayorista | $0.001 | $0.001 |
| GPU amortizada (hardware propio, 36 meses) | ~$0.002 | ~$0.001 |
| Servidor/electricidad | ~$0.002 | ~$0.002 |
| **Total/min** | **~$0.007** | **~$0.004** |

### Comparativa completa de las 4 cotizaciones

| Cotización | Stack | Desarrollo | Costo/min | Llamada 4 min | 1K llamadas/día/mes |
|---|---|---|---|---|---|
| #1 ElevenLabs + Telnyx | Cloud | $540 / 9 días | $0.1045 | $0.418 | $13,365 |
| #2 ElevenLabs + SIP propio | Cloud + SIP | $870 / 14.5 días | $0.1010 | $0.404 | $13,020 |
| #3 NVIDIA Riva self-hosted | CUDA GPU | $990 / 17.5 días | $0.009 | $0.036 | $936 |
| **#4 AMD ROCm self-hosted** | **ROCm GPU** | **$1,080 / 20 días** | **$0.004** | **$0.016** | **$504** |

> C#4 es la opción más barata por minuto gracias a LLM local (Ollama). Hardware ~55% más barato que NVIDIA para misma VRAM.

### Inversión en hardware + recuperación

| Hardware | Costo único | Ahorro vs C#1 (1K llamadas/día) | Recuperación |
|---|---|---|---|
| RX 7900 XTX ($800) + servidor ($500) | $1,300 | $12,861/mes | **< 2 días** |
| RTX 4090 ($1,800) + servidor ($500) | $2,300 | $12,429/mes | **< 6 días** |

### Pros y Contras

| ✅ Pros | ❌ Contras |
|---|---|
| Hardware 55% más barato que NVIDIA | Latencia E2E mayor (~1,000ms vs ~700ms de C#3) |
| LLM local incluido (Ollama) — $0 por llamada | ROCm menos maduro que CUDA, más bugs |
| Costo por minuto más bajo de todas las opciones | Menos documentación y comunidad que NVIDIA |
| Clonación de voz Vera en segundos (XTTS) | Fine-tuning del LLM local requiere validación en español |
| Sin dependencia de ninguna API externa | Mayor tiempo de desarrollo (+2.5 días vs C#3) |
| Escalable agregando más GPUs AMD | Llama 3.1 8B puede ser menos preciso que Claude en objeciones complejas |

### Resumen ejecutivo

| Concepto | Monto |
|---|---|
| **Desarrollo (única vez)** | **$1,080 USD** |
| **Hardware GPU (RX 7900 XTX + servidor)** | **$1,300 USD** |
| **Costo por minuto (totalmente self-hosted)** | **~$0.004 USD/min** |
| **Costo llamada promedio 4 min** | **~$0.016 USD** |
| Infraestructura mensual — 1,000 llamadas/día | **~$504 USD** |
| Infraestructura mensual — 5,000 llamadas/día | **~$1,560 USD** |
| **Tiempo de entrega** | **20 días hábiles** |
| GPU recomendada | RX 7900 XTX (24 GB VRAM) |

---

## Tabla resumen — las 4 cotizaciones

| | C#1 | C#2 | C#3 | C#4 |
|---|---|---|---|---|
| **Stack** | ElevenLabs + Telnyx | ElevenLabs + SIP propio | NVIDIA Riva + Claude Haiku | AMD ROCm + Ollama local |
| **Desarrollo** | $540 | $870 | $990 | $1,080 |
| **Tiempo entrega** | 9 días | 14.5 días | 17.5 días | 20 días |
| **Costo/min** | $0.1045 | $0.1010 | $0.009 | $0.004 |
| **Llamada 4 min** | $0.418 | $0.404 | $0.036 | $0.016 |
| **1K llamadas/día/mes** | $13,365 | $13,020 | $936 | $504 |
| **5K llamadas/día/mes** | $63,525 | $61,575 | $3,000* | $1,560 |
| **Dependencias externas** | ElevenLabs + Telnyx | ElevenLabs + mayorista | Claude API + mayorista | Solo mayorista SIP |
| **Complejidad operativa** | Baja | Media | Alta | Muy alta |
| **Escalabilidad** | Ilimitada (cloud) | Ilimitada (cloud) | Horizontal (GPUs) | Horizontal (GPUs) |
| **Latencia estimada** | ~400ms | ~400ms | ~700ms | ~1,000ms |

*C#3 a 5K llamadas/día requiere 4× GPU A10G (~$1,440 cloud) + SIP + LLM.

**Cuándo elegir cada una:**

| Si... | Elige |
|---|---|
| Necesitas arrancar en < 2 semanas y el volumen es bajo | **C#1** |
| Ya tienes > 400 llamadas/día y quieres reducir SIP | **C#2** |
| El volumen justifica self-hosted y tienes operador DevOps | **C#3** |
| Quieres máximo ahorro, no importa la latencia +300ms extra | **C#4** |
| El volumen crece a 3,000+ llamadas/día | **C#3 + escalabilidad horizontal** |

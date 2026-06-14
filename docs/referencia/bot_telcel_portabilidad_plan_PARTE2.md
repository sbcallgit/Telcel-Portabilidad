# BOT Telcel Portabilidad — Plan de trabajo

## Campaña Muévete Prepago · Región 4 — **PARTE 2 de 2**

**Esta Parte 2 cubre:** Día 3 (Agente de venta con LangGraph), Día 4 (Seguimientos automáticos y jobs), Día 5 (Flujos restantes y endurecimiento) y Días 6–7 (Piloto controlado y salida a producción). **La Parte 1 cubrió:** Día 1 (Cimientos) y Día 2 (Integraciones y base de conocimiento).

🔎 **Esta parte está aterrizada en los reportes de QA reales del proyecto.** El bot actual ya pasó por dos rondas de auditoría y un mystery shopper, que documentaron **40 errores y 13 patrones sistémicos**. Cada vez que un paso de este plan existe específicamente para no repetir un defecto conocido, lo marco con un callout **🔎 Aprendido de la auditoría**. La causa de fondo de la mayoría de esos defectos es que el bot actual funciona con **plantillas rígidas y reglas por palabra clave**; el diseño LangGraph \+ Claude de aquí los resuelve de raíz al ser genuinamente conversacional.

---

# Día 3: Agente de venta (LangGraph)

El Día 3 es el más complejo: construimos el agente de IA con LangGraph. Este agente sigue el embudo de la campaña — **valida la región por LADA → sondea → clasifica → presenta la promo → rebate objeciones → captura datos → escala al asesor humano** — y mantiene el contexto de toda la conversación.

El agente recibe mensajes de WhatsApp (leads que llegan de Meta Ads), entiende en qué etapa va, responde de forma natural y sabe exactamente cuándo escalar. El NIP y la validación de equipo los hace el **asesor humano en llamada** (el NIP es dato sensible y nunca se pide por WhatsApp).

**Regla de oro del agente (de las reglas de conversación):** mensajes cortos y cálidos, máximo 3 líneas, **una sola pregunta por mensaje**, tono humano nunca robótico, no inventar precios ni vigencias, y **cerrar siempre con una pregunta o un siguiente paso claro**.

## 3.1 Estado del agente — agents/portabilidad/state.py

**¿Qué es?** El estado es la "memoria de trabajo" del agente: todo lo que sabe en un momento dado sobre una conversación. En LangGraph, cada nodo lee el estado, lo modifica y pasa la versión actualizada al siguiente nodo.

**¿Por qué?** Sin un estado bien definido, la información se pierde entre pasos. Con un `TypedDict` claro, todos los nodos saben exactamente qué tienen disponible y qué pueden modificar.

**¿Cómo?**

1. Crear `agents/portabilidad/state.py`.  
2. Definir `PortabilidadState` como `TypedDict`.  
3. Campos:

| Campo | Para qué |
| :---- | :---- |
| `session_id` | Identifica la conversación |
| `messages` | Historial (usa `Annotated[list, add_messages]`) |
| `customer_phone` | Teléfono de WhatsApp del lead |
| `etapa` | `validacion`, `sondeo`, `oferta`, `objecion`, `cierre`, `escalado`, `fin` |
| `lada`, `ciudad`, `region_habilitada` | Resultado de la validación de LADA |
| `datos_lead` | nombre, número a portar, compañía donante, municipio, recarga habitual, uso predominante |
| `temperatura` | `caliente` / `tibio` / `frío` (clasificación interna) |
| `promo_elegida` | La promo presentada/aceptada |
| `objeciones_rebatidas` | Contador — para la regla de "rebatir hasta 3 veces" |
| `intentos_sin_avance` | Para detectar loops y activar salida/escalamiento |
| `escalate_to_human`, `motivo_escalacion` | Banderas de escalamiento |
| `bitrix_lead_id`, `bitrix_etapa` | Vínculo con el lead en Bitrix |

**¿Qué es TypedDict?** Un diccionario Python donde declaras de antemano qué campos tiene y de qué tipo son. Python te avisa si intentas usar un campo que no existe.

## 3.2 Nodo de validación de NIR/LADA — nodes/validacion.py

**¿Qué es?** El primer filtro operativo. Toma el número de 10 dígitos del cliente, detecta su LADA y consulta la tabla de LADAs (Día 2\) para decidir si la zona está habilitada para portabilidad digital o si hay que derivar a un CAC presencial.

**¿Por qué?** Es la regla comercial número uno: **no presentar promo sin validar la región**. Operar leads de ciudades no habilitadas genera trámites imposibles y desperdicia la inversión en pauta.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/validacion.py`.  
2. Extraer la LADA del número y consultar la tabla `ladas`.  
3. Si la ciudad está habilitada → continuar el flujo. Si no → mensaje claro y derivación a CAC presencial; tipificar en Bitrix como "no pertenece a la región".  
4. **Re-validar siempre que el cliente corrija su número o su LADA.**  
5. **Validar el input:** si llega un emoji, signos o letras al azar, NO interpretarlo como número; pedir el número con amabilidad.  
6. Si el cliente pregunta directo "¿la LADA 873 aplica?", responder SÍ/NO según la tabla y luego pedir el número.

🔎 **Aprendido de la auditoría:** el bot actual (a) ignora cuando el cliente corrige su número y deja de re-validar la LADA, procesando trámites imposibles (Hallazgos \#4 y \#5); (b) trata un emoji como si fuera el número e inventa "Gracias por 8112345678" (Hallazgo \#9, patrón \#5); y (c) evade la pregunta directa "¿aplica la LADA 873?" pidiendo el número en lugar de responder (Hallazgo \#12). Los pasos 4, 5 y 6 existen para corregir exactamente eso.

## 3.3 Nodo de sondeo — nodes/sondeo.py

**¿Qué es?** El nodo que conoce al cliente: cuánto recarga, qué usa más (redes, llamadas, streaming), qué necesita. Sirve para personalizar la oferta y calificar al lead.

**¿Por qué?** Sin sondeo, el bot ofrece lo mismo a todos y trata las objeciones a ciegas. Con sondeo, presenta la promo correcta y rebate con argumentos que sí le hacen sentido al cliente.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/sondeo.py`.  
2. Preguntar de a una: "¿Cuánto recargas normalmente?", luego "¿Qué usas más, redes o llamadas?", luego "¿Usas mucho internet?".  
3. Usar Claude para interpretar respuestas naturales ("como 200 pesos" → 200).  
4. **Responder las preguntas de información general (promos, tarifas, horarios, CACs, beneficios) SIN exigir el número primero.** El número solo se pide cuando se va a activar/avanzar, no como requisito para informar.

🔎 **Aprendido de la auditoría — el bug más grave (patrón \#1):** el bot actual exige el número de 10 dígitos antes de responder casi cualquier pregunta comercial ("¿qué incluye la promo de 100?", "¿cuándo me llega señal?", "¿cuánto da Claro Drive?"), bloqueando el flujo de sondeo→oferta (Hallazgos \#3, \#14, \#15, \#16). La meta de QA es **≥80% de preguntas comerciales respondidas sin pedir número primero**. Califica la necesidad *antes* de tratar objeciones (Mystery Shopper H-01).

## 3.4 Nodo de clasificación del lead — nodes/clasificacion.py

**¿Qué es?** Etiqueta internamente cada lead como **caliente** (quiere portarse ya, manda su número, pregunta por el CAC), **tibio** (pregunta precio/beneficios) o **frío** ("info", "luego veo").

**¿Por qué?** Permite priorizar: un lead caliente se cierra y escala rápido; uno frío recibe una pregunta de enganche y entra a seguimiento. Así no se trata igual a quien está listo que a quien apenas explora.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/clasificacion.py`.  
2. Usar Claude para asignar la temperatura según las señales del mensaje y el historial.  
3. Guardar la temperatura en el estado y reflejarla en la etapa de Bitrix.  
4. Lead caliente → ruta rápida a cierre/escalamiento.

## 3.5 Nodo de oferta — nodes/oferta.py

**¿Qué es?** Presenta la promo que mejor le encaja al cliente según su recarga, tomando los datos de la tabla `promos` (Día 2).

**¿Por qué?** Es donde se construye el valor. Una oferta personalizada y con un llamado a la acción claro convierte; una genérica se pierde.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/oferta.py`.  
2. Mapear recarga → promo: $50 → Sin Recarga Inicial $50; $100 → Portabilidad Plus **o** Sin Recarga Inicial $100; $150+ → Portabilidad Plus Plus (8 GB).  
3. Cuando una recarga tiene **dos opciones** (el caso de $100), presentar ambas y dejar elegir.  
4. Leer beneficios, vigencia y condiciones de la base de conocimiento — **nunca inventarlos**.  
5. **Cerrar siempre con un CTA** ("¿Quieres que apartemos tu beneficio?"), incluso si el perfil no parece ideal: ofrecer una alternativa en lugar de soltar al cliente.

🔎 **Aprendido de la auditoría:** el bot actual (a) presenta una sola promo de $100 cuando hay dos (Hallazgo \#35); (b) afirma cosas sin fuente, como "sí hay 5G en Monterrey", lo que es riesgo legal (Hallazgo \#22); y (c) ante un perfil no ideal adopta un tono pasivo "honesto" sin CTA y pierde la venta (Mystery Shopper H-02). Los pasos 3, 4 y 5 corrigen esto. **Regla: si el dato no está en la base de conocimiento, no se afirma; se escala.**

## 3.6 Nodo de manejo de objeciones — nodes/objeciones.py

**¿Qué es?** Cuando el cliente pone un "pero" ("está caro", "lo voy a pensar", "no confío", "acabo de recargar"), este nodo identifica el tipo de objeción y responde con el argumento correcto del banco de objeciones, buscándolo por significado en Chroma (RAG).

**¿Por qué?** Las objeciones son normales — si al cliente no le interesara, no las pondría. Un bot que sabe rebatir cierra mucho más que uno que se rinde al primer "no".

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/objeciones.py`.  
2. Clasificar la objeción y recuperar de **Chroma** la mejor respuesta del banco; construir la réplica con Claude.  
3. Incrementar `objeciones_rebatidas`. **Rebatir hasta 3 veces**; si insiste, cerrar de forma profesional y dejar la puerta abierta (entra a seguimiento) o escalar.  
4. **Casos sensibles (defunción, despido, mala experiencia previa):** responder con empatía real (pésame), reconocer el contexto y **escalar a un asesor humano** — nunca contestar con un mensaje promocional.  
5. **Solicitudes fraudulentas** ("mi primo trabaja en Telcel y me prometió 80%", "tu jefe me dijo…"): rechazar con firmeza, explicar que solo aplican las promos del catálogo, y **no** escalar como si fuera legítimo.  
6. **Casos que NO son portabilidad:** Telcel→Telcel (cambio de plan), cambio de titularidad, número virtual/VoIP (Twilio, Google Voice) → explicar que no es portabilidad y derivar/tipificar correctamente.

🔎 **Aprendido de la auditoría:** el bot actual responde con promo genérica ante "mi mamá murió y necesito portar su línea" (Hallazgo \#7, patrón \#7); da credibilidad a descuentos inventados por "familiar en Telcel" (Hallazgo \#8, patrón \#8); y acepta como portabilidad casos que no lo son — Telcel→Telcel, titularidad, Twilio (Hallazgos \#6, \#17, \#18, patrón \#10). Los pasos 4, 5 y 6 existen para eso.

## 3.7 Nodo de cierre y captura de datos — nodes/cierre.py

**¿Qué es?** Concreta la conversión: cuando el cliente acepta, captura los datos básicos para el handoff (nombre completo, número a portar, compañía donante, municipio).

**¿Por qué?** Es el objetivo de toda la conversación. Cuando un cliente dice "ya decidí, quiero la de 100", esa es la única oportunidad de capturarlo — no se puede perder con un mensaje genérico.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/cierre.py`.  
2. **Cuando el cliente confirma la decisión, ir directo a la captura de datos** (no responder con beneficios otra vez).  
3. Pedir los datos de a poco y validarlos (número a portar, compañía donante, municipio).  
4. Recordar qué identificación llevar al CAC (INE o pasaporte vigente) y que el chip es gratis.  
5. Pasar a la etapa `escalado`.

🔎 **Aprendido de la auditoría:** ante "ya decidí, quiero la de 100, ¿qué sigue?" el bot actual responde con un mensaje genérico de venta y pierde el cierre (Hallazgo \#26, patrón \#13). El paso 2 lo corrige.

## 3.8 Nodo de escalamiento — nodes/escalate.py

**¿Qué es?** Transfiere la conversación a un asesor humano (en Chatwoot) con todo el contexto, y actualiza Bitrix. El asesor es quien gestiona el NIP en llamada y valida el equipo.

**¿Por qué?** El handoff es el momento más valioso del embudo. Si el asesor recibe al cliente sin contexto, el cliente tiene que repetir todo y se pierde la venta.

**¿Cómo?**

1. Crear `agents/portabilidad/nodes/escalate.py`.  
2. Disparar el escalamiento según los triggers: el cliente quiere portarse y es de R4, pide un asesor, se molesta, objeción fuerte, o equipo que requiere validación de IMEI.  
3. Crear la conversación en Chatwoot y mover la etapa en Bitrix, **pasando el contexto completo**: nombre, número a portar, compañía donante, municipio y promo elegida.  
4. Avisar al cliente con un mensaje que prepare la transición ("te conecto con un asesor que continúa el proceso, incluyendo tu NIP").  
5. **Nunca** pedir ni procesar el NIP por WhatsApp.

🔎 **Aprendido de la auditoría / mystery shopper:** la transferencia actual manda al cliente a un "Canal Abierto" sin contexto y el cliente repite todo (Mystery Shopper H-04). El paso 3 (handoff con contexto completo) lo resuelve.

## 3.9 Memoria, anti-reinicio y variabilidad

**¿Qué es?** Tres comportamientos que hacen que el agente se sienta humano y continuo: memoria de la conversación, no reiniciarse a media charla, y no repetir el mismo texto literal.

**¿Por qué?** Un bot que olvida el contexto, que saluda "Hola 👋" en medio de la conversación o que repite la misma frase siete veces se percibe roto y espanta al cliente.

**¿Cómo?**

1. **Memoria:** corto plazo en Redis (TTL 24 h) y largo plazo en PostgreSQL. LangGraph la maneja con el **checkpointer**; el `thread_id` es el teléfono del cliente.  
2. **Anti-reinicio:** el saludo de apertura solo se usa en el primer turno. Nunca reiniciar el flujo ni volver a saludar en una conversación activa.  
3. **Variabilidad:** dejar que Claude genere la respuesta (no plantillas fijas); nunca enviar el mismo texto literal en turnos consecutivos.  
4. **Detección de loops/frustración:** si el cliente dice "no puedo", "no me deja", "no funciona", o si `intentos_sin_avance` ≥ 2, ofrecer una ruta alternativa o escalar — no repetir la misma instrucción.

🔎 **Aprendido de la auditoría / mystery shopper:** el bot actual reinicia con "Hola 👋" a media conversación perdiendo contexto (Hallazgo \#11, patrón \#4); repite el mismo mensaje idéntico hasta 7 veces (Hallazgo \#13, patrón \#2); y entra en loop cuando el cliente dice "no me deja", repitiendo la misma guía sin salida (Mystery Shopper H-03). Los pasos 2, 3 y 4 atacan estos tres.

## 3.10 Grafo LangGraph — agents/portabilidad/graph.py

**¿Qué es?** El grafo conecta todos los nodos y define el flujo: qué nodo va primero, qué decisiones se toman y qué caminos puede seguir la conversación.

**¿Por qué?** El grafo es el "director" del agente. Sin él los nodos existen pero no saben en qué orden correr ni qué condiciones determinan el camino.

**¿Cómo?**

1. Crear `agents/portabilidad/graph.py`.  
2. Instanciar `StateGraph` con `PortabilidadState`.  
3. Agregar los nodos: `validacion`, `sondeo`, `clasificacion`, `oferta`, `objeciones`, `cierre`, `escalate`.  
4. **Entry point:** `validacion` (siempre se valida la región primero).  
5. **Conditional edges** que siguen el embudo: validación → sondeo → clasificación → oferta → (objeciones ⇄ cierre) → escalate → END. Desde cualquier punto, una objeción va a `objeciones`; un trigger de escalamiento va a `escalate`.  
6. Compilar con el checkpointer configurado.

## 3.11 Webhook de entrada con cola de mensajes — api/routes/webhooks.py ⭐

**¿Qué es?** El endpoint que recibe los mensajes de WhatsApp (de leads que llegaron por Meta Ads). En lugar de procesar el mensaje al vuelo, lo mete a una **cola** y un worker lo procesa.

**¿Por qué?** WhatsApp espera respuesta en menos de \~5 segundos o asume que falló y reintenta; por eso respondemos 200 de inmediato. Pero si solo lanzamos una tarea en background y el proceso se reinicia a mitad, **ese mensaje se pierde en silencio**. Con una cola (Redis \+ `arq`), el mensaje queda guardado hasta que un worker lo procesa con éxito — garantía de "al menos una vez".

**¿Cómo?**

1. Crear `api/routes/webhooks.py`.  
2. `POST /webhooks/telcel` valida la firma del webhook (Día 2).  
3. Responde **200 inmediatamente** — antes de procesar nada.  
4. **Encola** el mensaje en Redis con `arq` (no `asyncio.create_task` suelto).  
5. Un **worker** toma el mensaje, corre el grafo del agente y responde por WhatsApp.  
6. Si el worker falla, el mensaje se reintenta; si agota reintentos, va a la cola de fallidos (Día 4).

pip install arq

curl \-X POST http://localhost:8000/webhooks/telcel \-d '{"test": true}'

## Checklist de fin del Día 3

| ✓ | ¿Qué verificar? | Cómo verificarlo |
| :---- | :---- | :---- |
| \[ \] | El grafo recorre el embudo completo | Conversación: validación → sondeo → oferta → objeción → cierre → escalamiento |
| \[ \] | Responde preguntas comerciales sin exigir el número | Preguntar promos/tarifas/CACs sin dar número y verificar que responde |
| \[ \] | Re-valida la LADA cuando el cliente corrige su número | Dar 811, luego corregir a 871 (Torreón) → debe derivar a CAC |
| \[ \] | Maneja con empatía un caso sensible | Mencionar una defunción → pésame \+ escalamiento, nunca promo |
| \[ \] | Rechaza solicitudes fraudulentas | "mi primo me prometió 80%" → rechazo firme, sin escalar |
| \[ \] | No reinicia ni repite texto idéntico | Conversación larga sin "Hola 👋" a media charla ni frases repetidas |
| \[ \] | Ningún mensaje se pierde si se reinicia el worker | Reiniciar el worker a media conversación y ver que el mensaje se procesa |

---

# Día 4: Seguimientos automáticos y jobs

El Día 4 construimos los **seguimientos automáticos** (recuperar leads que no respondieron o que se enfriaron) y las **automatizaciones por SLA de Bitrix**. En la campaña, recuperar leads es dinero directo: cada lead llegó pagando pauta de Meta Ads.

**Cuidado con dos cosas:** que los seguimientos corran a la **hora correcta** (zona horaria de Monterrey) y que respeten el horario de portabilidad (L-S 9am–9pm, sin domingos) para no escribir a deshoras.

## 4.1 Scheduler de seguimientos — jobs/seguimientos.py

**¿Qué es?** El código Python que programa y ejecuta los seguimientos a horas específicas. APScheduler es la librería que lo hace.

**¿Por qué?** Necesitamos manejo de errores sólido y la garantía de que cada seguimiento corre cuando debe y una sola vez.

**¿Cómo?**

1. Instalar APScheduler: `pip install apscheduler pytz`.  
2. Crear `jobs/seguimientos.py`.  
3. Instanciar `AsyncIOScheduler` con `timezone='America/Monterrey'` explícito.  
4. Configurar `max_instances=1` para que no corra en paralelo si se atrasa.  
5. Arrancar el scheduler al iniciar la aplicación.

pip install apscheduler pytz

## 4.2 La cadencia de seguimientos por etapa

**¿Qué es?** La secuencia exacta de mensajes de recuperación, distinta según en qué etapa se detuvo el lead.

**¿Por qué?** Un seguimiento genérico para todos rinde poco. Uno que retoma justo donde el cliente se quedó ("¿pudiste pensar la promo?", "¿cuánto recargas, $50 o $100?") recupera muchos más.

**¿Cómo?** Programar la cadencia que ya está definida en la especificación:

| Etapa donde se detuvo | Cadencia de seguimientos |
| :---- | :---- |
| No respondió al primer mensaje | 5 min · 30 min · 2 h · antes de 24 h |
| Dio número pero no terminó el sondeo | 5 min · 30 min · 2 h · antes de 24 h |
| Recibió la oferta y no respondió | 5 min · 30 min · 2 h · antes de 24 h |
| Dijo "lo voy a pensar" | 30 min · 2 h · antes de 24 h · día 2 |
| Mostró intención alta y se enfrió | 5 min · 30 min · 2 h · antes de 24 h |

Reglas: **máximo 5 seguimientos por lead**, nunca repetir el mismo texto, reiniciar el flujo si el cliente responde, y **detener** si dice "no me interesa". Cada abandono se tipifica en Bitrix.

## 4.3 Automatizaciones de SLA en Bitrix

**¿Qué es?** Las reglas del pipeline operativo que mueven leads solos: 24 h sin "Venta Exitosa" → **Recuperación**; 72 h sin "Venta Exitosa" → **Caído** (tipificado "sin respuesta del cliente").

**¿Por qué?** Sin estas automatizaciones, los leads se estancan en una etapa y nadie los retoma ni los cierra. El SLA obliga al sistema a actuar.

**¿Cómo?**

1. Decidir dónde viven: como **automatizaciones nativas de Bitrix** (preferible, ya que es su pipeline) o como jobs de nuestro sistema que consultan tiempos y mueven la etapa.  
2. Si las maneja nuestro sistema, programarlas con APScheduler y hacerlas **idempotentes** (ver 4.4).  
3. En ambos casos, el bot escribe la etapa y la tipificación que disparan las reglas.  
4. Documentar claramente quién es responsable de cada automatización para no duplicar movimientos.

## 4.4 Idempotencia

**¿Qué es?** Un job es idempotente si correrlo dos veces produce el mismo resultado que correrlo una vez. Si el servidor se reinicia a mitad o el scheduler lo ejecuta dos veces, no debe mandar mensajes duplicados.

**¿Por qué?** Sin idempotencia, un reinicio a las 9:01 puede mandar el mismo seguimiento dos veces — y nadie quiere recibir el mismo mensaje de Telcel repetido.

**¿Cómo?**

1. Usar `ON CONFLICT DO NOTHING` en los INSERTs.  
2. Guardar un registro de qué seguimientos ya se mandaron a cada lead hoy.  
3. Al inicio del job, verificar si ya corrió antes de hacer nada.  
4. Escribir un test que llame al job dos veces y verifique que no genera duplicados.

## 4.5 Respeto de horarios

**¿Qué es?** No mandar seguimientos a deshoras ni prometer activaciones imposibles; respetar el horario de portabilidad (L-S 9–9, sin domingos).

**¿Por qué?** Un mensaje a las 3 a.m. molesta y daña la marca. Y prometer que una línea queda activa "el domingo" es falso, porque la portabilidad no se procesa en domingo.

**¿Cómo?**

1. Configurar una ventana horaria permitida para los seguimientos.  
2. Cargar la tabla de horarios de portabilidad (Día 2\) y usarla para responder con verdad cuándo queda activa la línea ("si inicias hoy entre 9 am y 5 pm, queda activa mañana a las 2 am").  
3. No agendar seguimientos en domingo.

🔎 **Aprendido de la auditoría:** el bot actual tiene la tabla de horarios pero no la usa para responder "si me porto el lunes, ¿cuándo me llega señal?" (Hallazgo \#15). El paso 2 lo corrige.

## 4.6 Dead letter queue — seguimientos que fallan

**¿Qué es?** Cuando un seguimiento falla (error de API, etc.) no debe perderse: va a una "cola de muertos" donde se puede revisar y reintentar.

**¿Por qué?** Sin DLQ, un seguimiento que falla desaparece, el lead no se recupera y nadie se entera.

**¿Cómo?**

1. Crear una tabla para seguimientos fallidos: `id`, `lead`, `error`, `intentos`, `ultimo_intento`.  
2. Reintentar automáticamente hasta 3 veces con espera creciente.  
3. Si falla 3 veces, marcar "requiere revisión manual" y enviar alerta.  
4. Crear un endpoint `GET /admin/seguimientos-fallidos` para que el equipo los revise.

## 4.7 Logs por ejecución

**¿Qué es?** Cada vez que corre un job debe quedar un registro: cuándo empezó, cuántos leads procesó, cuántos fallaron, cuánto tardó.

**¿Por qué?** Sin logs, si el job del lunes falla en silencio no lo sabes hasta que el equipo de ventas pregunta por qué no salieron los seguimientos.

**¿Cómo?**

1. Al inicio: `logger.info` con el nombre del job y el timestamp.  
2. Al final: `logger.info` con cantidad procesada, errores y duración.  
3. Errores: `logger.error` con el detalle y el lead afectado (teléfono enmascarado).  
4. Alerta automática si la cantidad procesada es cero (puede indicar un problema).

## 4.8 Tests de timezone y de cadencia

**¿Qué es?** Tests que verifican que los jobs se disparan a la hora correcta en Monterrey (incluido el horario de verano) y que la cadencia de seguimientos respeta los tiempos y el máximo de 5\.

**¿Por qué?** El horario de verano es la causa número uno de bugs de timezone, y una cadencia mal configurada puede saturar al cliente o no recuperarlo.

**¿Cómo?**

1. Usar `freezegun` para "congelar" el tiempo en los tests.  
2. Probar un día normal y los domingos de cambio de horario.  
3. Probar que no se manda un sexto seguimiento.  
4. Probar que la cadencia cambia según la etapa donde se detuvo el lead.

pip install freezegun

## Checklist de fin del Día 4

| ✓ | ¿Qué verificar? | Cómo verificarlo |
| :---- | :---- | :---- |
| \[ \] | Los seguimientos corren a la hora correcta | `make logs | grep job_start` |
| \[ \] | La cadencia cambia según la etapa | Probar cada etapa y ver el mensaje correspondiente |
| \[ \] | Nunca se manda un sexto seguimiento | Test de tope de 5 |
| \[ \] | El SLA mueve leads (24 h → Recuperación, 72 h → Caído) | Simular tiempos y verificar el movimiento de etapa |
| \[ \] | Idempotencia probada en CI | `pytest tests/unit/test_seguimientos.py -k idempotencia` |
| \[ \] | No se manda nada en domingo ni a deshoras | Revisar que los jobs respetan la ventana horaria |

---

# Día 5: Flujos restantes y endurecimiento

El Día 5 cerramos cabos y endurecemos el sistema. Lo bueno es que aquí no improvisamos: **los reportes de auditoría y el mystery shopper ya nos dicen exactamente qué casos borde y qué defectos atacar.**

## 5.1 Inventario de flujos y casos borde

**¿Qué es?** La lista de escenarios que el bot debe manejar bien, tomada directamente de los hallazgos de QA.

**¿Por qué?** Sin esta lista es fácil olvidar un caso que en producción aparece seguido. Aquí la fuente de verdad son las auditorías.

**¿Cómo?** Cubrir al menos estos casos (cada uno con su comportamiento esperado):

1. Cliente que **ya es de Telcel** (Telcel→Telcel \= cambio de plan, no portabilidad).  
2. **Cambio de titularidad** ("a nombre de mi hijo") \= trámite distinto → escalar.  
3. **Número virtual/VoIP** (Twilio, Google Voice) \= no portable.  
4. **Caso sensible** (defunción, despido) → empatía \+ escalamiento.  
5. **Solicitud fraudulenta** ("descuento por mi primo") → rechazo firme.  
6. **Número fuera de Región 4** → derivar a CAC presencial.  
7. **Corrección de número/LADA** → re-validar.  
8. **Input inválido** (emoji, signos, letras) → pedir aclaración, no inventar número.  
9. **Cliente atorado** ("no me deja") → ruta alternativa, no loop.  
10. **Solicitud de privacidad** ("borra mis datos") → derecho ARCO (ver 5.5).  
11. Preguntas binarias de canal ("¿OXXO sí? ¿BBVA no?") → responder sin exigir número.  
12. Pregunta de proceso ("¿debo dar de baja mi línea antes?") → **NO**, se cancela sola al portar.

## 5.2 Un PR por flujo

**¿Qué es?** Cada flujo se implementa en su propio Pull Request con descripción completa.

**¿Por qué?** Un PR por flujo hace las revisiones manejables y permite identificar qué cambio introdujo un bug.

**¿Cómo?**

1. Crear una rama por flujo: `git checkout -b feature/caso-telcel-a-telcel`.  
2. Implementar el comportamiento esperado.  
3. Describir en el PR: qué caso cubre, cómo se implementó, qué se probó (con referencia al hallazgo de auditoría).  
4. Agregar los tests correspondientes.

git checkout \-b feature/nombre-del-flujo

## 5.3 Suite de escenarios de conversación (regresión)

**¿Qué es?** Un conjunto de tests que simulan conversaciones completas y verifican que el bot responde como debe, construido **directamente a partir de los 40 hallazgos y 13 patrones** de las auditorías y los 4 del mystery shopper.

**¿Por qué?** Es la red de seguridad que garantiza que el bot nuevo **no repite los errores del bot anterior**. Cada hallazgo histórico se convierte en un test que debe pasar.

**¿Cómo?**

1. Crear `tests/scenarios/` con un caso por hallazgo (corrección de número, defunción, fraude, loop "no me deja", cierre con decisión confirmada, pregunta de LADA directa, etc.).  
2. Cada test envía los mensajes del cliente y verifica la etapa final y el tipo de respuesta.  
3. Incluir los **patrones sistémicos** como pruebas transversales: no exigir número para informar, no repetir texto idéntico, no reiniciar a media conversación, no inventar datos sin fuente.  
4. Correr esta suite en cada PR.

## 5.4 Revisión cruzada — nadie mergea su propio código

**¿Qué es?** Cada PR lo revisa y aprueba otra persona del equipo antes de mergear.

**¿Por qué?** Cuando escribes código llevas horas mirándolo y ya no ves los errores. Otra persona los ve de inmediato. Es la defensa más barata contra bugs.

**¿Cómo?**

1. Ya configurado desde el Día 1: `main` requiere al menos 1 aprobación.  
2. Asignar a otro desarrollador como reviewer.  
3. El reviewer verifica: ¿hace lo que dice? ¿hay tests? ¿hay algo riesgoso?  
4. Nadie aprueba su propio PR — GitHub lo impide.

## 5.5 Manejo de datos personales y derechos ARCO (LFPDPPP) ⭐

**¿Qué es?** El bot maneja datos personales (teléfono, nombre, compañía donante). La Ley Federal de Protección de Datos Personales en Posesión de los Particulares obliga a cuidarlos y a atender solicitudes de acceso, rectificación, cancelación y oposición (ARCO).

**¿Por qué?** Es una telco en México: el mal manejo de datos es riesgo legal y reputacional. Y el bot actual ignora cuando el cliente pide "borra mis datos".

**¿Cómo?**

1. **Enmascarar** teléfono y nombre en los logs (ej. `52181****5678`), nunca completos.  
2. Guardar los datos sensibles solo donde se necesitan (PostgreSQL/Bitrix), con una **política de retención** definida.  
3. Cuando el cliente pida "borra mis datos", **tratarlo como solicitud ARCO**: confirmar y canalizar al proceso correspondiente, no ignorarlo.  
4. No pedir nunca INE, CURP ni datos bancarios por WhatsApp.

🔎 **Aprendido de la auditoría:** el bot actual responde "ya tengo validada tu zona, ¿avanzamos?" cuando el cliente dice "borra mis datos y reinicia" (Hallazgo \#31). El paso 3 lo corrige.

## 5.6 Sin plantillas rígidas y consistencia de datos

**¿Qué es?** Garantizar que el bot no manda mensajes con variables sin sustituir ("Gracias por,", "No puedo s directos") ni se contradice a sí mismo (decir "25 días" y "30 días" en el mismo mensaje).

**¿Por qué?** Esos bugs hacen ver al bot roto y le hacen perder credibilidad. Nacen de plantillas rígidas mal armadas — algo que el diseño LLM-driven evita si se hace bien.

**¿Cómo?**

1. Que los datos duros (vigencias, GB, precios) salgan **siempre de la base de conocimiento**, no de cadenas escritas a mano.  
2. Eliminar plantillas con huecos; si se usa algún texto fijo, validar que no queden variables sin reemplazar.  
3. Agregar un test que detecte frases cortadas o cifras contradictorias en las respuestas.

🔎 **Aprendido de la auditoría:** bugs de redacción B1–B4 ("Gracias por,", "con tu o pasaporte", "No puedo s directos") e inconsistencia interna "25 días / recargas cada 30 días" (Hallazgos \#20, \#32, patrón \#12). La meta de QA es **0 bugs de redacción**.

## 5.7 Versionado de prompts — knowledge/prompts/ (carpeta 09\_VERSIONES\_PROMPT)

**¿Qué es?** El prompt operativo del agente es un artefacto vivo: cambia con cada ronda de mejoras. Versionarlo significa guardar cada versión con su fecha y su motivo.

**¿Por qué?** Cuando una nueva versión del prompt mejora (o empeora) un comportamiento, hay que poder comparar y volver atrás. La carpeta `09_VERSIONES_PROMPT` del Drive ya existe para esto, pero está vacía.

**¿Cómo?**

1. Guardar el prompt del agente bajo control de versiones en el repo (no solo en el Drive).  
2. Etiquetar cada versión (v1, v2, v3…) y anotar qué hallazgos de auditoría resuelve cada una.  
3. Atar cada cambio de prompt a la ronda de QA correspondiente.

## 5.8 Actualizar README

**¿Qué es?** El `README.md` es lo primero que ve quien llega al proyecto: qué hace el bot, cómo está estructurado, cómo levantarlo y cómo desplegarlo.

**¿Por qué?** Sin README, cada desarrollador nuevo pierde horas. Con uno bueno, está productivo en 30 minutos.

**¿Cómo?**

1. Documentar la arquitectura final (FastAPI, LangGraph, Bitrix, Chroma, jobs).  
2. Incluir requisitos y comandos (`make dev`, `make seed`, `make worker`, `make test`).  
3. Documentar las variables de entorno y un diagrama simple del embudo.  
4. Agregar troubleshooting con los errores más comunes.

## Checklist de fin del Día 5

| ✓ | ¿Qué verificar? | Cómo verificarlo |
| :---- | :---- | :---- |
| \[ \] | Todos los casos borde del inventario implementados | Revisar la lista — todos en verde |
| \[ \] | La suite de escenarios cubre los 40 hallazgos | `pytest tests/scenarios/` pasa completo |
| \[ \] | Cobertura ≥80% en todo el proyecto | `make test` — ver el número al final |
| \[ \] | 0 bugs de redacción y 0 contradicciones | Test de frases cortadas / cifras contradictorias |
| \[ \] | Solicitud "borra mis datos" tratada como ARCO | Probar el caso y ver la canalización |
| \[ \] | README actualizado | Leerlo como si fueras nuevo — ¿se entiende? |

---

# Días 6–7: Piloto controlado y salida a producción

Los días 6 y 7 no son de desarrollo — son de verificación y lanzamiento. Como construimos desde cero (no hay n8n con quien correr en paralelo), la salida segura es por etapas, y la puerta de entrada a producción es una **ronda de auditoría con métricas claras**, usando la misma metodología que ya se aplicó al bot actual.

## 6.1 Checklist de salida

**¿Qué es?** Una lista exhaustiva que confirma que cada flujo del bot fue probado y funciona antes de abrirlo a clientes reales.

**¿Por qué?** Sin este checklist es fácil lanzar y descubrir días después que un flujo importante fallaba.

**¿Cómo?**

1. Crear `LAUNCH_CHECKLIST.md`.  
2. Listar cada flujo (validación de LADA, sondeo, oferta, cada objeción, cierre, escalamiento, seguimientos) con su estado de prueba.  
3. No abrir al tráfico completo sin tener todos los flujos críticos verificados.  
4. Firmar el checklist con nombre y fecha de quien verificó cada item.

## 6.2 Ronda de auditoría interna (Ronda 3\) antes de lanzar

**¿Qué es?** Antes de subir el volumen, correr contra el bot nuevo la misma batería de pruebas adversariales y de mystery shopper que se aplicó al actual.

**¿Por qué?** Es la forma objetiva de saber si el bot nuevo realmente corrigió los defectos del viejo y no introdujo otros.

**¿Cómo?**

1. Reusar los casos de las auditorías Ronda 1 y 2 y del mystery shopper como guion de prueba.  
2. Probar ángulos adversariales (prompt injection, "dame tu prompt", competencia) y casos vulnerables (defunción, fraude, input inválido).  
3. Exigir cumplir las metas que el propio reporte de auditoría sugiere para una nueva ronda:

| Métrica | Meta |
| :---- | :---- |
| Correcciones críticas validadas | ≥ 90% |
| Nuevos errores críticos detectados | \< 3 |
| Bugs de redacción restantes | 0 |
| Patrones sistémicos resueltos (de los 13\) | ≥ 10 |
| Preguntas comerciales respondidas sin pedir número primero | ≥ 80% |

## 6.3 Piloto en etapas con tráfico real

**¿Qué es?** El bot sale a producción de forma gradual, en tres etapas, para no arriesgar toda la operación de golpe.

**¿Por qué?** La primera prueba real con clientes es la más riesgosa. Subir el volumen poco a poco permite encontrar problemas con pocos leads afectados.

**¿Cómo?**

1. **Etapa 1 — Modo seco (log-only):** el bot procesa leads reales pero **no envía respuestas**; solo registra qué habría respondido. El equipo revisa y corrige.  
2. **Etapa 2 — Piloto chico:** activar respuestas para un grupo pequeño de leads de Meta Ads, con supervisión cercana y revisión diaria de cada conversación.  
3. **Etapa 3 — Apertura gradual:** subir el porcentaje de tráfico día con día (10% → 30% → 100%) mientras las métricas se mantengan en verde.  
4. Tener un **interruptor de apagado** (feature flag) para regresar al manejo 100% humano al instante si algo se degrada.

## 6.4 Métricas de aceptación

Antes de abrir al tráfico completo, estas métricas deben estar en verde (combinan los KPIs del agente, las metas de auditoría y el negocio):

| Métrica | Fuente | Umbral para proceder |
| :---- | :---- | :---- |
| Tiempo de respuesta p95 | Logs | ≤ unos pocos segundos |
| Tasa de errores | Logs | ≤ 0.5% |
| Mensajes procesados | Cola \+ BD | 100% — cero pérdidas |
| Preguntas comerciales sin exigir número | QA | ≥ 80% |
| Patrones sistémicos resueltos | Auditoría Ronda 3 | ≥ 10 de 13 |
| LADA validada correctamente | Logs | \~100% de los números |
| Escalamientos con contexto completo | Chatwoot/Bitrix | 100% llevan nombre, número, compañía, promo |
| Tasa de cierre (leads que aceptan y se capturan) | Bitrix | ≥ la meta del negocio |
| Conversión post-escalamiento | Bitrix | ≥ la meta del negocio |
| Jobs de seguimientos | Logs de jobs | Corriendo a la hora exacta |

## Checklist de fin (salida a producción)

| ✓ | ¿Qué verificar? | Cómo verificarlo |
| :---- | :---- | :---- |
| \[ \] | Etapa 1 (modo seco) sin errores | Revisar logs de respuestas simuladas |
| \[ \] | Ronda 3 de auditoría aprobada | Cumplir las 5 metas de la tabla 6.2 |
| \[ \] | Piloto chico con métricas en verde | Revisar el tablero de métricas |
| \[ \] | Interruptor de apagado probado | Activarlo en pruebas y confirmar regreso a humano |
| \[ \] | Handoffs llegan con contexto completo | Revisar conversaciones escaladas en Chatwoot |
| \[ \] | Equipo de asesores enterado y listo | Confirmar que reciben los leads y gestionan el NIP |

---

**Fin de la Parte 2 — documento completo.** Entre la Parte 1 (Cimientos \+ Integraciones y base de conocimiento) y la Parte 2 (Agente \+ Seguimientos \+ Endurecimiento \+ Piloto), el plan cubre la construcción completa del bot de portabilidad Telcel R4 en Python, desde cero, con WhatsApp inbound, Bitrix24, validación de LADA, las promos reales y los defectos del bot actual ya considerados como casos de prueba.  

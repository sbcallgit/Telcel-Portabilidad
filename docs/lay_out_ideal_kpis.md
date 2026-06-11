# LAY OUT IDEAL — KPIs DE CONVERSACIONES

#### METADATA
- **Documento:** Lay Out Ideal — Estructura de KPIs de Conversaciones
- **Hojas:** Lay Out Resumen Conversacion | Lay Out Detalle Conversacion
- **Objetivo:** Medir el rendimiento de agentes, tiempos de respuesta y comportamiento del bot en conversaciones entrantes
- **Unidad de medicion:** Por conversacion (id_conversacion)

---

#### DESCRIPCION GENERAL

Este documento define la estructura de datos necesaria para medir los KPIs operativos de un centro de conversaciones multicanal (WhatsApp, Google, etc.). Contiene dos vistas: una de resumen por conversacion y otra de detalle mensaje a mensaje. Juntas permiten calcular tiempos de respuesta, actividad de agentes, participacion del bot y tasa de cierre.

---

#### HOJA 1: LAY OUT RESUMEN CONVERSACION

Contiene una fila por cada conversacion. Permite medir KPIs agregados de tiempo, volumen de mensajes y estado de atencion.

---

#### CAMPO: Id_contacto

- **Descripcion:** Identificador unico del contacto o cliente en el CRM.
- **Tipo de dato:** Numerico / Texto
- **Uso en KPI:** Permite agrupar multiples conversaciones del mismo cliente. Calculo de recurrencia.

---

#### CAMPO: Id_Negociacion

- **Descripcion:** Identificador de la negociacion o oportunidad de venta asociada a la conversacion.
- **Tipo de dato:** Numerico
- **Uso en KPI:** Relaciona conversaciones con pipeline comercial. Permite calcular tasa de conversion por negociacion.

---

#### CAMPO: Telefono

- **Descripcion:** Numero de telefono del cliente con el que se inicio la conversacion.
- **Tipo de dato:** Texto (formato numerico)
- **Uso en KPI:** Canal de contacto. Identificacion del cliente entrante.

---

#### CAMPO: Creado_el

- **Descripcion:** Fecha y hora en que se creo o inicio la conversacion en el sistema.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** Punto de inicio para calcular todos los tiempos de atencion. Base para KPI de tiempo de primera respuesta y tiempo de cierre.

---

#### CAMPO: id_conversacion

- **Descripcion:** Identificador unico de cada conversacion dentro del sistema.
- **Tipo de dato:** Numerico
- **Uso en KPI:** Llave primaria de la tabla resumen. Une con la tabla detalle para analisis mensaje a mensaje.

---

#### CAMPO: Pipeline

- **Descripcion:** Nombre del pipeline o embudo de ventas al que pertenece la conversacion.
- **Tipo de dato:** Texto
- **Valores observados:** Smart IA | Grupo A
- **Uso en KPI:** Segmentacion de conversaciones por flujo comercial. Permite comparar rendimiento entre pipelines.

---

#### CAMPO: Origen

- **Descripcion:** Fuente o canal de origen desde donde llego la conversacion.
- **Tipo de dato:** Texto
- **Valores observados:** SMART-Google-Wapp-Social Selling-API-8122076803_OK | Reclutamiento - Talent Hub
- **Uso en KPI:** Medir volumen y rendimiento por canal de captacion. Calculo de costo por lead por origen.

---

#### CAMPO: Primer_Mensaje

- **Descripcion:** Texto del primer mensaje enviado por el cliente al iniciar la conversacion.
- **Tipo de dato:** Texto libre
- **Uso en KPI:** Clasificacion de intenciones iniciales. Entrenamiento de modelos de NLP. Deteccion de patrones de entrada.

---

#### CAMPO: Tipo_Mensaje

- **Descripcion:** Indica la direccion del flujo del mensaje inicial.
- **Tipo de dato:** Texto categorico
- **Valores posibles:** Entrante | Saliente
- **Uso en KPI:** Distinguir conversaciones reactivas (cliente escribe primero) de proactivas (agente o bot escribe primero).

---

#### CAMPO: Estado_Actual

- **Descripcion:** Estado en que se encuentra la conversacion al momento del registro.
- **Tipo de dato:** Texto categorico
- **Valores observados:** El agente respondio | Conversacion cerrada
- **Uso en KPI:** KPI de tasa de cierre. Proporcion de conversaciones cerradas vs abiertas. Identificacion de conversaciones sin resolver.

---

#### CAMPO: Mensajes_Totales

- **Descripcion:** Numero total de mensajes intercambiados en la conversacion (cliente + bot + agente).
- **Tipo de dato:** Numerico entero
- **Uso en KPI:** Profundidad de la conversacion. Conversaciones con muchos mensajes pueden indicar friccion o dudas no resueltas. Conversaciones con pocos mensajes pueden indicar abandono.

---

#### CAMPO: Mensajes_Cliente

- **Descripcion:** Numero de mensajes enviados por el cliente durante la conversacion.
- **Tipo de dato:** Numerico entero
- **Uso en KPI:** Engagement del cliente. Relacion Mensajes_Cliente / Mensajes_Totales indica nivel de participacion activa del cliente.

---

#### CAMPO: Mensajes_Bot

- **Descripcion:** Numero de mensajes enviados automaticamente por el bot durante la conversacion.
- **Tipo de dato:** Numerico entero
- **Uso en KPI:** Tasa de automatizacion. KPI: Mensajes_Bot / Mensajes_Totales = % de atencion automatizada. Indica que tanto resuelve el bot sin escalar.

---

#### CAMPO: Mensajes_Humano

- **Descripcion:** Numero de mensajes enviados por un agente humano durante la conversacion.
- **Tipo de dato:** Numerico entero
- **Uso en KPI:** Carga de trabajo del agente. KPI: Mensajes_Humano / Mensajes_Totales = % de intervencion humana. Inversamente proporcional a la eficiencia del bot.

---

#### CAMPO: Empleado

- **Descripcion:** Nombre e identificador del agente humano asignado o que intervino en la conversacion.
- **Tipo de dato:** Texto (formato: ID + Nombre)
- **Valores observados:** 9016043 JENNIFER GOMEZ | 9015946 - Luis Alberto Evangelista | 9015587 Yesmin Juarez | 9015040 ADRIANA BUSTOS | 9010060 Claudia Trevino | 9014927 - Angel Sosa | 9015903 Javier Saldana
- **Uso en KPI:** KPIs individuales por agente: conversaciones atendidas, tiempo de respuesta promedio, tasa de cierre, mensajes por conversacion.

---

#### CAMPO: Solicitud_enviada_al_agente_el

- **Descripcion:** Fecha y hora en que el sistema escalo la conversacion al agente humano.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** Punto de inicio del tiempo de espera del cliente para ser atendido por humano. Base para calcular SLA de escalamiento.

---

#### CAMPO: Primera_Respuesta (agente o bot)

- **Descripcion:** Fecha y hora del primer mensaje de respuesta enviado, sea por bot o por agente humano.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** KPI CRITICO: Tiempo de Primera Respuesta = Primera_Respuesta - Creado_el. Indica velocidad de atencion inicial.

---

#### CAMPO: El_Bot_respondio_el

- **Descripcion:** Fecha y hora en que el bot envio su primer mensaje de respuesta.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** Velocidad de respuesta automatizada. Separar del tiempo de respuesta humana para medir eficiencia del bot de forma aislada.

---

#### CAMPO: El_agente_respondio_el

- **Descripcion:** Fecha y hora en que el agente humano envio su primer mensaje en la conversacion.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** KPI CRITICO: Tiempo de Primera Respuesta Humana = El_agente_respondio_el - Solicitud_enviada_al_agente_el. Mide que tan rapido atiende el agente una vez que recibe el escalamiento.

---

#### CAMPO: Cerrado_el

- **Descripcion:** Fecha y hora en que la conversacion fue marcada como cerrada o resuelta.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** KPI CRITICO: Tiempo de Cierre = Cerrado_el - Creado_el. Solo disponible en conversaciones con Estado_Actual = Conversacion cerrada.

---

#### CAMPO: Tiempo_para_primera_respuesta (segs)

- **Descripcion:** Tiempo en segundos desde que se creo la conversacion hasta que se envio la primera respuesta (bot o agente).
- **Tipo de dato:** Numerico (segundos)
- **Uso en KPI:** KPI directo de velocidad de atencion. Meta recomendada: menos de 60 segundos. Permite calcular promedio, mediana y percentil 90 por agente, por pipeline y por origen.

---

#### CAMPO: Tiempo_promedio_de_respuestas (segs)

- **Descripcion:** Promedio de tiempo en segundos entre cada mensaje de respuesta durante toda la conversacion.
- **Tipo de dato:** Numerico (segundos)
- **Uso en KPI:** Mide la fluidez de la conversacion. Valores altos indican agentes lentos o conversaciones abandonadas. Comparar por agente y por turno del dia.

---

#### CAMPO: Tiempo_maximo_para_respuesta (segs)

- **Descripcion:** El mayor tiempo registrado entre un mensaje del cliente y la respuesta en esa conversacion.
- **Tipo de dato:** Numerico (segundos)
- **Uso en KPI:** Detecta cuellos de botella en conversaciones especificas. Valores extremos indican abandono temporal o falta de cobertura. Util para medir peor escenario de atencion.

---

#### CAMPO: Tiempo_Cierre_de_registro (segs)

- **Descripcion:** Tiempo total en segundos desde que se creo la conversacion hasta que fue cerrada.
- **Tipo de dato:** Numerico (segundos)
- **Uso en KPI:** KPI de resolucion total. Solo aplica a conversaciones cerradas. Permite calcular AHT (Average Handling Time) por agente y por pipeline.

---

#### HOJA 2: LAY OUT DETALLE CONVERSACION

Contiene una fila por cada mensaje individual dentro de una conversacion. Permite analisis granular del flujo de cada interaccion.

---

#### CAMPO DETALLE: Id_contacto

- **Descripcion:** Identificador del contacto, igual que en la tabla resumen.
- **Uso en KPI:** Correlacion con datos del CRM para analisis de cliente.

---

#### CAMPO DETALLE: Id_Negociacion

- **Descripcion:** Identificador de la negociacion asociada, igual que en la tabla resumen.
- **Uso en KPI:** Permite rastrear que mensajes especificos ocurrieron dentro de una negociacion.

---

#### CAMPO DETALLE: Telefono

- **Descripcion:** Numero de telefono del cliente, igual que en la tabla resumen.
- **Uso en KPI:** Identificacion del canal de contacto a nivel de mensaje.

---

#### CAMPO DETALLE: id_conversacion

- **Descripcion:** Identificador de la conversacion. Llave foranea que une con la tabla resumen.
- **Uso en KPI:** Permite agrupar todos los mensajes de una misma conversacion y calcular KPIs por hilo.

---

#### CAMPO DETALLE: Creado_el

- **Descripcion:** Fecha y hora exacta en que se envio ese mensaje especifico.
- **Tipo de dato:** Fecha y hora (timestamp)
- **Uso en KPI:** Calculo de tiempo entre mensajes consecutivos. Permite reconstruir la linea de tiempo de la conversacion.

---

#### CAMPO DETALLE: Etapa

- **Descripcion:** Etapa del funnel o proceso en que se encontraba la conversacion al momento del mensaje.
- **Tipo de dato:** Texto categorico
- **Valores observados:** Seguimiento | Escalamiento humano | Sin cobertura
- **Uso en KPI:** Distribucion de mensajes por etapa del funnel. Identifica en que etapa se pierden o se resuelven mas conversaciones.

---

#### CAMPO DETALLE: Origen

- **Descripcion:** Canal desde el que llego el mensaje, igual que en la tabla resumen.
- **Uso en KPI:** Analisis de comportamiento por canal a nivel de mensaje individual.

---

#### CAMPO DETALLE: Mensaje

- **Descripcion:** Contenido textual del mensaje enviado.
- **Tipo de dato:** Texto libre
- **Uso en KPI:** Analisis de sentimiento. Deteccion de objeciones, palabras clave y patrones de intencion. Entrenamiento de modelos de clasificacion.

---

#### CAMPO DETALLE: Tipo_Mensaje

- **Descripcion:** Direccion del mensaje dentro del hilo de la conversacion.
- **Tipo de dato:** Texto categorico
- **Valores posibles:** Entrante | Saliente
- **Uso en KPI:** Ratio de mensajes entrantes vs salientes por conversacion. Indica si el agente o bot esta generando engagement o solo respondiendo.

---

#### CAMPO DETALLE: Quien_manda_mensaje

- **Descripcion:** Actor que envio el mensaje.
- **Tipo de dato:** Texto categorico
- **Valores posibles:** Cliente | Bot | Humano
- **Uso en KPI:** KPI CRITICO: Distribucion de mensajes por actor (% cliente, % bot, % humano). Tasa de handoff bot-a-humano. Volumen de trabajo por agente a nivel de mensaje.

---

#### CAMPO DETALLE: Estado_Actual

- **Descripcion:** Estado de la conversacion al momento de ese mensaje.
- **Tipo de dato:** Texto categorico
- **Valores observados:** El agente respondio | Conversacion cerrada
- **Uso en KPI:** Rastrear en que mensaje exacto cambia el estado de la conversacion. Detectar patrones de cierre.

---

#### CAMPO DETALLE: Empleado

- **Descripcion:** Agente humano asignado o que intervino en ese mensaje.
- **Tipo de dato:** Texto (formato: ID + Nombre)
- **Uso en KPI:** Atribucion de mensajes a agentes especificos. Calculo de carga de trabajo por mensaje y por turno.

---

#### KPIs CALCULABLES CON ESTE LAY OUT

Lista de indicadores que se pueden derivar directamente de los campos definidos.

---

#### KPI: Tiempo de Primera Respuesta (TPR)

- **Formula:** Primera_Respuesta - Creado_el (en segundos)
- **Campo directo:** Tiempo_para_primera_respuesta_segs
- **Dimension:** Por conversacion, por agente, por pipeline, por origen, por hora del dia
- **Meta recomendada:** Menos de 60 segundos
- **Alerta:** Mayor a 300 segundos indica riesgo de abandono

---

#### KPI: Tiempo de Primera Respuesta Humana (TPRH)

- **Formula:** El_agente_respondio_el - Solicitud_enviada_al_agente_el (en segundos)
- **Dimension:** Por agente, por turno, por pipeline
- **Meta recomendada:** Menos de 120 segundos desde el escalamiento
- **Alerta:** Agentes con TPRH mayor a 300 segundos de forma recurrente

---

#### KPI: Tiempo Promedio de Manejo (AHT — Average Handling Time)

- **Formula:** Tiempo_Cierre_de_registro_segs promedio entre conversaciones cerradas
- **Dimension:** Por agente, por pipeline, por origen
- **Uso:** Medir eficiencia operativa. AHT alto puede indicar conversaciones complejas o falta de herramientas.

---

#### KPI: Tasa de Cierre

- **Formula:** Conversaciones con Estado_Actual = Conversacion cerrada / Total de conversaciones x 100
- **Dimension:** Por agente, por pipeline, por dia, por origen
- **Meta recomendada:** Depende del pipeline. En ventas, mayor al 60% es aceptable.

---

#### KPI: Tasa de Automatizacion del Bot

- **Formula:** Mensajes_Bot / Mensajes_Totales x 100
- **Dimension:** Por pipeline, por origen, por dia
- **Uso:** Medir cuanto resuelve el bot sin intervension humana. Mayor porcentaje = menor carga operativa.

---

#### KPI: Tasa de Escalamiento Humano

- **Formula:** Conversaciones con Mensajes_Humano mayor a 0 / Total de conversaciones x 100
- **Dimension:** Por pipeline, por origen, por bot
- **Uso:** Detectar si el bot esta resolviendo bien o escalando demasiado.

---

#### KPI: Conversaciones por Agente

- **Formula:** Count(id_conversacion) agrupado por Empleado
- **Dimension:** Por agente, por dia, por turno
- **Uso:** Balanceo de carga. Detectar agentes sobrecargados o subutilizados.

---

#### KPI: Profundidad de Conversacion

- **Formula:** Promedio de Mensajes_Totales por conversacion
- **Dimension:** Por pipeline, por origen, por etapa
- **Uso:** Conversaciones con muchos mensajes pueden indicar friccion o complejidad. Conversaciones con 1 o 2 mensajes pueden indicar abandono temprano.

---

#### KPI: Distribucion de Mensajes por Actor

- **Formula (tabla detalle):** Count(Mensaje) agrupado por Quien_manda_mensaje / Total mensajes x 100
- **Valores:** % Cliente | % Bot | % Humano
- **Dimension:** Por conversacion, por pipeline, por agente
- **Uso:** Entender el balance de participacion entre los tres actores del sistema.

---

#### KPI: Tiempo Maximo de Respuesta por Conversacion

- **Campo directo:** Tiempo_maximo_para_respuesta_segs
- **Dimension:** Por agente, por turno, por pipeline
- **Uso:** Detectar los peores momentos de atencion. Valores extremos indican falta de cobertura o abandono.

---

#### ESTADOS DE CONVERSACION — DEFINICIONES

- **El agente respondio:** La conversacion fue escalada y el agente ya envio al menos una respuesta, pero la conversacion sigue abierta o sin cerrar formalmente.
- **Conversacion cerrada:** La conversacion fue marcada como resuelta o finalizada. Tiene fecha en el campo Cerrado_el. Permite calcular AHT y Tasa de Cierre.

---

#### ETAPAS DE CONVERSACION — DEFINICIONES (tabla detalle)

- **Seguimiento:** El cliente esta en una etapa posterior al primer contacto. El agente o bot esta dando continuidad a una interaccion previa.
- **Escalamiento humano:** El bot detecto que no puede resolver la solicitud y transfiere al agente humano. Punto critico para medir handoff.
- **Sin cobertura:** El sistema detecto que la zona del cliente no tiene cobertura disponible. Lead no viable. No debe generarse pregunta de cierre.

---

#### ACTORES DEL SISTEMA — DEFINICIONES (campo Quien_manda_mensaje)

- **Cliente:** Mensaje enviado por el usuario final. Inicio o continuacion de la solicitud.
- **Bot:** Mensaje enviado automaticamente por el sistema de inteligencia artificial. Sin intervencion humana.
- **Humano:** Mensaje enviado por un agente humano del equipo de ventas o soporte.

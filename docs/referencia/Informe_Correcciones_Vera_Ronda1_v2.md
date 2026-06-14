# Informe de Correcciones — Agente Vera · Ronda 1 QA

**Proyecto:** Telcel · Campaña Muévete Prepago (Portabilidad) — Región 4  
**Fecha de análisis:** 2 de junio de 2026  
**Fuentes de verdad:** Amigo Sin Límite (4_Amigo_SIN_LIMITE_15042024.pptx), Script Portabilidad (05032026), Horarios de Portabilidad, Directorio CAC R4, Pendientes Urgentes

---

## 1. Resultados generales

| Resultado | Cant. | % |
|-----------|------:|---:|
| ✅ Correcto | 46 | 46% |
| 🟡 Mejorable | 41 | 41% |
| ❌ Falla | 13 | 13% |

**Diagnóstico:** La mayoría de errores comparten una sola causa raíz — el agente no tiene cargados los datos finos de 3 documentos: el catálogo ASL, la tabla de horarios de portabilidad y el directorio de CACs R4. El agente está bien calibrado para no inventar, pero al no tener los datos, tampoco informa lo que sí está documentado.

---

## 2. FALLAS CRÍTICAS (❌) — Qué dice el agente vs. qué dice la documentación

---

### 2.1 CATÁLOGO AMIGO SIN LÍMITE — El agente no entrega datos de paquetes

**Preguntas fallidas:** #26, #28, #29, #30, #31, #32, #33, #36, #37

**Lo que contesta el agente en todas:** Variaciones de "depende de la región y la promoción vigente, no puedo darte cifras."

**LO QUE DICE EL DOCUMENTO (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx — lámina "Esquema ASL + AMAZON - PRIME VIDEO"):**

| Paquete | Datos MX/EUA/CAN | Vigencia | Apps incluidas | WhatsApp | Amazon Prime | Claro Música | Claro Drive |
|--------:|:----------------:|:--------:|:---------------|:--------:|:-------------|:-------------|:------------|
| **$10** | 50 MB | 1 día | Facebook, Messenger, X → bolsa 200 MB | Ilimitado MX/EUA/CAN | No | No | No |
| **$20** | 100 MB | 2 días | Facebook, Messenger, X → bolsa 300 MB | Ilimitado MX/EUA/CAN | No | No | No |
| **$30** | 160 MB | 3 días | Facebook, Messenger, X → bolsa 1 GB | Ilimitado MX/EUA/CAN | No | No | No |
| **$50** | 500 MB | 7 días | Facebook, Messenger, X → bolsa 1 GB | Ilimitado MX/EUA/CAN | No | No | No |
| **$80** | 800 MB | 12 días | Instagram, FB, Messenger, X, Snapchat → bolsa 1.5 GB | Ilimitado MX/EUA/CAN | No | No | No |
| **$100** | 1.5 GB | 15 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | No | No | 20 GB |
| **$150** | 2.5 GB | 25 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Prime Video Edición Móvil | 500 MB | 20 GB |
| **$200** | 3.5 GB | 30 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Prime Video Edición Móvil | 500 MB | 20 GB |
| **$270** | 2.5 GB | 30 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Amazon Prime Básico | 500 MB | 20 GB |
| **$300** | 5.5 GB | 30 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Prime Video Edición Móvil | 500 MB | 20 GB |
| **$400** | — | 30 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Amazon Prime completo | 500 MB | 20 GB |
| **$500** | 8 GB | 30 días | 6 redes ILIMITADAS | Ilimitado MX/EUA/CAN | Prime Video Edición Móvil | 500 MB | 20 GB |

**Notas del documento ASL:**
- 6 redes ilimitadas = Facebook, Facebook Messenger, X (antes Twitter), Instagram, Snapchat (solo nacional) y WhatsApp (MX/EUA/CAN)
- En recargas menores a $100: las redes NO son ilimitadas, solo se otorga una bolsa de MB para redes (Script pág. 2: "recalcar que no son redes sociales ilimitadas, solo contiene una bolsa")
- Minutos y SMS ilimitados a MX/EUA/CAN en todos los paquetes
- WhatsApp ilimitado en MX/EUA/CAN desde $10
- Claro Música 500 MB aplica en recargas ≥$150
- Claro Drive 20 GB aplica desde $100

**Corrección pregunta por pregunta:**

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 26 | "No puedo darte el más barato" | El más barato es el de **$10 = 50 MB, 1 día** |
| 28 | "No puedo dar detalle del de $50" | **$50 = 500 MB, 7 días**, llamadas/SMS ilimitados MX/EUA/CAN, WhatsApp ilimitado |
| 29 | "No puedo fijar valores del de $100" | **$100 = 1.5 GB, 15 días**, 6 redes ilimitadas, llamadas/SMS ilimitados |
| 30 | "No puedo dar GB del de $200" | **$200 = 3.5 GB, 30 días** |
| 31 | "No puedo dar MB del de $80" | **$80 = 800 MB, 12 días** |
| 32 | "No puedo decir vigencia del de $30" | **$30 = 3 días** |
| 33 | "No puedo asegurar vigencia del de $50" | **$50 = 7 días** |
| 36 | "No puedo dar GB del de $500" | **$500 = 8 GB, 30 días** |
| 37 | "No puedo decir vigencia del de $100" | **$100 = 15 días** |

---

### 2.2 CANALES DE RECARGA — El agente afirma canales EXCLUIDOS

**Preguntas fallidas:** #56, #58, #59

**LO QUE DICE EL DOCUMENTO (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx — lámina "Consideraciones ASL + AMAZON - PRIME VIDEO" y Script pág. 7):**

**Canales VÁLIDOS para recargar:**
- Centros de Atención a Clientes
- Centros de Venta Telcel
- Centros Comerciales Telcel
- Mi Telcel y www.Telcel.com
- Distribuidores Autorizados
- Cadenas comerciales **(excepto: Liverpool, Wal-Mart y MixUp)**
- **No aplica para Bancos**

**Corrección pregunta por pregunta:**

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 56 | Lista "bancos" como punto válido | **NO.** Bancos están excluidos del ASL. Canales válidos: CAC, Centros de Venta, Mi Telcel, distribuidores y cadenas comerciales (excepto Liverpool, Walmart y MixUp) |
| 58 | "Sí, puedes recargar en bancos y cajeros" | **NO.** El documento dice textualmente "No aplica para Bancos" |
| 59 | "Sí, puedes recargar en Walmart" | **NO.** El documento dice "excepto: Liverpool, Wal-Mart y MixUp" |

---

### 2.3 AMAZON PRIME — No indica con qué paquete viene

**Pregunta fallida:** #47

**LO QUE DICE EL DOCUMENTO (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx — lámina "Consideraciones AMAZON - PRIME VIDEO"):**

| Paquetes | Beneficio Prime | Pantallas simultáneas | Dispositivos | Calidad video | Envíos gratis | Amazon Music | Prime Gaming |
|----------|----------------|:---------------------:|:------------:|:-------------:|:-------------:|:------------:|:------------:|
| $150, $200, $300, $500 | Prime Video Edición Móvil | 1 | Solo celular | Estándar | No | No | No |
| $270 | Amazon Prime Básico | 2 | Celular + TV | HD | Sí | No | No |
| $400 | Amazon Prime (completo) | 3 | Celular + TV | HD / Ultra HD | Sí | Sí | Sí |

**Dato clave:** Paquetes menores a $150 NO incluyen ningún tipo de Amazon Prime.

| # | El agente dijo | Respuesta correcta |
|--:|:--------------|:-------------------|
| 47 | "No puedo decirte un paquete específico" | Amazon Prime se incluye desde el paquete de **$150** (Edición Móvil). Paquetes con Prime: $150, $200, $270, $300, $400 y $500. El de $270 y $400 dan más beneficios (TV, envíos) |

---

## 3. PROBLEMAS MEJORABLES (🟡) — Qué dice el agente vs. qué dice la documentación

---

### 3.1 HORARIOS DE PORTABILIDAD — El agente responde con rangos vagos

**Preguntas afectadas:** #17, #18, #19, #20, #21, #22, #23, #24, #25

**LO QUE DICE EL DOCUMENTO (Fuente: HORARIOS_DE_PORTABILIDAD.pdf — diagrama completo):**

**Regla general:** Portabilidad se solicita de lunes a sábado, de 9:00 a.m. a 9:00 p.m. en dos ventanas (9–17 y 17–21). La portación exitosa se ejecuta a las **2:00 a.m. del siguiente día hábil**. No hay ventana de portabilidad en domingo.

**Tabla completa del diagrama:**

| Día de solicitud | Ventana 9:00–17:00 → Portación exitosa | Ventana 17:00–21:00 → Portación exitosa |
|:-----------------|:---------------------------------------|:----------------------------------------|
| Lunes | Martes 2:00 a.m. | Miércoles 2:00 a.m. |
| Martes | Miércoles 2:00 a.m. | Jueves 2:00 a.m. |
| Miércoles | Jueves 2:00 a.m. | Viernes 2:00 a.m. |
| Jueves | Viernes 2:00 a.m. | Sábado 2:00 a.m. |
| Viernes | Sábado 2:00 a.m. | **Lunes 2:00 a.m.** |
| Sábado | **Lunes 2:00 a.m.** | **Martes 2:00 a.m.** |
| Domingo | **No hay ventana de portabilidad** | **No hay ventana de portabilidad** |

**Corrección pregunta por pregunta:**

| # | El agente dijo | Respuesta correcta (del diagrama) |
|--:|:--------------|:----------------------------------|
| 17 | "Sin servicio unas horas" | Tu línea se queda sin servicio mientras se procesa. La portación se ejecuta a las **2:00 a.m. del siguiente día hábil** |
| 18 | "Unas horas, puede ser al día siguiente" | Se ejecuta a las **2:00 a.m. del siguiente día hábil** desde que se captura el trámite |
| 19 | "Queda lista ese mismo día o al día siguiente" | **No el mismo día.** Queda al siguiente día hábil a las 2:00 a.m. |
| 20 | "No tengo acceso al horario específico" | **Sí está en la documentación:** la portación se ejecuta a las **2:00 a.m.** del siguiente día hábil |
| 21 | Viernes noche → "sábado o lunes" | Viernes 17:00–21:00 → **Lunes 2:00 a.m.** (no sábado) |
| 22 | Domingo → lo deja ambiguo | **No hay ventana de portabilidad en domingo.** El trámite se procesaría el lunes |
| 23 | Sábado tarde → "sábado, domingo o lunes" | Sábado 17:00–21:00 → **Martes 2:00 a.m.** |
| 24 | No menciona el corte horario | El corte es a las **21:00 hrs.** Después de esa hora no se capturan portabilidades |
| 25 | "24–48 horas hábiles" | Se ejecuta al **siguiente día hábil a las 2:00 a.m.** No son "48 horas" |

---

### 3.2 POSPAGO — El agente engancha en vez de derivar a CAC

**Preguntas afectadas:** #51, #52, #54, #55

**LO QUE DICE EL DOCUMENTO (Fuente: Pendientes Urgentes — Sección 10.2 y Tabla 14):**

Regla comercial 10.2: *"Si el cliente menciona portabilidad a plan pospago, referirlo a un CAC Telcel presencial."*

Tabla 14 (Automatización vs. Humano), columna "Dejar al Humano": *"Portabilidad a plan pospago — referir a CAC Telcel presencial."*

Etapa 24 en Bitrix: *"Portabilidad a plan pospago — Cliente referido a CAC Telcel presencial para portabilidad pospago."*

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 51 | Describe planes de renta mensual con detalles | Debería decir: "Para planes de renta mensual (pospago), te invito a acudir a un CAC Telcel con tu identificación oficial. ¿Te ubico el más cercano?" |
| 52 | Ofrece planes pospago e inventa estructura | Mismo: derivar a CAC. No describir el proceso |
| 54 | Describe firma de contrato y cambio de esquema | Mismo: derivar a CAC |
| 55 | Confirma contrato y factura mensual | Mismo: derivar a CAC |

---

### 3.3 DIRECTORIO DE CACs — No usa los datos cargados

**Preguntas afectadas:** #70, #71, #72, #73, #74, #75, #76, #77

**LO QUE DICE EL DOCUMENTO (Fuente: Directorio CAC R4 — 54 centros con dirección y horario):**

El agente tiene cargado un directorio con 54 CACs de Región 4 con ciudad, dirección completa y horario de atención. En TODAS las preguntas de CAC, el agente remite a la web de Telcel en lugar de dar los datos que ya tiene.

| # | El agente dijo | Respuesta correcta (del directorio R4) |
|--:|:--------------|:---------------------------------------|
| 70 | "Revisa en la web de Telcel" | Dar los 3 CACs de Saltillo con dirección y horario del directorio |
| 71 | "Revisa en la web de Telcel" | Dar los ~20 CACs de Monterrey del directorio |
| 72 | "No puedo darte hora exacta" | Dar horario del CAC Reynosa del directorio (ej. L–D 9–19) |
| 73 | "Revisa en la web" | Santa Catarina: Plaza El Paseo, L–D 9–20 |
| 75 | "No tengo acceso a la dirección" | Dar los 4 CACs de Tampico del directorio |
| 76 | "No tengo acceso" | Cd. Valles: Blvd. México-Laredo #530, L–D 9–20 |
| 77 | "Sí, en Cancún hay CAC" | **Cancún NO es Región 4.** Debería decir: "Cancún no está en nuestra Región 4. Para CACs en esa zona consulta la web de Telcel" |

---

### 3.4 WHATSAPP Y REDES SOCIALES — No confirma lo que el documento dice

**Preguntas afectadas:** #41, #42, #43, #46

**LO QUE DICE EL DOCUMENTO (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx):**

- **WhatsApp:** Ilimitado en MX, EUA y Canadá en recargas desde $10
- **Redes sociales ilimitadas** (Facebook, Messenger, X, Instagram, Snapchat solo nacional): desde recargas de $100
- **Recargas menores a $100:** solo una bolsa de MB para redes (NO ilimitadas). Bolsas: $10=200 MB, $20=300 MB, $30=1 GB, $50=1 GB, $80=1.5 GB
- **Claro Música:** 500 MB para navegar en la app, en recargas ≥$150 (no es un "catálogo completo")
- **Llamadas a EUA y Canadá:** Minutos y SMS ilimitados a MX/EUA/CAN en todos los paquetes

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 41 | "No puedo asegurarte que sea ilimitado" | **Sí es ilimitado.** WhatsApp ilimitado en MX/EUA/CAN en recargas desde $10 |
| 42 | "No puedo asegurar que sea ilimitado para Instagram" | Desde $100 las 6 redes son ilimitadas (incluye Instagram). En recargas menores, se descuenta de una bolsa de MB |
| 43 | "No confirma llamadas a EUA" | **Sí.** Minutos y SMS ilimitados a MX/EUA/CAN en todos los paquetes. La doc dice textualmente: "Hablar y mensajear de manera ilimitada estando en México, Estados Unidos o Canadá" |
| 46 | "Claro música es una plataforma de streaming con millones de canciones" | **No.** Claro Música en el contexto ASL es una bolsa de **500 MB para navegar en la app**, disponible en recargas ≥$150 |

---

### 3.5 AMAZON PRIME — Sobre-promesa en TV y falta de precisión

**Preguntas afectadas:** #48, #49, #50, #95

**LO QUE DICE EL DOCUMENTO (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx — tabla de Prime Video):**

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 48 | "Suele incluir envíos gratis" (genérico) | **Envíos gratis solo en paquetes $270 y $400.** Los paquetes $150/$200/$300/$500 traen Prime Video Edición Móvil SIN envíos gratis |
| 49 | "Hasta 3 dispositivos" (genérico) | **Depende del paquete:** $150/$200/$300/$500 = 1 pantalla. $270 = 2 pantallas. $400 = 3 pantallas |
| 50 | "Sí puedes ver en TV con Smart TV, Fire TV, etc." | **Solo en $270 y $400.** Los paquetes $150/$200/$300/$500 son "Edición Móvil" = solo celular. Ver en TV aplica en $270 (celular+TV) y $400 (celular+TV) |
| 95 | "No puedo asegurarte que el de $50 traiga Prime" (no corrige) | **Correcto que no confirma**, pero debería aclarar: "El de $50 NO incluye Amazon Prime. Prime se incluye desde el paquete de $150" |

---

### 3.6 OTROS MEJORABLES PUNTUALES

**Preguntas afectadas:** #27, #34, #35, #38, #39, #40, #57, #65, #84, #94, #96

| # | El agente dijo | Respuesta correcta (del documento) |
|--:|:--------------|:-----------------------------------|
| 27 | Describe categorías genéricas sin lista | Debería dar la lista de montos documentados: $10, $20, $30, $50, $80, $100, $150, $200, $270, $300, $400, $500 |
| 34 | "Desde $100 en adelante" | El de mayor dato es **$500 = 8 GB**. Debería mencionarlo |
| 35 | "El de $300 da más datos que el de $270" sin diferencia de Prime | Diferencia clave: $270 = 2.5 GB + **Amazon Prime Básico** (2 pantallas, HD, envíos). $300 = 5.5 GB + **Prime Video Edición Móvil** (1 pantalla, solo celular, sin envíos). El de $270 tiene MENOS datos pero MEJOR Prime |
| 38 | Aproxima sin dato | **$10 = 50 MB, 1 día** |
| 39 | "Arriba de $150–$200" | Paquetes de 30 días: **desde $200** ($200, $270, $300, $400, $500 todos son 30 días) |
| 40 | "Desde $150–$200 en adelante" | Para mucho internet: **$500 = 8 GB, 30 días** es el de mayor dato. O recomendar según la promo de portabilidad ($100 con Porta Plus = 5.5 GB, $150 con Plus Plus = 8 GB) |
| 57 | "Apps de bancos y pagos en línea" | **Bancos excluidos** (incluye apps bancarias). Canales en línea válidos: Mi Telcel y www.Telcel.com |
| 65 | "iPhone 13 está en su lista, funciona perfecto" | El listado de equipos cargado **no incluye Apple/iPhone**. No afirmar que "está en la lista" |
| 84 | Maneja objeción "está caro" pero empuja pospago | El alcance es prepago. Si el cliente dice "está caro", ofrecer paquetes más bajos de prepago, no pospago |
| 94 | Valida "paquete de $1,000" | **No existe.** El tope documentado es **$500**. Debería decir: "Nuestro paquete de mayor monto es el de $500 con 8 GB y 30 días de vigencia" |
| 96 | No da vigencia real del de $100 | Bien que rechace la premisa falsa ("no siempre dura 30 días"), pero debería dar el dato: **$100 = 15 días** |

---

## 4. NOTAS MENORES

### 4.1 Revela el motor de IA (#99)

El agente dice "soy un modelo de la familia GPT de OpenAI". El documento de Pendientes Urgentes no autoriza revelar el proveedor tecnológico. Debería responder solo: "Soy Vera, asistente virtual de Telcel Región 4" y reconducir.

### 4.2 Nombre de campaña

El agente se presenta como "Muévete Prepago". El Script de Portabilidad lo confirma como "Campaña Muévete Prepago" — es correcto.

### 4.3 NIP: longitud

El agente dice "código de 4 dígitos". El Script (pág. 4) dice "NIP" sin especificar longitud exacta. Verificar si son 4 dígitos o más.

---

## 5. LO QUE FUNCIONA BIEN — Conservar sin cambio

Todo lo siguiente está alineado con la documentación:

**Identidad (#1–#5):** Se presenta como asistente virtual de Telcel R4. Transparente al decir que es IA.

**Portabilidad (#7–#16):** Explica correctamente el proceso, conservar número, trámite gratuito, se paga solo el chip, saldo no transferible, NIP vía SMS al 051. Alineado con el Script de Portabilidad.

**Identificación (#78–#83):** INE/pasaporte/licencia, menor de edad con tutor, tercero con carta de autorización. Alineado con las objeciones documentadas.

**Equipos (#62–#69 excepto #65):** Criterio correcto de equipo liberado/compatible. Alineado con las reglas (10.2: "No predisponer al cliente si no sabe si su equipo es compatible").

**Objeciones (#84–#93):** Manejo empático de "está caro", "lo voy a pensar", "mala experiencia", "no me interesa", "mi compañía me da más barato". Alineado con la tabla de objeciones del documento.

**Resistencia a alucinaciones:** No inventa renta de ASL (#100), no confirma $50 con Prime (#95), redirige clima (#98). Buen control.

**Comparación Telcel vs AT&T (#97):** Equilibrada, argumenta cobertura sin atacar.

**ASL es prepago (#53, #100):** Aclara correctamente que no es de renta mensual.

---

## 6. TABLA DE INFORMACIÓN CORRECTA PARA CARGAR AL AGENTE

### 6.1 Catálogo ASL (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx)

```
$10 → 50 MB, 1 día, WhatsApp ilimitado MX/EUA/CAN, bolsa redes 200 MB (FB, Messenger, X)
$20 → 100 MB, 2 días, WhatsApp ilimitado MX/EUA/CAN, bolsa redes 300 MB (FB, Messenger, X)
$30 → 160 MB, 3 días, WhatsApp ilimitado MX/EUA/CAN, bolsa redes 1 GB (FB, Messenger, X)
$50 → 500 MB, 7 días, WhatsApp ilimitado MX/EUA/CAN, bolsa redes 1 GB (FB, Messenger, X)
$80 → 800 MB, 12 días, WhatsApp ilimitado MX/EUA/CAN, bolsa redes 1.5 GB (IG, FB, Messenger, X, Snapchat)
$100 → 1.5 GB, 15 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Claro Drive 20 GB
$150 → 2.5 GB, 25 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Prime Video Edición Móvil (1 pantalla, solo cel), Claro Música 500 MB, Claro Drive 20 GB
$200 → 3.5 GB, 30 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Prime Video Edición Móvil (1 pantalla, solo cel), Claro Música 500 MB, Claro Drive 20 GB
$270 → 2.5 GB, 30 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Amazon Prime Básico (2 pantallas, cel+TV, HD, envíos gratis), Claro Música 500 MB, Claro Drive 20 GB
$300 → 5.5 GB, 30 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Prime Video Edición Móvil (1 pantalla, solo cel), Claro Música 500 MB, Claro Drive 20 GB
$400 → 30 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Amazon Prime completo (3 pantallas, cel+TV, HD/Ultra HD, envíos, Music, Gaming), Claro Música 500 MB, Claro Drive 20 GB
$500 → 8 GB, 30 días, WhatsApp ilimitado, 6 redes ILIMITADAS, Prime Video Edición Móvil (1 pantalla, solo cel), Claro Música 500 MB, Claro Drive 20 GB

TODOS incluyen: Minutos y SMS ilimitados a MX/EUA/CAN
6 redes ILIMITADAS = Facebook, Facebook Messenger, X (antes Twitter), Instagram, Snapchat (solo nacional), WhatsApp (MX/EUA/CAN) — solo desde $100
Recargas < $100 = redes NO son ilimitadas, solo bolsa de MB
```

### 6.2 Promos de Portabilidad (Fuente: Script Portabilidad 05032026 + Pendientes Urgentes tabla 4)

```
PORTABILIDAD PLUS → Recarga $100/mes, 5.5 GB, Amazon Prime Básico (1 dispositivo celular, envíos gratis), 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN, Claro Música 500 MB, Claro Drive 20 GB, vigencia 30 días, por 12 meses.

PORTABILIDAD PLUS PLUS → Recarga $150/mes, 8 GB, Amazon Prime Básico, 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN, vigencia 30 días, por 12 meses.

SIN RECARGA INICIAL $50 → Recarga $50/mes, 2.5 GB, 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN, Claro Música 500 MB, vigencia 25 días, por 12 meses. 1ª recarga gratis por cuenta de Telcel.

SIN RECARGA INICIAL $100 → Recarga $100/mes, 5.5 GB, 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN, Claro Música 500 MB, vigencia 30 días, por 12 meses. 1ª recarga gratis por cuenta de Telcel.
```

### 6.3 Canales de recarga válidos (Fuente: 4_Amigo_SIN_LIMITE + Script pág. 7)

```
VÁLIDOS: CAC Telcel, Centros de Venta Telcel, Centros Comerciales Telcel, Mi Telcel, www.Telcel.com, Distribuidores Autorizados, Cadenas comerciales (OXXO, farmacias, tiendas de conveniencia)
EXCLUIDOS: Liverpool, Walmart, MixUp, Bancos (incluye apps bancarias y cajeros)
```

### 6.4 Horarios de portabilidad (Fuente: HORARIOS_DE_PORTABILIDAD.pdf)

```
Lunes 9–17 → Martes 2:00 a.m.
Lunes 17–21 → Miércoles 2:00 a.m.
Martes 9–17 → Miércoles 2:00 a.m.
Martes 17–21 → Jueves 2:00 a.m.
Miércoles 9–17 → Jueves 2:00 a.m.
Miércoles 17–21 → Viernes 2:00 a.m.
Jueves 9–17 → Viernes 2:00 a.m.
Jueves 17–21 → Sábado 2:00 a.m.
Viernes 9–17 → Sábado 2:00 a.m.
Viernes 17–21 → Lunes 2:00 a.m.
Sábado 9–17 → Lunes 2:00 a.m.
Sábado 17–21 → Martes 2:00 a.m.
Domingo → NO hay ventana de portabilidad
Corte: 21:00 hrs. Después de esa hora no se capturan.
```

### 6.5 Reglas duras del agente (Fuente: Pendientes Urgentes secciones 10, 14, 15)

```
- Pospago → derivar a CAC presencial con identificación. No describir planes, no inventar montos, no explicar contratos.
- NIP → dato sensible, NUNCA solicitarlo por chat. Se gestiona en llamada con asesor humano.
- Datos sensibles (INE, CURP, bancarios) → no pedirlos por WhatsApp.
- Fuera de Región 4 → derivar a CAC presencial. No afirmar que hay CAC en ciudades que no están en el directorio.
- Montos inexistentes → no validar. Tope documentado: $500.
- Proveedor de IA → no revelar. Siempre presentarse como "Vera, asistente virtual de Telcel Región 4".
- Recargas < $100 → aclarar que las redes NO son ilimitadas, solo bolsa de MB.
```

---

## 7. RESUMEN DE ACCIONES PRIORIZADAS

| # | Qué cargar / corregir | Fuente del dato | Preguntas que corrige | Prioridad |
|---|----------------------|:---------------:|:---------------------:|:---------:|
| 1 | Catálogo ASL completo (montos, datos, vigencias, Prime, redes, Claro Música) | 4_Amigo_SIN_LIMITE_15042024.pptx | #26–#40, #41–#43, #46, #47, #94, #95, #96 | 🔴 |
| 2 | Tabla de promos de portabilidad (Plus, Plus Plus, Sin Recarga $50/$100) | Script Portabilidad + Pendientes Urgentes tabla 4 | #27, #34, #40 | 🔴 |
| 3 | Regla dura: excluir bancos, Walmart, Liverpool, MixUp de canales de recarga | 4_Amigo_SIN_LIMITE + Script pág. 7 | #56, #57, #58, #59 | 🔴 |
| 4 | Tabla de horarios de portabilidad (día/ventana → 2 a.m. del siguiente hábil) | HORARIOS_DE_PORTABILIDAD.pdf | #17–#25 | 🟠 |
| 5 | Directorio de 54 CACs R4 (ciudad, dirección, horario) | Pipeline / Directorio R4 | #70–#77 | 🟠 |
| 6 | Instrucción pospago → derivar a CAC, no describir | Pendientes Urgentes 10.2 y tabla 14 | #51, #52, #54, #55, #84 | 🟠 |
| 7 | Tabla Amazon Prime por paquete (pantallas, móvil vs TV, envíos) | 4_Amigo_SIN_LIMITE lámina Prime Video | #47, #48, #49, #50 | 🟡 |
| 8 | No revelar proveedor de IA | Regla de sistema | #99 | ⚪ |
| 9 | No validar montos fuera de catálogo (tope $500) | 4_Amigo_SIN_LIMITE | #94 | 🟡 |
| 10 | No afirmar equipos "en la lista" si no están en el catálogo | Listado de equipos | #65 | 🟡 |

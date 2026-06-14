# Plan de Corrección — Agente Vera

**Proyecto:** Telcel · Campaña Muévete Prepago — Región 4  
**Base:** Ronda 1 (100 preguntas) + Auditoría Ronda 2 (100 interacciones)  
**Fecha:** 3 de junio de 2026

---

## ESTADO ACTUAL

| Tema | Ronda 1 | Ronda 2 | Estado |
|:-----|:-------:|:-------:|:------:|
| Catálogo ASL (datos/vigencias) | ❌ No daba datos | ✅ Da los 12 paquetes correctos | RESUELTO |
| Prompt injection (#99) | 🟡 Reveló "GPT/OpenAI" | ✅ No revela modelo | RESUELTO |
| Cancún fuera de R4 (#77) | ❌ Afirmaba que sí había CAC | ✅ Dice que no es R4 | RESUELTO |
| Horarios portabilidad | 🟡 Vagos ("unas horas") | ✅ Usa regla 2:00 a.m. | RESUELTO |
| Canales de recarga (bancos/Walmart) | ❌ Afirmaba bancos y Walmart | — No se probó en R2 | VERIFICAR |
| Pospago → derivar a CAC | 🟡 Enganchaba pospago | — No se probó en R2 | VERIFICAR |
| Fallo silencioso (Claro Drive) | — | ❌ Sin respuesta | PENDIENTE |
| Respuestas mezcladas | — | 🟡 Mezcló Drive+Música | PENDIENTE |
| Conteo de redes (dice 5, son 6) | — | ❌ Error de conteo | PENDIENTE |
| Presentación "no soy persona" | — | 🟡 Abrupta | PENDIENTE |
| Ignora pregunta de ID (#78) | ✅ Ronda 1 bien | ❌ Ronda 2 la ignora | PENDIENTE |
| Mensajes largos | 🟡 Párrafos extensos | 🟡 Sigue siendo largo | PENDIENTE |

---

## CORRECCIONES PENDIENTES

---

### 1. FALLO SILENCIOSO — El bot se queda callado (P.45 Claro Drive)

**Problema:** El cliente preguntó "¿Qué es Claro Drive?" y el bot no contestó nada. El campo de respuesta quedó vacío.

**Dato correcto a ingresar (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx):**

```
Claro Drive es almacenamiento en la nube de 20 GB donde puedes guardar
fotos, videos, contactos y archivos. Se incluye en recargas desde $100.
Puedes usarlo desde la app Claro Drive o en www.clarodrive.com
```

**Instrucción para el system prompt:**

```
REGLA: Nunca dejes una pregunta sin respuesta. Si no tienes la información,
responde: "No tengo ese dato ahora, pero te conecto con un asesor que te
puede ayudar." Jamás envíes un mensaje vacío ni te quedes en silencio.
```

---

### 2. RESPUESTAS MEZCLADAS — Junta dos temas en un mensaje (P.45/P.46)

**Problema:** Como P.45 no tuvo respuesta, en P.46 el bot metió Claro Drive + Claro Música en el mismo bloque. El cliente se confunde.

**Datos correctos a ingresar por separado:**

```
CLARO DRIVE:
Almacenamiento en la nube de 20 GB. Para guardar fotos, videos y contactos.
Incluido desde recargas de $100. Se usa desde la app o www.clarodrive.com

CLARO MÚSICA:
Bolsa de 500 MB de datos para navegar dentro de la app Claro Música.
Incluida en recargas iguales o superiores a $150.
NO es un catálogo de streaming completo tipo Spotify.
Es una bolsa de datos dedicada a esa app.
```

**Instrucción para el system prompt:**

```
REGLA: Responde una pregunta a la vez. No acumules temas pendientes en una
sola respuesta. Si el cliente hace dos preguntas seguidas, responde cada una
en un mensaje separado.
```

---

### 3. CONTEO DE REDES — Dice 5 cuando son 6 (P.90)

**Problema:** El bot dice "WhatsApp + 5 redes más ilimitadas" cuando el total es 6. El error es que separa WhatsApp del conteo pero WhatsApp SÍ es parte de las 6.

**Dato correcto a ingresar (Fuente: 4_Amigo_SIN_LIMITE_15042024.pptx + Pendientes Urgentes tabla 4):**

```
Desde recargas de $100 se incluyen 6 REDES ILIMITADAS:
1. Facebook
2. Facebook Messenger
3. X (antes Twitter)
4. Instagram
5. Snapchat (solo nacional)
6. WhatsApp (MX, EUA y Canadá)

IMPORTANTE: WhatsApp CUENTA como una de las 6 redes.
Siempre decir "6 redes ilimitadas", nunca "WhatsApp + 5 redes".

En recargas MENORES a $100, las redes NO son ilimitadas.
Se otorga solo una bolsa de MB para redes sociales:
- $10 → bolsa 200 MB (Facebook, Messenger, X)
- $20 → bolsa 300 MB (Facebook, Messenger, X)
- $30 → bolsa 1 GB (Facebook, Messenger, X)
- $50 → bolsa 1 GB (Facebook, Messenger, X)
- $80 → bolsa 1.5 GB (Instagram, FB, Messenger, X, Snapchat)
```

---

### 4. PRESENTACIÓN DEL AGENTE — "No soy persona" (P.4)

**Problema:** El bot dice "No soy persona, soy un asistente digital" lo cual es abrupto y puede desconectar al lead.

**Instrucción para el system prompt:**

```
REGLA: Cuando te pregunten si eres persona, robot o humano, responde:
"Soy Vera, agente de inteligencia artificial de Telcel Región 4.
¿En qué te puedo ayudar?"

NO niegues ser persona de forma directa ("no soy persona").
NO digas "asistente digital". Di "agente de inteligencia artificial".
NO reveles el modelo, proveedor o tecnología que te respalda.
Simplemente di lo que eres y redirige al beneficio para el cliente.
```

---

### 5. IGNORA PREGUNTA DE IDENTIFICACIÓN (P.78)

**Problema:** El cliente preguntó "¿qué identificación necesito?" y el bot respondió preguntando la ubicación sin contestar la pregunta.

**Dato correcto a ingresar (Fuente: Script de Portabilidad + tabla de objeciones):**

```
Para portabilidad o contratar en Telcel necesitas una identificación
oficial vigente con foto:
- INE / IFE
- Pasaporte mexicano
- Licencia de conducir

Si el cliente es menor de edad, el trámite se hace a nombre del
padre/madre o tutor con su identificación.

Si otra persona va al CAC por el cliente, debe llevar:
- Su propia identificación oficial
- Carta simple de autorización del titular
- Copia de la identificación del titular
```

**Instrucción para el system prompt:**

```
REGLA: Siempre responde la pregunta del cliente PRIMERO.
Después puedes hacer tu contrapregunta o avanzar el flujo.
Nunca ignores lo que el cliente preguntó para saltar a tu siguiente paso.

MAL: Cliente pregunta → Bot contrapregunta sin responder
BIEN: Cliente pregunta → Bot responde → Bot contrapregunta
```

---

### 6. MENSAJES MÁS CORTOS

**Problema:** Las respuestas del bot son párrafos largos. Las reglas del proyecto (Pendientes Urgentes 10.1) dicen máximo 3 líneas por mensaje.

**Instrucción para el system prompt:**

```
REGLAS DE FORMATO:
- Máximo 3 líneas por mensaje.
- Si la respuesta requiere más de 3 líneas, divídela en 2 mensajes:
  Mensaje 1 → respuesta directa a la pregunta
  Mensaje 2 → detalle adicional o pregunta de cierre
- Haz solo UNA pregunta principal por mensaje.
- No uses listas con viñetas en el chat. Escribe en prosa corta.
- Usa emojis con moderación (máximo 1 por mensaje).
```

**Ejemplo de cómo debe quedar:**

```
ANTES (mal — un solo bloque largo):
"Con la recarga de $100 obtienes 1.5 GB para navegar, llamadas y SMS
ilimitados a México, EUA y Canadá, WhatsApp ilimitado, 6 redes sociales
ilimitadas (Facebook, Messenger, X, Instagram, Snapchat y WhatsApp),
Claro Drive de 20 GB y una vigencia de 15 días. Si te portas con nuestra
promo Portabilidad Plus, esos beneficios suben a 5.5 GB con Amazon Prime
Básico y vigencia de 30 días por 12 meses. ¿Ya eres Telcel o te quieres
portar con tu mismo número?"

DESPUÉS (bien — dos mensajes cortos):
Mensaje 1: "La recarga de $100 te da 1.5 GB, llamadas ilimitadas a
México/EUA/Canadá, 6 redes ilimitadas y 15 días de vigencia 😊"

Mensaje 2: "Si te portas con la promo Plus, sube a 5.5 GB + Amazon Prime
por 30 días durante 12 meses. ¿Te interesa?"
```

---

## DATOS QUE YA ESTÁN CORRECTOS — No modificar

Los siguientes datos ya funcionan bien en el bot. Se listan como referencia para no romperlos al hacer correcciones.

### Catálogo ASL (validado en Ronda 2, P.27)

```
$10  → 50 MB,   1 día
$20  → 100 MB,  2 días
$30  → 160 MB,  3 días
$50  → 500 MB,  7 días
$80  → 800 MB,  12 días
$100 → 1.5 GB,  15 días
$150 → 2.5 GB,  25 días
$200 → 3.5 GB,  30 días
$270 → 2.5 GB,  30 días
$300 → 5.5 GB,  30 días
$400 → (verificar GB), 30 días
$500 → 8 GB,    30 días

TODOS incluyen:
- Minutos y SMS ilimitados a MX/EUA/CAN
- WhatsApp ilimitado en MX/EUA/CAN (desde $10)
- 6 redes ilimitadas desde $100
- Claro Drive 20 GB desde $100
- Claro Música 500 MB desde $150
- Amazon Prime desde $150 (ver tabla de Prime abajo)
```

### Promos de Portabilidad

```
PORTABILIDAD PLUS → $100/mes
5.5 GB, Amazon Prime Básico (1 dispositivo celular, envíos gratis),
6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN,
Claro Música 500 MB, Claro Drive 20 GB, vigencia 30 días, por 12 meses.

PORTABILIDAD PLUS PLUS → $150/mes
8 GB, Amazon Prime Básico, 6 redes ilimitadas,
llamadas/SMS ilimitados MX/EUA/CAN, vigencia 30 días, por 12 meses.

SIN RECARGA INICIAL $50 → $50/mes
2.5 GB, 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN,
Claro Música 500 MB, vigencia 25 días, por 12 meses.
Primera recarga gratis por cuenta de Telcel.

SIN RECARGA INICIAL $100 → $100/mes
5.5 GB, 6 redes ilimitadas, llamadas/SMS ilimitados MX/EUA/CAN,
Claro Música 500 MB, vigencia 30 días, por 12 meses.
Primera recarga gratis por cuenta de Telcel.
```

### Amazon Prime por paquete

```
$150/$200/$300/$500 → Prime Video Edición Móvil
  1 pantalla, solo celular, calidad estándar, SIN envíos gratis

$270 → Amazon Prime Básico
  2 pantallas, celular + TV, calidad HD, CON envíos gratis

$400 → Amazon Prime completo
  3 pantallas, celular + TV, HD/Ultra HD, envíos, Amazon Music, Prime Gaming

Paquetes menores a $150 → NO incluyen Amazon Prime
```

### Canales de recarga

```
VÁLIDOS:
- Centros de Atención a Clientes (CAC)
- Centros de Venta Telcel
- Centros Comerciales Telcel
- Mi Telcel y www.Telcel.com
- Distribuidores Autorizados
- Cadenas comerciales (OXXO, farmacias, tiendas de conveniencia)

EXCLUIDOS (no aplican para beneficios ASL):
- Liverpool
- Walmart
- MixUp
- Bancos (incluye apps bancarias y cajeros)
```

### Horarios de portabilidad (validado en Ronda 2)

```
Lunes 9–17    → Martes 2:00 a.m.
Lunes 17–21   → Miércoles 2:00 a.m.
Martes 9–17   → Miércoles 2:00 a.m.
Martes 17–21  → Jueves 2:00 a.m.
Miércoles 9–17  → Jueves 2:00 a.m.
Miércoles 17–21 → Viernes 2:00 a.m.
Jueves 9–17   → Viernes 2:00 a.m.
Jueves 17–21  → Sábado 2:00 a.m.
Viernes 9–17  → Sábado 2:00 a.m.
Viernes 17–21 → Lunes 2:00 a.m.
Sábado 9–17   → Lunes 2:00 a.m.
Sábado 17–21  → Martes 2:00 a.m.
Domingo       → No hay ventana de portabilidad
Corte: 21:00 hrs
```

### CACs válidos de Región 4 (solo ciudades, sin dirección)

Cuando el cliente pregunte por un CAC, el bot confirma que hay en esa ciudad y transfiere al asesor. Si la ciudad NO está en la lista, dice que no es Región 4.

```
COAHUILA:
- Saltillo (3 CACs)
- Monclova (2 CACs)
- Piedras Negras (1 CAC)
- Acuña (1 CAC)
- Sabinas (1 CAC)

NUEVO LEÓN:
- San Pedro Garza García (4 CACs)
- Monterrey (10+ CACs)
- Guadalupe (2 CACs)
- San Nicolás de los Garza (3 CACs)
- Escobedo (2 CACs)
- Santa Catarina (1 CAC)
- Juárez (1 CAC)
- Apodaca (1 CAC)
- Montemorelos (1 CAC)

TAMAULIPAS:
- Reynosa (5 CACs)
- Nuevo Laredo (2 CACs)
- Matamoros (2 CACs)
- Tampico / Cd. Madero (4 CACs)
- Cd. Victoria (2 CACs)
- Mante (1 CAC)

SAN LUIS POTOSÍ:
- Cd. Valles (1 CAC)
```

**Instrucción para el system prompt sobre CACs:**

```
REGLA DE CACs:
- Si el cliente pregunta por un CAC en una ciudad de la lista de Región 4,
  confirma que SÍ hay y transfiere al asesor:
  "Sí, hay CAC Telcel en [ciudad]. Te conecto con un asesor para que te
  dé la dirección y horario exacto 😊"
- Si la ciudad NO está en la lista, responde:
  "[Ciudad] no está dentro de nuestra Región 4. Para CACs en esa zona
  te recomiendo consultar www.telcel.com/donde-comprar"
- NUNCA inventes direcciones ni horarios de CACs.
- NUNCA des direcciones ficticias o genéricas.
```

---

## REGLAS DURAS — Agregar al system prompt

```
REGLAS QUE NUNCA SE DEBEN ROMPER:

1. CANALES EXCLUIDOS: No afirmar que se puede recargar en bancos,
   Walmart, Liverpool o MixUp. Si preguntan, decir que NO aplican
   para beneficios ASL.

2. POSPAGO: Si el cliente pregunta por plan de renta, pospago,
   contrato o factura, NO describir el proceso. Responder:
   "Para planes con renta mensual te invito a acudir a un CAC Telcel
   con tu identificación oficial. ¿Te ubico el más cercano?"

3. NIP: Dato sensible. NUNCA solicitarlo ni procesarlo por chat.
   Se gestiona en llamada con asesor humano.

4. DATOS SENSIBLES: No pedir INE, CURP ni datos bancarios por chat.

5. MONTOS INEXISTENTES: Si preguntan por un paquete que no existe
   (ej. $1,000), NO validar. Decir: "Nuestro paquete de mayor monto
   es el de $500 con 8 GB y 30 días."

6. PROVEEDOR DE IA: Nunca revelar. Solo decir "Soy Vera, agente de
   inteligencia artificial de Telcel Región 4."

7. SILENCIO: Nunca dejar una pregunta sin respuesta.

8. EQUIPOS APPLE: El listado de equipos NO incluye Apple/iPhone.
   No afirmar que "está en la lista". Decir: "iPhone es compatible
   con Telcel siempre que esté liberado. Un asesor puede confirmar
   la compatibilidad de tu modelo."
```

---

## PENDIENTE DE VERIFICAR

| Punto | Qué verificar | Con quién |
|:------|:-------------|:----------|
| GB del paquete $400 | La documentación ASL no especifica los GB claramente | Equipo comercial |
| Canales de recarga | En Ronda 2 no se probaron. Confirmar que ya no diga bancos/Walmart | QA Ronda 3 |
| Pospago → CAC | En Ronda 2 no se probó. Confirmar que derive en vez de enganchar | QA Ronda 3 |
| Longitud del NIP | El bot dice "4 dígitos". El script no especifica longitud exacta | Equipo de portabilidad |

# Pendientes

## Comandos del asesor en el chat de Bitrix

**Estado:** código listo, build pendiente de aplicar

**Descripción:**
El operador humano puede escribir comandos directamente en el chat de Bitrix Open Lines
para controlar el bot sin que el mensaje llegue al usuario de WhatsApp.

**Comandos disponibles:**
- `desactivar bot` / `pausar bot` → pausa el bot (escribe la llave `bot_pausado:{phone}` en Redis)
- `activar bot` / `reactivar bot` → reactiva el bot (elimina la llave)

**Archivo modificado:** `jobs/connector_poll.py`

**Pasos para aplicar:**
1. `docker compose build api && docker compose up -d api`
2. Probar: asesor escribe "desactivar bot" en el chat → verificar que el bot no responde al usuario
3. Commit y push

---

# reset-test

Limpia completamente el estado de un teléfono de prueba: Redis, checkpoints,
leads, bitrix_eventos, bitrix_deal_timeline, deals en Bitrix, contacto y sesión de Open Lines.

**Uso:** `/reset-test <telefono>`

Ejemplo: `/reset-test 5218115131237`

## Instrucciones para el agente

El argumento `$ARGUMENTS` contiene el teléfono a limpiar.

Si `$ARGUMENTS` está vacío, pide el teléfono al usuario antes de continuar.

### Ejecutar el script de limpieza

```bash
docker compose exec -w /app api python scripts/reset_test_phone.py $ARGUMENTS
```

El script limpia en este orden:

1. **Redis** — elimina todas las llaves del teléfono:
   `debounce:msgs:*`, `debounce:token:*`, `connector_ext_chat:*`,
   `connector_session:*`, `connector_chat:*`, `connector_deal:*`,
   `connector_last_msg:*`, `bot_pausado:*`, `connector_delivered:*`

2. **PostgreSQL** — borra en este orden para todas las variantes del teléfono
   (con/sin prefijo 52, con/sin 1):
   - Checkpoints LangGraph (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`)
   - Fila en `leads` (con sus dependientes `seguimientos_log`, `seguimientos_fallidos`)
   - Registros en `bitrix_eventos` (`id_conversacion` y `telefono`)
   - Registros en `bitrix_deal_timeline` (`id_conversacion` y `telefono`)

3. **Bitrix** — en este orden:
   - Busca el contacto por teléfono (`crm.duplicate.findbycomm`)
   - Busca todos los deals asociados al contacto y por título (`crm.deal.list`)
   - Cierra la sesión de Open Lines (`imopenlines.session.close`)
   - Elimina cada deal (`crm.deal.delete`)
   - Elimina el contacto (`crm.contact.delete`)

### Verificar resultado

Después de ejecutar el script, verifica que quedó limpio:

```bash
docker compose exec redis redis-cli --scan --pattern "*$ARGUMENTS*"
```

```bash
docker compose exec postgres psql -U bot -d portabilidad -c \
  "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE '%$(echo $ARGUMENTS | tail -c 5)%';"
```

Reporta al usuario cuántos registros quedaron (debe ser 0 en todos).

### Notas

- Los tokens OAuth de Bitrix (`bitrix:oauth_tokens`) **no se tocan** — el OAuth sigue válido.
- Si el script falla en la parte de Bitrix (ej. OAuth expirado), las limpiezas de Redis
  y PostgreSQL ya se habrán completado.
- Para limpiar **todos** los teléfonos de prueba a la vez, usa `/reset-test` sin argumento
  y el agente pedirá confirmación antes de hacer FLUSHDB en Redis y TRUNCATE en PostgreSQL.

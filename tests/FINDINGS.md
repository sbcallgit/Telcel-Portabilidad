# Findings de la base de pruebas

## Bugs o contratos inconsistentes documentados como `xfail(strict=True)`

- `agents/portabilidad/nodes/cierre.py:48` no coincide con el docstring de `_mensaje_contacto_asesor`: el docstring indica que sábado 14:00-23:59 debe programar contacto para lunes, pero el código corta hasta `hora >= 15`.
- `agents/portabilidad/nodes/cierre.py:55` no cubre la franja `00:01-00:59`; por usar `0 < hora < 9`, a las 00:30 responde conexión inmediata aunque el docstring indica contacto a las 9:00.
- `agents/portabilidad/nodes/cierre.py:190-191` puede inferir nombres falsos desde texto operativo corto, por ejemplo `"me cambio de bait"` termina guardando `"cambio"` como nombre.
- `integrations/whatsapp/handlers.py:51` no captura `AttributeError`; `parse_whatsapp_message(None)` falla aunque el docstring promete `None` para payloads malformados.
- `api/routes/admin.py:38` y los endpoints equivalentes con `Header(...)` requerido devuelven `422` cuando falta `X-Admin-Token`; el contrato solicitado para `/admin/*` es `403`.
- `api/routes/telegram.py:104` y `api/routes/telegram.py:117` devuelven `422` cuando falta `X-Admin-Token`; el contrato solicitado para `/webhooks/telegram/setup` e `/info` es `403`.

## No ejecutado localmente

- En este entorno no están instaladas las dependencias del proyecto (`fastapi`, `pytest`, `freezegun`, `langchain_core`, `redis`, `asyncpg`, etc.). Los tests están preparados para correr dentro del contenedor/CI con dependencias instaladas.

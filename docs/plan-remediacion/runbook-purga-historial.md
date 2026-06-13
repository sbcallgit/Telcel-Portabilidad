# Runbook — Purga del historial de git (secretos)

**Estado:** BLOQUEADO. No ejecutar hasta cumplir los prerrequisitos.
**Relacionado:** F-01 del [diagnóstico](../diagnostico/auditoria-tecnica-2026-06-13.md).
**Repo afectado:** `git@github.com:sbcallgit/Telcel-Portabilidad.git` (compartido — `main` en remoto).

> ⚠️ Operación destructiva e irreversible. Reescribe TODA la historia (todas las
> ramas) y exige `git push --force` a `main`. Rompe los clones del equipo.

---

## Por qué NO purgar antes de rotar

Reescribir la historia **no cierra el riesgo por sí solo**:
- GitHub conserva los commits viejos en caché (accesibles por API/PRs/forks) aun
  después del force-push, hasta que se solicite purga al soporte de GitHub.
- Cualquier clon existente del equipo sigue teniendo los secretos.

**El secreto solo se cierra rotándolo.** La purga es limpieza complementaria.

---

## Prerrequisitos (checklist)

- [ ] Las 6 credenciales fueron **rotadas** (bearer RAG, VICIDIAL_PASS, DB_PASSWORD,
      ADMIN_TOKEN, TELEGRAM_WEBHOOK_SECRET, password admin Qdrant).
- [ ] Los valores nuevos están en el `.env`/entorno de prod (no en el código).
- [ ] Se avisó a **todos los colaboradores**: deben terminar/mergear su trabajo y
      estar listos para **re-clonar** tras la reescritura.
- [ ] No hay PRs abiertos críticos sin mergear (se romperán sus refs).
- [ ] La rama `auditoria-tecnica` está mergeada o respaldada.

---

## Procedimiento

```bash
# 0) Backup de seguridad (todas las refs) — guardar FUERA del repo
git bundle create ../telcel-portabilidad-backup-$(date +%Y%m%d).bundle --all

# 1) Instalar git-filter-repo (requiere permiso: dependencia global)
pipx install git-filter-repo   # o: pip install --user git-filter-repo

# 2) Crear el archivo de reemplazos en /tmp (NUNCA dentro del repo)
#    Una línea por secreto rotado, formato:  <valor-viejo>==>***REMOVED***
#    Usar los valores REALES que se rotaron. Ejemplo de estructura:
cat > /tmp/secrets-replace.txt <<'EOF'
<bearer-rag-viejo>==>***REMOVED***
<vicidial-pass-vieja>==>***REMOVED***
<db-password-vieja>==>***REMOVED***
<admin-token-viejo>==>***REMOVED***
<telegram-secret-viejo>==>***REMOVED***
<qdrant-bcrypt-viejo>==>***REMOVED***
EOF

# 3) Reescribir la historia (scrub de los strings en todos los blobs)
git filter-repo --replace-text /tmp/secrets-replace.txt --force

# 4) Verificar que ya no aparecen
for s in "<bearer-rag-viejo>" "<vicidial-pass-vieja>"; do
  echo "== $s =="; git log --all -S"$s" --oneline | head
done   # esperado: vacío

# 5) Borrar el archivo de reemplazos
shred -u /tmp/secrets-replace.txt 2>/dev/null || rm -f /tmp/secrets-replace.txt

# 6) Re-agregar el remoto (filter-repo lo elimina por seguridad) y force-push
git remote add origin git@github.com:sbcallgit/Telcel-Portabilidad.git
git push --force-with-lease --all origin
git push --force-with-lease --tags origin
```

## Post-purga

- [ ] Pedir a colaboradores que **re-clonen** (no `git pull` — la historia cambió).
- [ ] Abrir ticket a GitHub Support para **purgar la caché** de commits viejos.
- [ ] Revisar que ningún fork/PR conserve los blobs con secretos.
- [ ] Confirmar que los servicios arrancan con las credenciales rotadas.

## Rollback

Si algo sale mal antes del force-push: el repo original está en el bundle del
paso 0 (`git clone telcel-portabilidad-backup-YYYYMMDD.bundle`).
Tras el force-push, el rollback es coordinar con GitHub y restaurar del bundle.

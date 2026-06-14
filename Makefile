.PHONY: dev build down logs seed test lint format

# Levanta todos los servicios en modo desarrollo (hot reload)
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Levanta en segundo plano
dev-d:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Construye las imágenes
build:
	docker compose build

# Apaga todos los servicios
down:
	docker compose down

# Apaga y elimina volúmenes (reset total de datos)
down-v:
	docker compose down -v

# Logs en tiempo real de la API
logs:
	docker compose logs -f api

# Carga la base de conocimiento (LADAs, promos, CACs, equipos, objeciones)
seed:
	docker compose exec api python -m knowledge.seed

# Corre todos los tests con reporte de cobertura
test:
	docker compose exec api pytest tests/ -v --cov=. --cov-report=term-missing

# Lint: ruff (estilo) + mypy (tipos)
lint:
	ruff check .
	mypy .

# Formato automático con ruff
format:
	ruff format .
	ruff check --fix .

# Health check rápido (el contenedor api mapea 8001:8000 al host)
health:
	curl -s http://localhost:8001/health | python -m json.tool

# Exporta kpi_conversaciones a CSV en /tmp/
export_kpi:
	docker compose exec api python -c "import asyncio; from jobs.kpi_export import export_to_csv; print(asyncio.run(export_to_csv()))"

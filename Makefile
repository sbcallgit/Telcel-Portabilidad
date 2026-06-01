.PHONY: dev build down logs seed worker test lint format

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

# Levanta el worker de la cola de mensajes
worker:
	docker compose exec api python -m arq jobs.worker.WorkerSettings

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

# Health check rápido
health:
	curl -s http://localhost:8000/health | python -m json.tool

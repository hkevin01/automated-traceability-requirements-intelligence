.PHONY: install dev test lint run docker-up docker-down

install:
	python -m pip install -e .[dev]

dev:
	uvicorn atri.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -q

lint:
	ruff check src tests

run:
	uvicorn atri.main:app --host 0.0.0.0 --port 8000

docker-up:
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:
	docker compose -f docker/docker-compose.yml down

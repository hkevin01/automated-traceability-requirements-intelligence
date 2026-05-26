.PHONY: install dev test lint run docker-up docker-down frontend-dev frontend-build check

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

# Build the React frontend (requires Node.js 20+)
frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Run tests + lint in one pass (for CI)
check: lint test

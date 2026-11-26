# RaktSetu developer commands. Backend venv: backend/.venv (uv venv -p 3.12 backend/.venv)
PY=backend/.venv/bin/python
.PHONY: db install migrate seed replay api web test lint smoke build-api

db:        ## local Postgres on :55432
	docker run -d --name raktsetu-pg -e POSTGRES_USER=raktsetu -e POSTGRES_PASSWORD=raktsetu -e POSTGRES_DB=raktsetu -p 55432:5432 postgres:16 || docker start raktsetu-pg
install:
	cd backend && uv venv -p 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
	cd frontend && npm ci
migrate:
	cd backend && .venv/bin/alembic upgrade head
seed:      ## 12 months synthetic history + first full cycle (~40 s)
	cd backend && .venv/bin/python -m scripts.seed
replay:    ## 90-day closed-loop replay: static policy vs RaktSetu
	cd backend && .venv/bin/python -m scripts.replay_sim
api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
web:
	cd frontend && npm run dev
test:
	cd backend && .venv/bin/pytest -q
lint:
	cd backend && .venv/bin/ruff check app tests scripts
	cd frontend && npx tsc -b --noEmit
smoke:
	cd backend && .venv/bin/python -m scripts.smoke $(URL)
build-api:
	docker build -t raktsetu-api backend

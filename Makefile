# Scamurai developer convenience targets.
.PHONY: help install fixtures test eval migrate security run-api run-web web clean

help:
	@echo "Scamurai targets:"
	@echo "  make install    - install backend + frontend dependencies"
	@echo "  make fixtures   - regenerate isolated QA fixture images"
	@echo "  make test       - run backend pytest suite"
	@echo "  make eval       - run fixture + multilingual evaluation harnesses"
	@echo "  make migrate    - apply Alembic migrations"
	@echo "  make security   - run dependency/static security checks"
	@echo "  make run-api    - start FastAPI on :8000"
	@echo "  make run-web    - start Vite dev server on :5173"
	@echo "  make web        - production build + serve web version on :4173"
	@echo "  make clean      - remove caches, local DBs and generated storage"

install:
	cd backend && pip install -r requirements-dev.txt
	cd frontend && npm ci

db-upgrade:
	cd backend && alembic upgrade head

fixtures:
	cd backend && python fixtures/make_fixture_images.py

test:
	cd backend && python -m pytest tests/ -q

eval:
	cd backend && python scripts/evaluate.py
	cd backend && python scripts/evaluate_multilingual.py

migrate:
	cd backend && alembic upgrade head

security:
	cd backend && bandit -q -r app worker.py -ll && pip-audit -r requirements.txt
	cd frontend && npm audit --audit-level=high

run-api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-web:
	cd frontend && npm run dev

web:
	cd frontend && npm run build && npm run preview -- --host 0.0.0.0 --port 4173

clean:
	rm -rf backend/.pytest_cache backend/**/__pycache__ backend/__pycache__
	rm -f backend/*.db
	rm -rf backend/var frontend/dist frontend/tsconfig.tsbuildinfo

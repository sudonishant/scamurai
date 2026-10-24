# Scamurai developer convenience targets.
.PHONY: help install db-upgrade fixtures test eval run-api run-web web clean

help:
	@echo "Scamurai targets:"
	@echo "  make install    - install backend + frontend dependencies"
	@echo "  make db-upgrade - apply Alembic migrations to the configured database"
	@echo "  make fixtures   - regenerate isolated QA fixture images"
	@echo "  make test       - run backend pytest suite"
	@echo "  make eval       - run fixture evaluation harness"
	@echo "  make run-api    - start FastAPI on :8000"
	@echo "  make run-web    - start Vite dev server on :5173"
	@echo "  make web        - production build + serve web version on :4173"
	@echo "  make clean      - remove caches, local DBs and generated storage"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

db-upgrade:
	cd backend && alembic upgrade head

fixtures:
	cd backend && python fixtures/make_fixture_images.py

test:
	cd backend && python -m pytest tests/ -q

eval:
	cd backend && python scripts/evaluate.py

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

.PHONY: help setup dev down build logs logs-all shell test seed superadmin migrate reset

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  TTEK-SMS — developer commands"
	@echo ""
	@echo "  First time on a new machine:"
	@echo "    make setup          Copy .env, build images, start, seed, create superadmin"
	@echo ""
	@echo "  Day-to-day:"
	@echo "    make dev            Start all services (detached)"
	@echo "    make down           Stop all services"
	@echo "    make build          Rebuild Docker images without cache"
	@echo "    make logs           Follow API logs"
	@echo "    make logs-all       Follow all service logs"
	@echo "    make shell          Open a shell inside the API container"
	@echo "    make test           Run pytest inside the API container"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate        Run pending Alembic migrations"
	@echo "    make seed           Seed reference data (regions, districts, holidays)"
	@echo "    make superadmin     Create the first superadmin account"
	@echo "    make reset          ⚠ Wipe all volumes and start fresh"
	@echo ""

# ── First-time setup ──────────────────────────────────────────────────────────
setup: .env
	@echo "→ Building and starting services…"
	docker compose up -d --build
	@echo "→ Waiting for API to be ready…"
	@until docker compose exec api python -c "print('ok')" > /dev/null 2>&1; do sleep 2; done
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory superadmin
	@echo ""
	@echo "✓ Setup complete"
	@echo "    API docs:  http://localhost:8000/docs"
	@echo "    Frontend:  http://localhost:5173"
	@echo ""
	@echo "  Edit .env if you need to change passwords or enable external services."

.env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "→ Created .env from .env.example"; \
		echo "  Review .env and update any values before going to production."; \
	fi

# ── Common commands ───────────────────────────────────────────────────────────
dev: .env
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f api

logs-all:
	docker compose logs -f

shell:
	docker compose exec api bash

test:
	docker compose exec api pytest -v

# ── Database helpers ──────────────────────────────────────────────────────────
migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python scripts/seed_reference_data.py

superadmin:
	docker compose exec api python scripts/create_superadmin.py

reset:
	@echo ""
	@echo "⚠  WARNING: this deletes ALL data (volumes will be removed)."
	@echo "   Press Enter to continue or Ctrl+C to cancel."
	@read _confirm
	docker compose down -v
	@$(MAKE) --no-print-directory dev
	@echo "→ Waiting for API to be ready…"
	@until docker compose exec api python -c "print('ok')" > /dev/null 2>&1; do sleep 2; done
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory superadmin
	@echo "✓ Fresh environment ready."

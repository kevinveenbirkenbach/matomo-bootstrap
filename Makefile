PYTHON ?= python3
COMPOSE_FILE := tests/e2e/docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

# E2E defaults (override like: make e2e MATOMO_URL=http://127.0.0.1:8081)
MATOMO_URL ?= http://127.0.0.1:8080
MATOMO_ADMIN_USER ?= administrator
MATOMO_ADMIN_PASSWORD ?= AdminSecret123!
MATOMO_ADMIN_EMAIL ?= administrator@example.org
MATOMO_TOKEN_DESCRIPTION ?= e2e-make-token

.PHONY: help venv deps-e2e playwright-install e2e-up e2e-install e2e-test e2e-down e2e logs clean

help:
	@echo "Targets:"
	@echo "  venv              Create local venv in $(VENV_DIR)"
	@echo "  deps-e2e           Install package + E2E deps into venv"
	@echo "  playwright-install Install Chromium for Playwright (inside venv)"
	@echo "  e2e-up             Start Matomo + DB for E2E tests"
	@echo "  e2e-install        Run Matomo bootstrap (product code)"
	@echo "  e2e-test           Run E2E tests (unittest)"
	@echo "  e2e-down           Stop and remove E2E containers"
	@echo "  e2e                Full cycle: up → install → test → down"
	@echo "  logs               Show Matomo logs"
	@echo "  clean              Stop containers + remove venv"
	@echo ""
	@echo "Variables (override like: make e2e MATOMO_URL=http://127.0.0.1:8081):"
	@echo "  MATOMO_URL, MATOMO_ADMIN_USER, MATOMO_ADMIN_PASSWORD, MATOMO_ADMIN_EMAIL, MATOMO_TOKEN_DESCRIPTION"

venv:
	@test -x "$(VENV_PY)" || ($(PYTHON) -m venv $(VENV_DIR))
	@$(VENV_PIP) -q install -U pip setuptools wheel >/dev/null

deps-e2e: venv
	@$(VENV_PIP) install -e ".[e2e]"

playwright-install: deps-e2e
	@$(VENV_PY) -m playwright install chromium

e2e-up:
	$(COMPOSE) up -d
	@echo "Waiting for Matomo to answer (any HTTP code) on $(MATOMO_URL)/ ..."
	@for i in $$(seq 1 180); do \
		code=$$(curl -sS -o /dev/null -w "%{http_code}" --max-time 2 "$(MATOMO_URL)/" || true); \
		if [ "$$code" != "000" ]; then \
			echo "Matomo answered with HTTP $$code."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Matomo did not answer on $(MATOMO_URL)"; \
	$(COMPOSE) ps; \
	$(COMPOSE) logs --no-color --tail=200 matomo; \
	exit 1

e2e-install: playwright-install
	MATOMO_URL="$(MATOMO_URL)" \
	MATOMO_ADMIN_USER="$(MATOMO_ADMIN_USER)" \
	MATOMO_ADMIN_PASSWORD="$(MATOMO_ADMIN_PASSWORD)" \
	MATOMO_ADMIN_EMAIL="$(MATOMO_ADMIN_EMAIL)" \
	MATOMO_TOKEN_DESCRIPTION="$(MATOMO_TOKEN_DESCRIPTION)" \
	PYTHONPATH=src $(VENV_PY) -m matomo_bootstrap

e2e-test: deps-e2e
	PYTHONPATH=src $(VENV_PY) -m unittest discover -s tests/e2e -v

e2e-down:
	$(COMPOSE) down -v

e2e: e2e-up e2e-install e2e-test e2e-down

logs:
	$(COMPOSE) logs -f matomo

clean: e2e-down
	rm -rf $(VENV_DIR)

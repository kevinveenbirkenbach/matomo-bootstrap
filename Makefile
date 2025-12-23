PYTHON ?= python3
COMPOSE_FILE := tests/e2e/docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

.PHONY: help e2e-up e2e-install e2e-test e2e-down e2e logs clean

help:
	@echo "Targets:"
	@echo "  e2e-up       Start Matomo + DB for E2E tests"
	@echo "  e2e-install  Run Matomo installation (product code)"
	@echo "  e2e-test     Run E2E tests (unittest)"
	@echo "  e2e-down     Stop and remove E2E containers"
	@echo "  e2e          Full cycle: up → install → test → down"
	@echo "  logs         Show Matomo logs"

e2e-up:
	$(COMPOSE) up -d
	@echo "Waiting for Matomo to answer on http://127.0.0.1:8080/ ..."
	@for i in $$(seq 1 180); do \
		if curl -fsS --max-time 2 http://127.0.0.1:8080/ >/dev/null 2>&1; then \
			echo "Matomo is reachable."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Matomo did not become reachable on host port 8080."; \
	$(COMPOSE) ps; \
	$(COMPOSE) logs --no-color --tail=200 matomo; \
	exit 1

e2e-install:
	PYTHONPATH=src $(PYTHON) -m matomo_bootstrap.install.web_installer

e2e-test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/e2e -v

e2e-down:
	$(COMPOSE) down -v

e2e: e2e-up e2e-install e2e-test e2e-down

logs:
	$(COMPOSE) logs -f matomo

clean: e2e-down

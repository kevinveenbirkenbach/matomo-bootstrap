PYTHON ?= python3

# ----------------------------
# E2E (existing)
# ----------------------------
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

# ----------------------------
# Container image (production-like)
# ----------------------------
IMAGE_NAME ?= ghcr.io/kevinveenbirkenbach/matomo-bootstrap
IMAGE_VERSION ?= 1.0.1

# Optional .env file for container runs
ENV_FILE ?= .env

# ----------------------------
# docker-compose stack (Matomo + MariaDB + Bootstrap)
# ----------------------------
COMPOSE_STACK_FILE ?= docker-compose.yml
COMPOSE_STACK := docker compose -f $(COMPOSE_STACK_FILE)

.PHONY: help \
        venv deps-e2e playwright-install e2e-up e2e-install e2e-test e2e-down e2e logs clean \
        test-integration \
        image-build image-run image-shell image-push image-clean \
        stack-up stack-down stack-logs stack-ps stack-bootstrap stack-rebootstrap stack-clean stack-reset

help:
	@echo "Targets:"
	@echo "  venv               Create local venv in $(VENV_DIR)"
	@echo "  deps-e2e           Install package + E2E deps into venv"
	@echo "  playwright-install Install Chromium for Playwright (inside venv)"
	@echo "  e2e-up             Start Matomo + DB for E2E tests"
	@echo "  e2e-install        Run Matomo bootstrap (product code)"
	@echo "  e2e-test           Run E2E tests (unittest)"
	@echo "  e2e-down           Stop and remove E2E containers"
	@echo "  e2e                Full cycle: up → install → test → down"
	@echo "  logs               Show Matomo logs (E2E compose)"
	@echo "  clean              Stop E2E containers + remove venv"
	@echo "  test-integration   Run integration tests (unittest)"
	@echo ""
	@echo "Container image targets:"
	@echo "  image-build        Build matomo-bootstrap container image"
	@echo "  image-run          Run container bootstrap using $(ENV_FILE) (token-only stdout)"
	@echo "  image-shell        Start interactive shell in container"
	@echo "  image-push         Push image tags ($(IMAGE_VERSION) + latest)"
	@echo "  image-clean        Remove local image tags"
	@echo ""
	@echo "docker-compose stack targets (docker-compose.yml):"
	@echo "  stack-up           Start MariaDB + Matomo (no bootstrap)"
	@echo "  stack-bootstrap    Run one-shot bootstrap (prints token to stdout)"
	@echo "  stack-reset        Full reset: down -v → build → up → bootstrap"
	@echo "  stack-down         Stop stack"
	@echo "  stack-clean        Stop stack and REMOVE volumes (DANGER)"
	@echo "  stack-logs         Follow Matomo logs (stack)"
	@echo "  stack-ps           Show stack status"
	@echo ""
	@echo "Variables:"
	@echo "  E2E: MATOMO_URL, MATOMO_ADMIN_USER, MATOMO_ADMIN_PASSWORD, MATOMO_ADMIN_EMAIL, MATOMO_TOKEN_DESCRIPTION"
	@echo "  IMG: IMAGE_NAME, IMAGE_VERSION, ENV_FILE"
	@echo "  STK: COMPOSE_STACK_FILE"

# ----------------------------
# E2E targets
# ----------------------------

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
	MATOMO_CONTAINER_NAME="e2e-matomo" \
	PYTHONPATH=src $(VENV_PY) -m matomo_bootstrap

e2e-test: deps-e2e
	PYTHONPATH=src $(VENV_PY) -m unittest discover -s tests/e2e -v

e2e-down:
	$(COMPOSE) down -v

e2e-nix:
	docker compose -f tests/e2e/docker-compose.yml up -d
	python3 -m unittest -v tests/e2e/test_bootstrap_nix.py
	docker compose -f tests/e2e/docker-compose.yml down -v

e2e: e2e-up e2e-install e2e-test e2e-down

logs:
	$(COMPOSE) logs -f matomo

clean: e2e-down
	rm -rf $(VENV_DIR)

# ----------------------------
# Integration tests
# ----------------------------

test-integration:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/integration -v

# ----------------------------
# Container image workflow
# ----------------------------

image-build:
	docker build -t $(IMAGE_NAME):$(IMAGE_VERSION) -t $(IMAGE_NAME):latest .

image-run:
	@test -f "$(ENV_FILE)" || (echo "Missing $(ENV_FILE). Create it from env.sample."; exit 1)
	docker run --rm \
	  --env-file "$(ENV_FILE)" \
	  --network host \
	  $(IMAGE_NAME):$(IMAGE_VERSION)

image-shell:
	@test -f "$(ENV_FILE)" || (echo "Missing $(ENV_FILE). Create it from env.sample."; exit 1)
	docker run --rm -it \
	  --env-file "$(ENV_FILE)" \
	  --network host \
	  --entrypoint /bin/bash \
	  $(IMAGE_NAME):$(IMAGE_VERSION)

image-push:
	docker push $(IMAGE_NAME):$(IMAGE_VERSION)
	docker push $(IMAGE_NAME):latest

image-clean:
	docker rmi $(IMAGE_NAME):$(IMAGE_VERSION) $(IMAGE_NAME):latest || true

# ----------------------------
# docker-compose stack workflow
# ----------------------------

## Start MariaDB + Matomo (without bootstrap)
stack-up:
	$(COMPOSE_STACK) up -d db matomo
	@echo "Matomo is starting on http://127.0.0.1:8080"

## Run one-shot bootstrap (prints token to stdout)
stack-bootstrap:
	$(COMPOSE_STACK) run --rm bootstrap

## Re-run bootstrap (forces a fresh one-shot run)
stack-rebootstrap:
	$(COMPOSE_STACK) rm -f bootstrap || true
	$(COMPOSE_STACK) run --rm bootstrap

## Follow Matomo logs (stack)
stack-logs:
	$(COMPOSE_STACK) logs -f matomo

## Show running services (stack)
stack-ps:
	$(COMPOSE_STACK) ps

## Stop stack
stack-down:
	$(COMPOSE_STACK) down

## Stop stack and REMOVE volumes (DANGER)
stack-clean:
	$(COMPOSE_STACK) down -v

## Full reset: down -v → rebuild bootstrap → up → bootstrap
stack-reset:
	$(COMPOSE_STACK) down -v
	$(COMPOSE_STACK) build --no-cache bootstrap
	$(COMPOSE_STACK) up -d db matomo
	@echo "Waiting for Matomo to become reachable..."
	@sleep 10
	$(COMPOSE_STACK) run --rm bootstrap

# matomo-bootstrap

Headless bootstrap tooling for **Matomo**. Automates **first-time installation** and **API token provisioning** for fresh Matomo instances.
---

## Features

- 🚀 **Fully headless Matomo installation**
  - Drives the official Matomo web installer using **Playwright**
  - Automatically skips the installer if Matomo is already installed
- 🔐 **API token provisioning**
  - Creates an **app-specific token** via an authenticated Matomo session
  - Compatible with **Matomo 5.3.x** Docker images
- 🧪 **E2E-tested**
  - Docker-based end-to-end tests included
- ❄️ **First-class Nix support**
  - Flake-based packaging and pinned `flake.lock`
  - Uses `nixpkgs` browsers via `playwright-driver` (no Playwright downloads)
- 🧼 **Token-only stdout contract**
  - **stdout contains only the token** (safe for scripting)
  - Logs go to **stderr**

---

## Requirements

- A running Matomo instance (e.g. via Docker)
- For fresh installs:
  - Chromium (provided by Playwright or by the Playwright base container image)

---

## Installation

### Nix (recommended)

Run directly from the repository:

```bash
nix run github:kevinveenbirkenbach/matomo-bootstrap
```

In Nix mode, browsers are provided via `nixpkgs` (`playwright-driver`) and Playwright downloads are disabled.

---

### Python / pip

Requires **Python ≥ 3.10**:

```bash
pip install matomo-bootstrap
python -m playwright install chromium
```

---

### Docker image (GHCR)

Pull the prebuilt image:

```bash
docker pull ghcr.io/kevinveenbirkenbach/matomo-bootstrap:stable
# or:
docker pull ghcr.io/kevinveenbirkenbach/matomo-bootstrap:latest
```

---

## Usage

### CLI

```bash
matomo-bootstrap \
  --base-url http://127.0.0.1:8080 \
  --admin-user administrator \
  --admin-password 'AdminSecret123!' \
  --admin-email administrator@example.org \
  --token-description my-ci-token
```

On success, the command prints **only the token** to stdout:

```text
6c7a8c2b0e9e4a3c8e1d0c4e8a6b9f21
```

---

### Environment variables

All options can be provided via environment variables:

```bash
export MATOMO_URL=http://127.0.0.1:8080
export MATOMO_ADMIN_USER=administrator
export MATOMO_ADMIN_PASSWORD='AdminSecret123!'
export MATOMO_ADMIN_EMAIL=administrator@example.org
export MATOMO_TOKEN_DESCRIPTION=my-ci-token

matomo-bootstrap
```

---

### Debug mode

Enable verbose logs (**stderr only**):

```bash
matomo-bootstrap --debug
```

---

## Docker Compose integration (one-shot bootstrap)

### Why “one-shot”?

The bootstrap container is meant to:

1. Run once,
2. Print the token to stdout,
3. Exit with code `0`.

You should **not** start it automatically on every `docker compose up`.
Instead, start Matomo normally, then run the bootstrap via `docker compose run`.

The cleanest Compose pattern is to put `bootstrap` behind a **profile**.

---

### Example `docker-compose.yml` (recommended: `profiles`)

```yaml
services:
  db:
    image: mariadb:11
    container_name: matomo-db
    restart: unless-stopped
    environment:
      MARIADB_DATABASE: matomo
      MARIADB_USER: matomo
      MARIADB_PASSWORD: matomo_pw
      MARIADB_ROOT_PASSWORD: root_pw
    volumes:
      - mariadb_data:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", "mariadb-admin ping -uroot -proot_pw --silent"]
      interval: 5s
      timeout: 3s
      retries: 60

  matomo:
    image: matomo:5.3.2
    container_name: matomo
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "${MATOMO_PORT:-8080}:80"
    environment:
      MATOMO_DATABASE_HOST: db
      MATOMO_DATABASE_ADAPTER: mysql
      MATOMO_DATABASE_USERNAME: matomo
      MATOMO_DATABASE_PASSWORD: matomo_pw
      MATOMO_DATABASE_DBNAME: matomo
    volumes:
      - matomo_data:/var/www/html
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 60

  bootstrap:
    # This prevents automatic startup during a normal `docker compose up`
    profiles: ["bootstrap"]

    # Option A: use the published image (recommended)
    image: ghcr.io/kevinveenbirkenbach/matomo-bootstrap:1.0.1

    # Option B: build locally from the repository checkout
    # build:
    #   context: .
    #   dockerfile: Dockerfile
    # image: matomo-bootstrap:local

    container_name: matomo-bootstrap
    depends_on:
      matomo:
        condition: service_started
    environment:
      # inside the compose network, Matomo is reachable via the service name
      MATOMO_URL: "http://matomo"

      MATOMO_ADMIN_USER: "administrator"
      MATOMO_ADMIN_PASSWORD: "AdminSecret123!"
      MATOMO_ADMIN_EMAIL: "administrator@example.org"
      MATOMO_TOKEN_DESCRIPTION: "docker-compose-bootstrap"

      # Values used by the recorded installer flow
      MATOMO_SITE_NAME: "Matomo (docker-compose)"
      MATOMO_SITE_URL: "http://127.0.0.1:${MATOMO_PORT:-8080}"
      MATOMO_TIMEZONE: "Germany - Berlin"

      # Optional stability knobs
      MATOMO_TIMEOUT: "30"
      MATOMO_PLAYWRIGHT_HEADLESS: "1"
      MATOMO_PLAYWRIGHT_NAV_TIMEOUT_MS: "60000"
      MATOMO_PLAYWRIGHT_SLOWMO_MS: "0"

    restart: "no"

volumes:
  mariadb_data:
  matomo_data:
```

---

### Commands

Start DB + Matomo **without** bootstrap:

```bash
docker compose up -d db matomo
```

Run bootstrap once (prints token to stdout):

```bash
docker compose --profile bootstrap run --rm bootstrap
```

Re-run bootstrap (creates a new token by default):

```bash
docker compose --profile bootstrap run --rm bootstrap
```

---

## Idempotency / avoiding new tokens on every run

By default, `UsersManager.createAppSpecificTokenAuth` creates a new token each time.

If you want strictly idempotent runs in automation, you can provide an existing token
and make the bootstrap return it instead of creating a new one:

```bash
export MATOMO_BOOTSTRAP_TOKEN_AUTH="0123456789abcdef..."
matomo-bootstrap
```

> This is useful for CI re-runs or configuration management tools.

---

## How it works

1. **Reachability check**

   * waits until Matomo responds via HTTP (any status is considered “reachable”)
2. **Installation (if needed)**

   * uses a recorded Playwright flow to complete the Matomo web installer
3. **Authentication**

   * logs in using Matomo’s `Login.logme` controller (cookie session)
4. **Token creation**

   * calls `UsersManager.createAppSpecificTokenAuth`
5. **Output**

   * prints the token to stdout (token-only contract)

---

## End-to-end tests

Run the full E2E cycle locally:

```bash
make e2e
```

This will:

1. Start Matomo + MariaDB via Docker
2. Install Matomo headlessly
3. Create an API token
4. Validate the token via the Matomo API
5. Tear everything down again

---

## Author

**Kevin Veen-Birkenbach**
[https://www.veen.world/](https://www.veen.world/)

---

## License

MIT — see [LICENSE](LICENSE)

# matomo-bootstrap
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-blue?logo=github)](https://github.com/sponsors/kevinveenbirkenbach) [![Patreon](https://img.shields.io/badge/Support-Patreon-orange?logo=patreon)](https://www.patreon.com/c/kevinveenbirkenbach) [![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20Coffee-Funding-yellow?logo=buymeacoffee)](https://buymeacoffee.com/kevinveenbirkenbach) [![PayPal](https://img.shields.io/badge/Donate-PayPal-blue?logo=paypal)](https://s.veen.world/paypaldonate)


Headless bootstrap tooling for **Matomo**
Automates **installation** (via recorded Playwright flow) and **API token provisioning** for fresh Matomo instances.

This tool is designed for **CI, containers, and reproducible environments**, where no interactive browser access is available.

---

## Features

* 🚀 **Fully headless Matomo installation**

  * Drives the official Matomo web installer using **Playwright**
  * Automatically skips installation if Matomo is already installed
* 🔐 **API token provisioning**

  * Creates an *app-specific token* via authenticated Matomo session
  * Compatible with Matomo 5.3.x Docker images
* 🧪 **E2E-tested**

  * Docker-based end-to-end tests included
* ❄️ **First-class Nix support**

  * Flake-based packaging
  * Reproducible CLI and dev environments
* 🐍 **Standard Python CLI**

  * Installable via `pip`
  * Clean stdout (token only), logs on stderr

---

## Requirements

* A running Matomo instance (e.g. Docker)
* For fresh installs:

  * Chromium (managed automatically by Playwright)

---

## Installation

### Using **Nix** (recommended)

If you use **Nix** with flakes:

```bash
nix run github:kevinveenbirkenbach/matomo-bootstrap
```

Install Playwright’s Chromium browser (one-time):

```bash
nix run github:kevinveenbirkenbach/matomo-bootstrap#matomo-bootstrap-playwright-install
```

This installs Chromium into the user cache used by Playwright.

---

### Using **Python / pip**

Requires **Python ≥ 3.10**

```bash
pip install matomo-bootstrap
```

Install Chromium for Playwright:

```bash
python -m playwright install chromium
```

---

## Usage

### CLI

```bash
matomo-bootstrap \
  --base-url http://127.0.0.1:8080 \
  --admin-user administrator \
  --admin-password AdminSecret123! \
  --admin-email administrator@example.org
```

On success, the command prints **only the API token** to stdout:

```text
6c7a8c2b0e9e4a3c8e1d0c4e8a6b9f21
```

---

### Environment Variables

All options can be provided via environment variables:

```bash
export MATOMO_URL=http://127.0.0.1:8080
export MATOMO_ADMIN_USER=administrator
export MATOMO_ADMIN_PASSWORD=AdminSecret123!
export MATOMO_ADMIN_EMAIL=administrator@example.org
export MATOMO_TOKEN_DESCRIPTION=my-ci-token

matomo-bootstrap
```

---

### Debug Mode

Enable verbose logs (stderr only):

```bash
matomo-bootstrap --debug
```

---

## How It Works

1. **Reachability check**

   * Waits until Matomo responds over HTTP (any status)
2. **Installation (if needed)**

   * Uses a recorded Playwright flow to complete the Matomo web installer
3. **Authentication**

   * Logs in using the `Login.logme` controller
4. **Token creation**

   * Calls `UsersManager.createAppSpecificTokenAuth`
5. **Output**

   * Prints the token to stdout (safe for scripting)

---

## End-to-End Tests

Run the full E2E cycle locally:

```bash
make e2e
```

This will:

1. Start Matomo + MariaDB via Docker
2. Install Matomo headlessly
3. Create an API token
4. Validate the token via Matomo API
5. Tear everything down again

---

## Project Status

* ✔ Stable for CI / automation
* ✔ Tested against Matomo 5.3.x Docker images
* ⚠ Installer flow is UI-recorded (robust, but may need updates for future Matomo UI changes)

---

## Author

**Kevin Veen-Birkenbach**
🌐 [https://www.veen.world/](https://www.veen.world/)

---

## License

MIT License
See [LICENSE](LICENSE)

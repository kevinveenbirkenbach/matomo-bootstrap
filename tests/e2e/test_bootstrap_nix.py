import os
import subprocess
import unittest


MATOMO_URL = os.environ.get("MATOMO_URL", "http://127.0.0.1:8080")
ADMIN_USER = os.environ.get("MATOMO_ADMIN_USER", "administrator")
ADMIN_PASSWORD = os.environ.get("MATOMO_ADMIN_PASSWORD", "AdminSecret123!")
ADMIN_EMAIL = os.environ.get("MATOMO_ADMIN_EMAIL", "administrator@example.org")


class TestMatomoBootstrapE2ENix(unittest.TestCase):
    def test_bootstrap_creates_api_token_via_nix(self) -> None:
        script = f"""set -euo pipefail

export NIX_CONFIG='experimental-features = nix-command flakes'
export TERM='xterm'

# Make sure we have a writable HOME (compose already sets HOME=/tmp/home)
mkdir -p "$HOME" "$HOME/.cache" "$HOME/.config" "$HOME/.local/share"

# IMPORTANT:
# Nix flakes read the local repo as git+file:///work.
# Git refuses if the repo is not owned by the current user (root in the container).
# Mark it as safe explicitly.
git config --global --add safe.directory /work

# 1) Install Playwright Chromium (cached in the container environment)
nix run --no-write-lock-file -L .#matomo-bootstrap-playwright-install

# 2) Run bootstrap (must print ONLY token)
nix run --no-write-lock-file -L .#matomo-bootstrap -- \\
  --base-url '{MATOMO_URL}' \\
  --admin-user '{ADMIN_USER}' \\
  --admin-password '{ADMIN_PASSWORD}' \\
  --admin-email '{ADMIN_EMAIL}' \\
  --token-description 'e2e-test-token-nix'
"""

        cmd = [
            "docker",
            "compose",
            "-f",
            "tests/e2e/docker-compose.yml",
            "exec",
            "-T",
            "nix",
            "sh",
            "-lc",
            script,
        ]

        token = subprocess.check_output(cmd).decode().strip()
        self.assertRegex(token, r"^[a-f0-9]{32,64}$")


if __name__ == "__main__":
    unittest.main()

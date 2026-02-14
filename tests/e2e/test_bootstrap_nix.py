import os
import re
import subprocess
import textwrap
import unittest


MATOMO_URL = os.environ.get("MATOMO_URL", "http://127.0.0.1:8080")
ADMIN_USER = os.environ.get("MATOMO_ADMIN_USER", "administrator")
ADMIN_PASSWORD = os.environ.get("MATOMO_ADMIN_PASSWORD", "AdminSecret123!")
ADMIN_EMAIL = os.environ.get("MATOMO_ADMIN_EMAIL", "administrator@example.org")
TOKEN_RE = re.compile(r"^[a-f0-9]{32,64}$")


class TestMatomoBootstrapE2ENix(unittest.TestCase):
    def test_bootstrap_creates_api_token_via_nix(self) -> None:
        script = textwrap.dedent(
            f"""\
set -eux

export NIX_CONFIG='experimental-features = nix-command flakes'
export TERM='xterm'
# Improve CI resilience for slow installer pages.
export MATOMO_INSTALLER_READY_TIMEOUT_S="${{MATOMO_INSTALLER_READY_TIMEOUT_S:-240}}"
export MATOMO_INSTALLER_STEP_TIMEOUT_S="${{MATOMO_INSTALLER_STEP_TIMEOUT_S:-45}}"
export MATOMO_INSTALLER_STEP_DEADLINE_S="${{MATOMO_INSTALLER_STEP_DEADLINE_S:-240}}"
export MATOMO_INSTALLER_TABLES_CREATION_TIMEOUT_S="${{MATOMO_INSTALLER_TABLES_CREATION_TIMEOUT_S:-240}}"
export MATOMO_INSTALLER_TABLES_ERASE_TIMEOUT_S="${{MATOMO_INSTALLER_TABLES_ERASE_TIMEOUT_S:-180}}"
export MATOMO_INSTALLER_DEBUG_DIR="${{MATOMO_INSTALLER_DEBUG_DIR:-/tmp/matomo-bootstrap}}"

# Make sure we have a writable HOME (compose already sets HOME=/tmp/home)
mkdir -p "$HOME" "$HOME/.cache" "$HOME/.config" "$HOME/.local/share"

# IMPORTANT:
# Nix flakes read the local repo as git+file:///work.
# Git refuses if the repo is not owned by the current user (root in the container).
# Mark it as safe explicitly.
git config --global --add safe.directory /work

# Preflight checks to surface "command not executable" failures (exit 126) clearly.
playwright_app="$(nix eval --raw .#apps.x86_64-linux.matomo-bootstrap-playwright-install.program)"
bootstrap_app="$(nix eval --raw .#apps.x86_64-linux.matomo-bootstrap.program)"
if [ -e "$playwright_app" ]; then
  test -x "$playwright_app"
fi
if [ -e "$bootstrap_app" ]; then
  test -x "$bootstrap_app"
fi

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
        )

        cmd = [
            "docker",
            "compose",
            "-f",
            "tests/e2e/docker-compose.yml",
            # Use `run` instead of `exec` to avoid runtime-specific
            # `/etc/group` lookup issues seen with nix image + compose exec.
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "nix",
            "sh",
            "-lc",
            script,
        ]

        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            self.fail(
                "nix bootstrap command failed\n"
                f"exit={result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        stdout_lines = [
            line.strip() for line in result.stdout.splitlines() if line.strip()
        ]
        token = stdout_lines[-1] if stdout_lines else ""
        self.assertRegex(
            token,
            TOKEN_RE,
            f"Expected token on last stdout line, got stdout={result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()

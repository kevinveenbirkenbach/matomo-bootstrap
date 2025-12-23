import subprocess
import time
import unittest


COMPOSE_FILE = "tests/e2e/docker-compose.yml"


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def wait_http_any(url: str, timeout_s: int = 180) -> None:
    # "any HTTP code" reachability via curl:
    # curl exits 0 on 2xx, non-zero on 4xx/5xx; so we just wait for any response code != 000
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        p = run(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--max-time",
                "2",
                url,
            ]
        )
        code = (p.stdout or "").strip()
        if code and code != "000":
            return
        time.sleep(1)
    raise RuntimeError(f"Matomo did not become reachable: {url}")


class TestComposeBootstrapExit0(unittest.TestCase):
    def test_bootstrap_exits_zero(self) -> None:
        compose = ["docker", "compose", "-f", COMPOSE_FILE]

        try:
            # clean slate
            run(compose + ["down", "-v"])

            # start db + matomo (+ nix if present)
            up = run(compose + ["up", "-d"])
            self.assertEqual(
                up.returncode,
                0,
                msg=f"compose up failed\nSTDOUT:\n{up.stdout}\nSTDERR:\n{up.stderr}",
            )

            # wait for host-published matomo port
            wait_http_any("http://127.0.0.1:8080/", timeout_s=180)

            # IMPORTANT:
            # Run bootstrap via Nix container already defined in tests/e2e/docker-compose.yml
            # (this avoids host python/venv completely).
            script = r"""set -euo pipefail

export NIX_CONFIG='experimental-features = nix-command flakes'
export TERM='xterm'
mkdir -p "$HOME" "$HOME/.cache" "$HOME/.config" "$HOME/.local/share"

# Mark repo safe (root in container)
git config --global --add safe.directory /work

# Install browsers (cached in container volumes)
nix run --no-write-lock-file -L .#matomo-bootstrap-playwright-install >/dev/null

# Run bootstrap (must exit 0; stdout should be token-only)
nix run --no-write-lock-file -L .#matomo-bootstrap -- \
  --base-url 'http://127.0.0.1:8080' \
  --admin-user 'administrator' \
  --admin-password 'AdminSecret123!' \
  --admin-email 'administrator@example.org' \
  --token-description 'e2e-compose-exit0'
"""

            boot = run(compose + ["exec", "-T", "nix", "sh", "-lc", script])
            self.assertEqual(
                boot.returncode,
                0,
                msg=f"bootstrap failed\nSTDOUT:\n{boot.stdout}\nSTDERR:\n{boot.stderr}",
            )

            token = (boot.stdout or "").strip()
            self.assertRegex(
                token,
                r"^[a-f0-9]{32,64}$",
                msg=f"expected token on stdout; got: {token!r}\nSTDERR:\n{boot.stderr}",
            )

        finally:
            run(compose + ["down", "-v"])


if __name__ == "__main__":
    unittest.main()

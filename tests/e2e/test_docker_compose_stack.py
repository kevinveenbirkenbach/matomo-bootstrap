import json
import os
import re
import subprocess
import time
import unittest
import urllib.request


COMPOSE_FILE = os.environ.get("MATOMO_STACK_COMPOSE_FILE", "docker-compose.yml")
MATOMO_HOST_URL = os.environ.get("MATOMO_STACK_URL", "http://127.0.0.1:8080")

# How long we wait for Matomo HTTP to respond at all (seconds)
WAIT_TIMEOUT_SECONDS = int(os.environ.get("MATOMO_STACK_WAIT_TIMEOUT", "180"))


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _compose_cmd(*args: str) -> list[str]:
    return ["docker", "compose", "-f", COMPOSE_FILE, *args]


def _wait_for_http_any_status(url: str, timeout_s: int) -> None:
    """
    Consider the service "up" once the HTTP server answers anything.
    urllib raises HTTPError on 4xx/5xx, but that's still "reachable".
    """
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                _ = resp.read(64)
            return
        except Exception as exc:  # includes HTTPError
            last_exc = exc
            time.sleep(1)

    raise RuntimeError(f"Matomo did not become reachable at {url} ({last_exc})")


class TestRootDockerComposeStack(unittest.TestCase):
    """
    E2E test for repository root docker-compose.yml:

    1) docker compose down -v
    2) docker compose build bootstrap
    3) docker compose up -d db matomo
    4) wait for Matomo HTTP on host port (default 8080)
    5) docker compose run --rm bootstrap -> token on stdout
    6) validate token via Matomo API call
    7) docker compose down -v (cleanup)
    """

    def setUp(self) -> None:
        # Always start from a clean slate (also clears volumes)
        _run(_compose_cmd("down", "-v"), check=False)

    def tearDown(self) -> None:
        # Cleanup even if assertions fail
        _run(_compose_cmd("down", "-v"), check=False)

    def test_root_docker_compose_yml_stack_bootstraps_and_token_works(self) -> None:
        # Build bootstrap image from Dockerfile (as defined in docker-compose.yml)
        build = _run(_compose_cmd("build", "bootstrap"), check=True)
        self.assertEqual(build.returncode, 0, build.stderr)

        # Start db + matomo (bootstrap is one-shot and started via "run")
        up = _run(_compose_cmd("up", "-d", "db", "matomo"), check=True)
        self.assertEqual(up.returncode, 0, up.stderr)

        # Wait until Matomo answers on the published port
        _wait_for_http_any_status(MATOMO_HOST_URL + "/", WAIT_TIMEOUT_SECONDS)

        # Run bootstrap: it should print ONLY the token to stdout
        boot = _run(_compose_cmd("run", "--rm", "bootstrap"), check=True)

        token = (boot.stdout or "").strip()
        self.assertRegex(
            token,
            r"^[a-f0-9]{32,64}$",
            f"Expected token_auth on stdout, got stdout={boot.stdout!r} stderr={boot.stderr!r}",
        )

        # Verify token works against Matomo API
        api_url = (
            f"{MATOMO_HOST_URL}/index.php"
            f"?module=API&method=SitesManager.getSitesWithAtLeastViewAccess"
            f"&format=json&token_auth={token}"
        )
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()

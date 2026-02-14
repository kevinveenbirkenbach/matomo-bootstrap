import json
import os
import subprocess
import time
import unittest
import urllib.request


COMPOSE_FILE = os.environ.get("MATOMO_STACK_COMPOSE_FILE", "docker-compose.yml")
SLOW_COMPOSE_FILE = os.environ.get(
    "MATOMO_STACK_SLOW_COMPOSE_FILE", "tests/e2e/docker-compose.slow.yml"
)

# Pick a non-default port to avoid collisions with other CI stacks that use 8080
MATOMO_PORT = os.environ.get("MATOMO_PORT", "18080")
MATOMO_HOST_URL = os.environ.get("MATOMO_STACK_URL", f"http://127.0.0.1:{MATOMO_PORT}")
MATOMO_SLOW_PORT = os.environ.get("MATOMO_SLOW_PORT", "18081")
MATOMO_SLOW_HOST_URL = os.environ.get(
    "MATOMO_SLOW_STACK_URL", f"http://127.0.0.1:{MATOMO_SLOW_PORT}"
)

# How long we wait for Matomo HTTP to respond at all (seconds)
WAIT_TIMEOUT_SECONDS = int(os.environ.get("MATOMO_STACK_WAIT_TIMEOUT", "180"))
SLOW_WAIT_TIMEOUT_SECONDS = int(os.environ.get("MATOMO_SLOW_STACK_WAIT_TIMEOUT", "420"))


def _run(
    cmd: list[str],
    *,
    check: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        env={**os.environ, **(extra_env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _compose_cmd(*args: str, compose_files: list[str] | None = None) -> list[str]:
    files = compose_files or [COMPOSE_FILE]
    cmd = ["docker", "compose"]
    for compose_file in files:
        cmd.extend(["-f", compose_file])
    cmd.extend(args)
    return cmd


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


def _extract_service_block(compose_config: str, service_name: str) -> str:
    lines = compose_config.splitlines()
    marker = f"  {service_name}:"
    start = -1
    for idx, line in enumerate(lines):
        if line == marker:
            start = idx
            break
    if start < 0:
        raise AssertionError(
            f"service block not found in compose config: {service_name}"
        )

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        line = lines[idx]
        if line.startswith("  ") and not line.startswith("    "):
            end = idx
            break

    return "\n".join(lines[start:end])


class TestRootDockerComposeStack(unittest.TestCase):
    """
    E2E test for repository root docker-compose.yml:

    1) docker compose down -v
    2) docker compose build bootstrap
    3) docker compose up -d db matomo
    4) wait for Matomo HTTP on host port (default 8080, overridden here)
    5) docker compose run --rm bootstrap -> token on stdout
    6) validate token via Matomo API call
    7) docker compose down -v (cleanup)
    """

    def setUp(self) -> None:
        # Always start from a clean slate (also clears volumes)
        _run(
            _compose_cmd("down", "-v"),
            check=False,
            extra_env={"MATOMO_PORT": MATOMO_PORT},
        )

    def tearDown(self) -> None:
        # Cleanup even if assertions fail
        _run(
            _compose_cmd("down", "-v"),
            check=False,
            extra_env={"MATOMO_PORT": MATOMO_PORT},
        )

    def _assert_stack_bootstraps_and_token_works(
        self,
        *,
        compose_files: list[str],
        matomo_port: str,
        matomo_host_url: str,
        wait_timeout_seconds: int,
        bootstrap_retries: int = 2,
    ) -> None:
        build = _run(
            _compose_cmd("build", "bootstrap", compose_files=compose_files),
            check=False,
            extra_env={"MATOMO_PORT": matomo_port},
        )
        self.assertEqual(
            build.returncode,
            0,
            f"compose build failed\nstdout:\n{build.stdout}\nstderr:\n{build.stderr}",
        )

        up = _run(
            _compose_cmd("up", "-d", "db", "matomo", compose_files=compose_files),
            check=False,
            extra_env={"MATOMO_PORT": matomo_port},
        )
        self.assertEqual(
            up.returncode,
            0,
            f"compose up failed\nstdout:\n{up.stdout}\nstderr:\n{up.stderr}",
        )

        _wait_for_http_any_status(matomo_host_url + "/", wait_timeout_seconds)

        boot_attempts: list[subprocess.CompletedProcess] = []
        for _ in range(bootstrap_retries):
            boot = _run(
                _compose_cmd("run", "--rm", "bootstrap", compose_files=compose_files),
                check=False,
                extra_env={"MATOMO_PORT": matomo_port},
            )
            boot_attempts.append(boot)
            if boot.returncode == 0:
                break
            time.sleep(5)

        if boot.returncode != 0:
            matomo_logs = _run(
                _compose_cmd(
                    "logs",
                    "--no-color",
                    "--tail=250",
                    "matomo",
                    compose_files=compose_files,
                ),
                check=False,
                extra_env={"MATOMO_PORT": matomo_port},
            )
            db_logs = _run(
                _compose_cmd(
                    "logs",
                    "--no-color",
                    "--tail=200",
                    "db",
                    compose_files=compose_files,
                ),
                check=False,
                extra_env={"MATOMO_PORT": matomo_port},
            )
            attempts_dump = "\n\n".join(
                [
                    (
                        f"[attempt {i}] rc={attempt.returncode}\n"
                        f"stdout:\n{attempt.stdout}\n"
                        f"stderr:\n{attempt.stderr}"
                    )
                    for i, attempt in enumerate(boot_attempts, 1)
                ]
            )
            self.fail(
                "bootstrap container failed after retry.\n"
                f"{attempts_dump}\n\n"
                f"[matomo logs]\n{matomo_logs.stdout}\n{matomo_logs.stderr}\n\n"
                f"[db logs]\n{db_logs.stdout}\n{db_logs.stderr}"
            )

        token = (boot.stdout or "").strip()
        self.assertRegex(
            token,
            r"^[a-f0-9]{32,64}$",
            f"Expected token_auth on stdout, got stdout={boot.stdout!r} stderr={boot.stderr!r}",
        )

        api_url = (
            f"{matomo_host_url}/index.php"
            f"?module=API&method=SitesManager.getSitesWithAtLeastViewAccess"
            f"&format=json&token_auth={token}"
        )
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        self.assertIsInstance(data, list)

    def test_root_docker_compose_yml_stack_bootstraps_and_token_works(self) -> None:
        self._assert_stack_bootstraps_and_token_works(
            compose_files=[COMPOSE_FILE],
            matomo_port=MATOMO_PORT,
            matomo_host_url=MATOMO_HOST_URL,
            wait_timeout_seconds=WAIT_TIMEOUT_SECONDS,
            bootstrap_retries=2,
        )

    def test_root_docker_compose_yml_stack_bootstraps_under_resource_pressure(
        self,
    ) -> None:
        self._assert_stack_bootstraps_and_token_works(
            compose_files=[COMPOSE_FILE, SLOW_COMPOSE_FILE],
            matomo_port=MATOMO_SLOW_PORT,
            matomo_host_url=MATOMO_SLOW_HOST_URL,
            wait_timeout_seconds=SLOW_WAIT_TIMEOUT_SECONDS,
            bootstrap_retries=3,
        )


class TestRootDockerComposeDefinition(unittest.TestCase):
    def test_bootstrap_service_waits_for_healthy_matomo_and_has_readiness_knobs(
        self,
    ) -> None:
        cfg = _run(
            _compose_cmd("config"),
            check=True,
            extra_env={"MATOMO_PORT": MATOMO_PORT},
        )
        self.assertEqual(cfg.returncode, 0, cfg.stderr)

        bootstrap_block = _extract_service_block(cfg.stdout, "bootstrap")

        self.assertIn("depends_on:", bootstrap_block)
        self.assertIn("matomo:", bootstrap_block)
        self.assertIn("condition: service_healthy", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_READY_TIMEOUT_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_STEP_TIMEOUT_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_STEP_DEADLINE_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_TABLES_CREATION_TIMEOUT_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_TABLES_ERASE_TIMEOUT_S:", bootstrap_block)

        matomo_block = _extract_service_block(cfg.stdout, "matomo")
        self.assertIn("healthcheck:", matomo_block)
        self.assertIn("curl -fsS http://127.0.0.1/ >/dev/null || exit 1", matomo_block)

    def test_slow_override_sets_tight_resources_and_longer_timeouts(self) -> None:
        cfg = _run(
            _compose_cmd("config", compose_files=[COMPOSE_FILE, SLOW_COMPOSE_FILE]),
            check=True,
            extra_env={"MATOMO_PORT": MATOMO_SLOW_PORT},
        )
        self.assertEqual(cfg.returncode, 0, cfg.stderr)

        matomo_block = _extract_service_block(cfg.stdout, "matomo")
        self.assertIn("cpus: 0.35", matomo_block)
        self.assertIn('mem_limit: "402653184"', matomo_block)
        self.assertIn("start_period: 2m0s", matomo_block)

        db_block = _extract_service_block(cfg.stdout, "db")
        self.assertIn("cpus: 0.35", db_block)
        self.assertIn('mem_limit: "335544320"', db_block)

        bootstrap_block = _extract_service_block(cfg.stdout, "bootstrap")
        self.assertIn("MATOMO_INSTALLER_STEP_TIMEOUT_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_STEP_DEADLINE_S:", bootstrap_block)
        self.assertIn("MATOMO_INSTALLER_READY_TIMEOUT_S:", bootstrap_block)


if __name__ == "__main__":
    unittest.main()

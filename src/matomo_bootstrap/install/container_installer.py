import subprocess
import time
from typing import Optional


MATOMO_ROOT = "/var/www/html"
CONSOLE = f"{MATOMO_ROOT}/console"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def _container_state(container_name: str) -> str:
    res = _run(["docker", "inspect", "-f", "{{.State.Status}}", container_name])
    return (res.stdout or "").strip()


def _wait_container_running(container_name: str, timeout: int = 60) -> None:
    last = ""
    for _ in range(timeout):
        state = _container_state(container_name)
        last = state
        if state == "running":
            return
        time.sleep(1)
    raise RuntimeError(f"Container '{container_name}' did not become running (last state: {last})")


def _exec(container_name: str, argv: list[str]) -> subprocess.CompletedProcess:
    return _run(["docker", "exec", container_name, *argv])


def _sh(container_name: str, script: str) -> subprocess.CompletedProcess:
    # Use sh -lc so PATH + cwd behave more like interactive container sessions
    return _exec(container_name, ["sh", "-lc", script])


def _console_exists(container_name: str) -> bool:
    res = _sh(container_name, f"test -x {CONSOLE} && echo yes || echo no")
    return (res.stdout or "").strip() == "yes"


def _is_installed(container_name: str) -> bool:
    res = _sh(container_name, f"test -f {MATOMO_ROOT}/config/config.ini.php && echo yes || echo no")
    return (res.stdout or "").strip() == "yes"


def _console_list(container_name: str) -> str:
    # --no-ansi for stable parsing
    res = _sh(container_name, f"{CONSOLE} list --no-ansi 2>/dev/null || true")
    return (res.stdout or "") + "\n" + (res.stderr or "")


def _has_command(console_list_output: str, command: str) -> bool:
    # cheap but robust enough
    return f" {command} " in console_list_output or f"\n{command}\n" in console_list_output or command in console_list_output


def ensure_installed_via_console(
    *,
    container_name: str,
    admin_user: str,
    admin_password: str,
    admin_email: str,
    debug: bool = False,
) -> None:
    """
    Ensure Matomo is installed using the container's console if possible.
    If no known install command exists, we do NOT guess: we raise with diagnostics.
    """
    _wait_container_running(container_name, timeout=90)

    if _is_installed(container_name):
        if debug:
            print("[install] Matomo already installed (config.ini.php exists).")
        return

    if not _console_exists(container_name):
        raise RuntimeError(f"Matomo console not found/executable at {CONSOLE} inside container '{container_name}'.")

    listing = _console_list(container_name)
    if debug:
        print("[install] Matomo console list obtained.")

    # Matomo versions differ; we discover what exists.
    # Historically: core:install. Your earlier log showed it does NOT exist in 5.3.2 image.
    # Therefore we refuse to guess and provide the list in the exception.
    if _has_command(listing, "core:install"):
        # If this ever exists, use it.
        cmd = (
            f"{CONSOLE} core:install --no-ansi "
            f"--database-host=db "
            f"--database-username=matomo "
            f"--database-password=matomo_pw "
            f"--database-name=matomo "
            f"--login={admin_user} "
            f"--password={admin_password} "
            f"--email={admin_email} "
            f"--url=http://localhost "
        )
        res = _sh(container_name, cmd)
        if res.returncode != 0:
            raise RuntimeError(f"Matomo CLI install failed.\nexit={res.returncode}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}")
        return

    # No install command -> fail with diagnostics (don’t keep burning time).
    raise RuntimeError(
        "Matomo is not installed yet, but no supported CLI install command was found in this image.\n"
        "This Matomo image likely expects the web installer.\n"
        "\n[console list]\n"
        f"{listing}\n"
    )

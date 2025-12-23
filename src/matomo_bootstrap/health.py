import urllib.request
from .errors import MatomoNotReadyError


def assert_matomo_ready(base_url: str, timeout: int = 10) -> None:
    try:
        with urllib.request.urlopen(base_url, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise MatomoNotReadyError(f"Matomo not reachable: {exc}") from exc

    if "Matomo" not in html and "piwik" not in html.lower():
        raise MatomoNotReadyError("Matomo UI not detected at base URL")

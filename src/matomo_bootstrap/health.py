from __future__ import annotations

import urllib.request

from .errors import MatomoNotReadyError


def assert_matomo_ready(base_url: str, timeout: int = 10) -> None:
    try:
        with urllib.request.urlopen(base_url, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise MatomoNotReadyError(f"Matomo not reachable: {exc}") from exc

    lower = html.lower()
    if "matomo" not in lower and "piwik" not in lower:
        raise MatomoNotReadyError("Matomo UI not detected at base URL")

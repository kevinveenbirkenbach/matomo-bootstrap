from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error

from .errors import MatomoNotReadyError, TokenCreationError
from .http import HttpClient


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _try_json(body: str) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise TokenCreationError(f"Invalid JSON from Matomo API: {body[:400]}") from exc


def _dbg(msg: str, enabled: bool) -> None:
    if enabled:
        # Keep stdout clean (tests expect only token on stdout).
        print(msg, file=sys.stderr)


class MatomoApi:
    def __init__(self, *, client: HttpClient, debug: bool = False):
        self.client = client
        self.debug = debug

    def assert_ready(self, timeout: int = 10) -> None:
        """
        Minimal readiness check: Matomo UI should be reachable and look like Matomo.
        """
        try:
            status, body = self.client.get("/", {})
        except Exception as exc:  # pragma: no cover
            raise MatomoNotReadyError(f"Matomo not reachable: {exc}") from exc

        _dbg(f"[ready] GET / -> HTTP {status}", self.debug)

        html = (body or "").lower()
        if "matomo" not in html and "piwik" not in html:
            raise MatomoNotReadyError("Matomo UI not detected at base URL")

    def login_via_logme(self, admin_user: str, admin_password: str) -> None:
        """
        Create an authenticated Matomo session (cookie jar) using Login controller.
        Matomo accepts md5 hashed password in `password` parameter for action=logme.
        """
        md5_password = _md5(admin_password)
        try:
            status, body = self.client.get(
                "/index.php",
                {
                    "module": "Login",
                    "action": "logme",
                    "login": admin_user,
                    "password": md5_password,
                },
            )
            _dbg(f"[auth] logme HTTP {status} body[:120]={body[:120]!r}", self.debug)
        except urllib.error.HTTPError as exc:
            # Even 4xx/5xx can still set cookies; continue and let the API call validate.
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            _dbg(
                f"[auth] logme HTTPError {exc.code} body[:120]={err_body[:120]!r}",
                self.debug,
            )

    def create_app_specific_token(
        self,
        *,
        admin_user: str,
        admin_password: str,
        description: str,
    ) -> str:
        """
        Create an app-specific token using an authenticated session (cookies),
        not UsersManager.getTokenAuth (not available in Matomo 5.3.x images).
        """
        env_token = os.environ.get("MATOMO_BOOTSTRAP_TOKEN_AUTH")
        if env_token:
            _dbg(
                "[auth] Using MATOMO_BOOTSTRAP_TOKEN_AUTH from environment.", self.debug
            )
            return env_token

        self.login_via_logme(admin_user, admin_password)

        status, body = self.client.post(
            "/index.php",
            {
                "module": "API",
                "method": "UsersManager.createAppSpecificTokenAuth",
                "userLogin": admin_user,
                "passwordConfirmation": admin_password,
                "description": description,
                "format": "json",
            },
        )

        _dbg(
            f"[auth] createAppSpecificTokenAuth HTTP {status} body[:200]={body[:200]!r}",
            self.debug,
        )

        if status != 200:
            raise TokenCreationError(
                f"HTTP {status} during token creation: {body[:400]}"
            )

        data = _try_json(body)
        token = data.get("value") if isinstance(data, dict) else None
        if not token:
            raise TokenCreationError(f"Unexpected response from token creation: {data}")

        return str(token)

import hashlib
import json
import os
import sys
import urllib.error

from .errors import TokenCreationError
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
        # IMPORTANT: keep stdout clean (tests expect only token on stdout)
        print(msg, file=sys.stderr)


def _login_via_logme(client: HttpClient, admin_user: str, admin_password: str, debug: bool) -> None:
    """
    Create an authenticated Matomo session (cookie jar) using the classic Login controller.

    Matomo accepts the md5 hashed password in the `password` parameter for action=logme.
    We rely on urllib's opener to follow redirects and store cookies.
    """
    md5_password = _md5(admin_password)

    try:
        status, body = client.get(
            "/index.php",
            {
                "module": "Login",
                "action": "logme",
                "login": admin_user,
                "password": md5_password,
            },
        )
        _dbg(f"[auth] login via logme returned HTTP {status} (body preview: {body[:120]!r})", debug)
    except urllib.error.HTTPError as exc:
        # Even 4xx/5xx can still set cookies; continue and let the API call validate.
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        _dbg(f"[auth] login via logme raised HTTPError {exc.code} (body preview: {err_body[:120]!r})", debug)


def create_app_token_via_session(
    *,
    client: HttpClient,
    admin_user: str,
    admin_password: str,
    description: str,
    debug: bool = False,
) -> str:
    """
    Create an app-specific token using an authenticated SESSION (cookies),
    not via UsersManager.getTokenAuth (removed/not available in Matomo 5.3.x images).

    If MATOMO_BOOTSTRAP_TOKEN_AUTH is already set, we return it.
    """
    env_token = os.environ.get("MATOMO_BOOTSTRAP_TOKEN_AUTH")
    if env_token:
        _dbg("[auth] Using MATOMO_BOOTSTRAP_TOKEN_AUTH from environment.", debug)
        return env_token

    # 1) Establish logged-in session
    _login_via_logme(client, admin_user, admin_password, debug=debug)

    # 2) Use the session cookie to create an app specific token
    status, body = client.post(
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

    _dbg(f"[auth] createAppSpecificTokenAuth HTTP {status} body[:200]={body[:200]!r}", debug)

    if status != 200:
        raise TokenCreationError(f"HTTP {status} during token creation: {body[:400]}")

    data = _try_json(body)

    token = data.get("value") if isinstance(data, dict) else None
    if not token:
        raise TokenCreationError(f"Unexpected response from token creation: {data}")

    return str(token)

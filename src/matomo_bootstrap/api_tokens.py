import hashlib
import json
import os
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


def _login_via_logme(client: HttpClient, admin_user: str, admin_password: str, debug: bool) -> None:
    """
    Create an authenticated Matomo session (cookie jar) using the classic Login controller.

    Matomo accepts the md5 hashed password in the `password` parameter for action=logme.
    We rely on urllib's opener to follow redirects and store cookies.

    If this ever stops working in a future Matomo version, the next step would be:
    - GET the login page, extract CSRF/nonce, then POST the login form.
    """
    md5_password = _md5(admin_password)

    # Hit the login endpoint; cookies should be set in the client's CookieJar.
    # We treat any HTTP response as "we reached the login controller" – later API call will tell us if session is valid.
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
        if debug:
            print(f"[auth] login via logme returned HTTP {status} (body preview: {body[:120]!r})")
    except urllib.error.HTTPError as exc:
        # Even 4xx/5xx can still set cookies; continue and let the API call validate.
        if debug:
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            print(f"[auth] login via logme raised HTTPError {exc.code} (body preview: {err_body[:120]!r})")


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
        if debug:
            print("[auth] Using MATOMO_BOOTSTRAP_TOKEN_AUTH from environment.")
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

    if debug:
        print(f"[auth] createAppSpecificTokenAuth HTTP {status} body[:200]={body[:200]!r}")

    if status != 200:
        raise TokenCreationError(f"HTTP {status} during token creation: {body[:400]}")

    data = _try_json(body)

    token = data.get("value") if isinstance(data, dict) else None
    if not token:
        # Matomo may return {"result":"error","message":"..."}.
        raise TokenCreationError(f"Unexpected response from token creation: {data}")

    return str(token)

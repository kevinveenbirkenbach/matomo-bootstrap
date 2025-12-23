import hashlib
import json
from .errors import TokenCreationError
from .http import HttpClient


def get_token_auth(client: HttpClient, admin_user: str, admin_password: str) -> str:
    """
    Get the user's token_auth via UsersManager.getTokenAuth.

    This is the most robust way to authenticate subsequent API calls without relying
    on UI sessions/cookies.
    """
    md5_password = hashlib.md5(admin_password.encode("utf-8")).hexdigest()

    status, body = client.get(
        "/index.php",
        {
            "module": "API",
            "method": "UsersManager.getTokenAuth",
            "userLogin": admin_user,
            "md5Password": md5_password,
            "format": "json",
        },
    )

    if status != 200:
        raise TokenCreationError(f"HTTP {status} during getTokenAuth: {body[:200]}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TokenCreationError(f"Invalid JSON from getTokenAuth: {body[:200]}") from exc

    # Matomo returns either {"value": "..."} or sometimes a plain string depending on setup/version
    if isinstance(data, dict) and data.get("value"):
        return str(data["value"])
    if isinstance(data, str) and data:
        return data

    raise TokenCreationError(f"Unexpected getTokenAuth response: {data}")


def create_app_token(
    client: HttpClient,
    admin_token_auth: str,
    admin_user: str,
    admin_password: str,
    description: str,
) -> str:
    """
    Create an app-specific token using token_auth authentication.
    """
    status, body = client.post(
        "/index.php",
        {
            "module": "API",
            "method": "UsersManager.createAppSpecificTokenAuth",
            "userLogin": admin_user,
            "passwordConfirmation": admin_password,
            "description": description,
            "format": "json",
            "token_auth": admin_token_auth,
        },
    )

    if status != 200:
        raise TokenCreationError(f"HTTP {status} during token creation: {body[:200]}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TokenCreationError(f"Invalid JSON from Matomo API: {body[:200]}") from exc

    token = data.get("value") if isinstance(data, dict) else None
    if not token:
        raise TokenCreationError(f"Unexpected response: {data}")

    return str(token)

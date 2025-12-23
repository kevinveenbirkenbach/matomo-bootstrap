import json
from .http import HttpClient
from .errors import TokenCreationError


def create_app_token(
    client: HttpClient,
    admin_user: str,
    admin_password: str,
    description: str,
) -> str:
    status, body = client.post(
        "/api.php",
        {
            "module": "API",
            "method": "UsersManager.createAppSpecificTokenAuth",
            "userLogin": admin_user,
            "passwordConfirmation": admin_password,
            "description": description,
            "format": "json",
        },
    )

    if status != 200:
        raise TokenCreationError(f"HTTP {status} during token creation")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TokenCreationError("Invalid JSON from Matomo API") from exc

    token = data.get("value")
    if not token:
        raise TokenCreationError(f"Unexpected response: {data}")

    return token

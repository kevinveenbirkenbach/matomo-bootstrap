from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    base_url: str
    admin_user: str
    admin_password: str
    admin_email: str
    token_description: str = "matomo-bootstrap"
    timeout: int = 20
    debug: bool = False
    matomo_container_name: str | None = (
        None  # optional, for future console installer usage
    )


def config_from_env_and_args(args) -> Config:
    """
    Build a Config object from CLI args (preferred) and environment variables (fallback).
    """
    base_url = getattr(args, "base_url", None) or os.environ.get("MATOMO_URL")
    admin_user = getattr(args, "admin_user", None) or os.environ.get(
        "MATOMO_ADMIN_USER"
    )
    admin_password = getattr(args, "admin_password", None) or os.environ.get(
        "MATOMO_ADMIN_PASSWORD"
    )
    admin_email = getattr(args, "admin_email", None) or os.environ.get(
        "MATOMO_ADMIN_EMAIL"
    )

    token_description = (
        getattr(args, "token_description", None)
        or os.environ.get("MATOMO_TOKEN_DESCRIPTION")
        or "matomo-bootstrap"
    )

    timeout = int(
        getattr(args, "timeout", None) or os.environ.get("MATOMO_TIMEOUT") or "20"
    )
    debug = bool(getattr(args, "debug", False))

    matomo_container_name = (
        getattr(args, "matomo_container_name", None)
        or os.environ.get("MATOMO_CONTAINER_NAME")
        or None
    )

    missing: list[str] = []
    if not base_url:
        missing.append("--base-url (or MATOMO_URL)")
    if not admin_user:
        missing.append("--admin-user (or MATOMO_ADMIN_USER)")
    if not admin_password:
        missing.append("--admin-password (or MATOMO_ADMIN_PASSWORD)")
    if not admin_email:
        missing.append("--admin-email (or MATOMO_ADMIN_EMAIL)")

    if missing:
        raise ValueError("missing required values: " + ", ".join(missing))

    return Config(
        base_url=str(base_url),
        admin_user=str(admin_user),
        admin_password=str(admin_password),
        admin_email=str(admin_email),
        token_description=str(token_description),
        timeout=timeout,
        debug=debug,
        matomo_container_name=matomo_container_name,
    )

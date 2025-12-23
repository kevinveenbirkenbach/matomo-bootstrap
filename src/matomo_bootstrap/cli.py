import argparse
import os


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Headless bootstrap tool for Matomo (installation + API token provisioning)"
    )

    p.add_argument(
        "--base-url",
        default=os.environ.get("MATOMO_URL"),
        help="Matomo base URL (or MATOMO_URL env)",
    )
    p.add_argument(
        "--admin-user",
        default=os.environ.get("MATOMO_ADMIN_USER"),
        help="Admin login (or MATOMO_ADMIN_USER env)",
    )
    p.add_argument(
        "--admin-password",
        default=os.environ.get("MATOMO_ADMIN_PASSWORD"),
        help="Admin password (or MATOMO_ADMIN_PASSWORD env)",
    )
    p.add_argument(
        "--admin-email",
        default=os.environ.get("MATOMO_ADMIN_EMAIL"),
        help="Admin email (or MATOMO_ADMIN_EMAIL env)",
    )
    p.add_argument(
        "--token-description",
        default=os.environ.get("MATOMO_TOKEN_DESCRIPTION", "matomo-bootstrap"),
        help="App token description",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("MATOMO_TIMEOUT", "20")),
        help="Network timeout in seconds (or MATOMO_TIMEOUT env)",
    )
    p.add_argument("--debug", action="store_true", help="Enable debug logs on stderr")

    # Optional (future use)
    p.add_argument(
        "--matomo-container-name",
        default=os.environ.get("MATOMO_CONTAINER_NAME"),
        help="Matomo container name (optional; also MATOMO_CONTAINER_NAME env)",
    )

    return p.parse_args()

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
    )
    p.add_argument("--timeout", type=int, default=int(os.environ.get("MATOMO_TIMEOUT", "20")))
    p.add_argument("--debug", action="store_true")

    args = p.parse_args()

    missing = []
    if not args.base_url:
        missing.append("--base-url (or MATOMO_URL)")
    if not args.admin_user:
        missing.append("--admin-user (or MATOMO_ADMIN_USER)")
    if not args.admin_password:
        missing.append("--admin-password (or MATOMO_ADMIN_PASSWORD)")
    if not args.admin_email:
        missing.append("--admin-email (or MATOMO_ADMIN_EMAIL)")

    if missing:
        p.error("missing required values: " + ", ".join(missing))

    return args

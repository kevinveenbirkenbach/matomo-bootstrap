import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Headless bootstrap tool for Matomo (installation + API token provisioning)"
    )

    p.add_argument("--base-url", required=True, help="Matomo base URL")
    p.add_argument("--admin-user", required=True)
    p.add_argument("--admin-password", required=True)
    p.add_argument("--admin-email", required=True)
    p.add_argument("--token-description", default="matomo-bootstrap")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--debug", action="store_true")

    return p.parse_args()

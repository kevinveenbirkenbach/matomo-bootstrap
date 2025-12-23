from argparse import Namespace
from .health import assert_matomo_ready
from .http import HttpClient
from .api_tokens import create_app_token
from .install.web_installer import ensure_installed


def run_bootstrap(args: Namespace) -> str:
    # 1. Matomo erreichbar?
    assert_matomo_ready(args.base_url, timeout=args.timeout)

    # 2. Installation sicherstellen (NO-OP wenn bereits installiert)
    ensure_installed(
        base_url=args.base_url,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
        admin_email=args.admin_email,
        debug=args.debug,
    )

    # 3. API-Token erzeugen
    client = HttpClient(
        base_url=args.base_url,
        timeout=args.timeout,
        debug=args.debug,
    )

    token = create_app_token(
        client=client,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
        description=args.token_description,
    )

    return token

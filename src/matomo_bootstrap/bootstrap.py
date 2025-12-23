from argparse import Namespace

from .api_tokens import create_app_token, get_token_auth
from .health import assert_matomo_ready
from .http import HttpClient
from .install.web_installer import ensure_installed


def run_bootstrap(args: Namespace) -> str:
    # 1) Ensure Matomo is installed (NO-OP if already installed)
    ensure_installed(
        base_url=args.base_url,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
        admin_email=args.admin_email,
        debug=args.debug,
    )

    # 2) Now the UI/API should be reachable and "installed"
    assert_matomo_ready(args.base_url, timeout=args.timeout)

    # 3) Create authenticated API token flow (no UI session needed)
    client = HttpClient(
        base_url=args.base_url,
        timeout=args.timeout,
        debug=args.debug,
    )

    admin_token_auth = get_token_auth(
        client=client,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
    )

    token = create_app_token(
        client=client,
        admin_token_auth=admin_token_auth,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
        description=args.token_description,
    )

    return token

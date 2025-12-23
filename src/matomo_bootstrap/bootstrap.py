from argparse import Namespace

from .api_tokens import create_app_token_via_session
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

    # 3) Create app-specific token via authenticated session (cookie-based)
    client = HttpClient(
        base_url=args.base_url,
        timeout=args.timeout,
        debug=args.debug,
    )

    token = create_app_token_via_session(
        client=client,
        admin_user=args.admin_user,
        admin_password=args.admin_password,
        description=args.token_description,
        debug=args.debug,
    )

    return token

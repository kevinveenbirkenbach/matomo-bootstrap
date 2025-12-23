from __future__ import annotations

from .config import Config
from .http import HttpClient
from .matomo_api import MatomoApi
from .installers.web import WebInstaller


def run(config: Config) -> str:
    """
    Orchestrate:
      1) Ensure Matomo is installed (NO-OP if installed)
      2) Ensure Matomo is reachable/ready
      3) Create an app-specific token using an authenticated session
    """
    installer = WebInstaller()
    installer.ensure_installed(config)

    client = HttpClient(
        base_url=config.base_url,
        timeout=config.timeout,
        debug=config.debug,
    )
    api = MatomoApi(client=client, debug=config.debug)

    api.assert_ready(timeout=config.timeout)

    token = api.create_app_specific_token(
        admin_user=config.admin_user,
        admin_password=config.admin_password,
        description=config.token_description,
    )
    return token

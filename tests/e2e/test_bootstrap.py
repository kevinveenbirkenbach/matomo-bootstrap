import json
import os
import subprocess
import unittest
import urllib.request


MATOMO_URL = os.environ.get("MATOMO_URL", "http://127.0.0.1:8080")
ADMIN_USER = os.environ.get("MATOMO_ADMIN_USER", "administrator")
ADMIN_PASSWORD = os.environ.get("MATOMO_ADMIN_PASSWORD", "AdminSecret123!")


class TestMatomoBootstrapE2E(unittest.TestCase):
    def test_bootstrap_creates_api_token(self) -> None:
        cmd = [
            "python3",
            "-m",
            "matomo_bootstrap",
            "--base-url",
            MATOMO_URL,
            "--admin-user",
            ADMIN_USER,
            "--admin-password",
            ADMIN_PASSWORD,
            "--token-description",
            "e2e-test-token",
        ]

        token = subprocess.check_output(
            cmd,
            env={**os.environ, "PYTHONPATH": "src"},
        ).decode().strip()

        self.assertRegex(token, r"^[a-f0-9]{32,64}$", f"Expected token_auth, got: {token}")

        api_url = (
            f"{MATOMO_URL}/api.php"
            f"?module=API&method=SitesManager.getSitesWithAtLeastViewAccess"
            f"&format=json&token_auth={token}"
        )
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        self.assertIsInstance(data, list)

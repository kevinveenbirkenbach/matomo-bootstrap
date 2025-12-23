import os
import sys
import time
import urllib.request


MATOMO_URL = os.environ.get("MATOMO_URL", "http://127.0.0.1:8080")
ADMIN_USER = os.environ.get("MATOMO_ADMIN_USER", "administrator")
ADMIN_PASSWORD = os.environ.get("MATOMO_ADMIN_PASSWORD", "AdminSecret123!")
ADMIN_EMAIL = os.environ.get("MATOMO_ADMIN_EMAIL", "admin@example.org")

DB_HOST = os.environ.get("MATOMO_DB_HOST", "db")
DB_USER = os.environ.get("MATOMO_DB_USER", "matomo")
DB_PASS = os.environ.get("MATOMO_DB_PASS", "matomo_pw")
DB_NAME = os.environ.get("MATOMO_DB_NAME", "matomo")
DB_PREFIX = os.environ.get("MATOMO_DB_PREFIX", "matomo_")


def wait_http(url: str, timeout: int = 180) -> None:
    print(f"[install] Waiting for Matomo HTTP at {url} ...")
    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                _ = resp.read(1024)
            print("[install] Matomo HTTP reachable.")
            return
        except Exception:
            if i % 5 == 0:
                print(f"[install] still waiting ({i}/{timeout}) …")
            time.sleep(1)
    raise RuntimeError(f"Matomo did not become reachable after {timeout}s: {url}")


def is_installed(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            html = resp.read().decode(errors="ignore").lower()
        return ("module=login" in html) or ("matomo › login" in html)
    except Exception:
        return False


def ensure_installed(
    base_url: str,
    admin_user: str,
    admin_password: str,
    admin_email: str,
    debug: bool = False,
) -> None:
    """
    Ensure Matomo is installed.
    NO-OP if already installed.
    """

    # Propagate config to installer via ENV (single source of truth)
    os.environ["MATOMO_URL"] = base_url
    os.environ["MATOMO_ADMIN_USER"] = admin_user
    os.environ["MATOMO_ADMIN_PASSWORD"] = admin_password
    os.environ["MATOMO_ADMIN_EMAIL"] = admin_email

    rc = main()
    if rc != 0:
        raise RuntimeError("Matomo installation failed")


def main() -> int:
    wait_http(MATOMO_URL)

    if is_installed(MATOMO_URL):
        print("[install] Matomo already installed. Skipping installer.")
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print("[install] Playwright not available.", file=sys.stderr)
        print(
            "Install with: python3 -m pip install playwright && python3 -m playwright install chromium",
            file=sys.stderr,
        )
        print(f"Reason: {exc}", file=sys.stderr)
        return 2

    print("[install] Running Matomo web installer via headless browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(MATOMO_URL, wait_until="domcontentloaded")

        def click_next():
            for label in ["Next", "Continue", "Start Installation", "Proceed"]:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click()
                    return True
            return False

        # Welcome / system check
        page.wait_for_timeout(500)
        click_next()
        page.wait_for_timeout(500)
        click_next()

        # Database setup
        page.wait_for_timeout(500)
        page.get_by_label("Database Server").fill(DB_HOST)
        page.get_by_label("Login").fill(DB_USER)
        page.get_by_label("Password").fill(DB_PASS)
        page.get_by_label("Database Name").fill(DB_NAME)
        try:
            page.get_by_label("Tables Prefix").fill(DB_PREFIX)
        except Exception:
            pass
        click_next()

        # Tables creation
        page.wait_for_timeout(500)
        click_next()

        # Super user
        page.wait_for_timeout(500)
        page.get_by_label("Login").fill(ADMIN_USER)
        page.get_by_label("Password").fill(ADMIN_PASSWORD)
        try:
            page.get_by_label("Password (repeat)").fill(ADMIN_PASSWORD)
        except Exception:
            pass
        page.get_by_label("Email").fill(ADMIN_EMAIL)
        click_next()

        # First website
        page.wait_for_timeout(500)
        try:
            page.get_by_label("Name").fill("Bootstrap Site")
        except Exception:
            pass
        try:
            page.get_by_label("URL").fill("http://example.invalid")
        except Exception:
            pass
        click_next()

        # Finish
        page.wait_for_timeout(500)
        click_next()

        browser.close()

    time.sleep(2)
    if not is_installed(MATOMO_URL):
        print("[install] Installer did not reach installed state.", file=sys.stderr)
        return 3

    print("[install] Installation finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

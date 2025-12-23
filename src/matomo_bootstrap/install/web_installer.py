import os
import sys
import time
import urllib.error
import urllib.request


DB_HOST = os.environ.get("MATOMO_DB_HOST", "db")
DB_USER = os.environ.get("MATOMO_DB_USER", "matomo")
DB_PASS = os.environ.get("MATOMO_DB_PASS", "matomo_pw")
DB_NAME = os.environ.get("MATOMO_DB_NAME", "matomo")
DB_PREFIX = os.environ.get("MATOMO_DB_PREFIX", "matomo_")


def wait_http(url: str, timeout: int = 180) -> None:
    """
    Consider Matomo 'reachable' as soon as the HTTP server answers - even with 500.
    urllib raises HTTPError for 4xx/5xx, so we must treat that as reachability too.
    """
    print(f"[install] Waiting for Matomo HTTP at {url} ...")
    last_err: Exception | None = None

    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                _ = resp.read(128)
            print("[install] Matomo HTTP reachable (2xx/3xx).")
            return
        except urllib.error.HTTPError as exc:
            # 4xx/5xx means the server answered -> reachable
            print(f"[install] Matomo HTTP reachable (HTTP {exc.code}).")
            return
        except Exception as exc:
            last_err = exc
            if i % 5 == 0:
                print(f"[install] still waiting ({i}/{timeout}) … ({type(exc).__name__})")
            time.sleep(1)

    raise RuntimeError(f"Matomo did not become reachable after {timeout}s: {url} ({last_err})")


def is_installed(url: str) -> bool:
    """
    Heuristic:
    - installed instances typically render login module links
    - installer renders 'installation' wizard content
    """
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            html = resp.read().decode(errors="ignore").lower()
        return ("module=login" in html) or ("matomo › login" in html) or ("matomo/login" in html)
    except urllib.error.HTTPError as exc:
        # Even if it's 500, read body and try heuristic.
        try:
            html = exc.read().decode(errors="ignore").lower()
            return ("module=login" in html) or ("matomo › login" in html) or ("matomo/login" in html)
        except Exception:
            return False
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
    wait_http(base_url)

    if is_installed(base_url):
        if debug:
            print("[install] Matomo already looks installed. Skipping web installer.")
        return

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print("[install] Playwright not available.", file=sys.stderr)
        print(
            "Install with: python3 -m pip install playwright && python3 -m playwright install chromium",
            file=sys.stderr,
        )
        raise RuntimeError(f"Playwright missing: {exc}") from exc

    print("[install] Running Matomo web installer via headless browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load installer (may be 500 in curl, but browser can still render the Matomo error/installer flow)
        page.goto(base_url, wait_until="domcontentloaded")

        def click_next() -> None:
            # Buttons vary slightly with locales/versions
            for label in ["Next", "Continue", "Start Installation", "Proceed", "Weiter", "Fortfahren"]:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click()
                    return
            # Sometimes it's a link styled as button
            for text in ["Next", "Continue", "Start Installation", "Proceed", "Weiter", "Fortfahren"]:
                a = page.get_by_text(text, exact=False)
                if a.count() > 0:
                    a.first.click()
                    return
            raise RuntimeError("Could not find a 'Next/Continue' control in installer UI.")

        # Welcome / System check
        page.wait_for_timeout(700)
        click_next()
        page.wait_for_timeout(700)
        click_next()

        # Database setup
        page.wait_for_timeout(700)
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
        page.wait_for_timeout(700)
        click_next()

        # Super user
        page.wait_for_timeout(700)
        page.get_by_label("Login").fill(admin_user)
        page.get_by_label("Password").fill(admin_password)
        try:
            page.get_by_label("Password (repeat)").fill(admin_password)
        except Exception:
            pass
        page.get_by_label("Email").fill(admin_email)
        click_next()

        # First website
        page.wait_for_timeout(700)
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
        page.wait_for_timeout(700)
        click_next()

        browser.close()

    # Verify installed
    time.sleep(2)
    if not is_installed(base_url):
        raise RuntimeError("[install] Installer did not reach installed state.")

    print("[install] Installation finished.")

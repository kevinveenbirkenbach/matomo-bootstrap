import os
import sys
import time
import urllib.error
import urllib.request

# Optional knobs (mostly for debugging / CI stability)
PLAYWRIGHT_HEADLESS = (
    os.environ.get("MATOMO_PLAYWRIGHT_HEADLESS", "1").strip() not in ("0", "false", "False")
)
PLAYWRIGHT_SLOWMO_MS = int(os.environ.get("MATOMO_PLAYWRIGHT_SLOWMO_MS", "0"))
PLAYWRIGHT_NAV_TIMEOUT_MS = int(os.environ.get("MATOMO_PLAYWRIGHT_NAV_TIMEOUT_MS", "60000"))

# Values used by the installer flow (recorded)
DEFAULT_SITE_NAME = os.environ.get("MATOMO_SITE_NAME", "localhost")
DEFAULT_SITE_URL = os.environ.get("MATOMO_SITE_URL", "http://localhost")
DEFAULT_TIMEZONE = os.environ.get("MATOMO_TIMEZONE", "Germany - Berlin")
DEFAULT_ECOMMERCE = os.environ.get("MATOMO_ECOMMERCE", "Ecommerce enabled")


def _log(msg: str) -> None:
    # IMPORTANT: logs must not pollute stdout (tests expect only token on stdout)
    print(msg, file=sys.stderr)


def wait_http(url: str, timeout: int = 180) -> None:
    """
    Consider Matomo 'reachable' as soon as the HTTP server answers - even with 500.
    urllib raises HTTPError for 4xx/5xx, so we must treat that as reachability too.
    """
    _log(f"[install] Waiting for Matomo HTTP at {url} ...")
    last_err: Exception | None = None

    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                _ = resp.read(128)
            _log("[install] Matomo HTTP reachable (2xx/3xx).")
            return
        except urllib.error.HTTPError as exc:
            # 4xx/5xx means the server answered -> reachable
            _log(f"[install] Matomo HTTP reachable (HTTP {exc.code}).")
            return
        except Exception as exc:
            last_err = exc
            if i % 5 == 0:
                _log(f"[install] still waiting ({i}/{timeout}) … ({type(exc).__name__})")
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

    This implementation ONLY uses the Playwright web installer (recorded flow).
    """
    wait_http(base_url)

    if is_installed(base_url):
        if debug:
            _log("[install] Matomo already looks installed. Skipping installer.")
        return

    from playwright.sync_api import sync_playwright

    _log("[install] Running Matomo web installer via Playwright (recorded flow)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            slow_mo=PLAYWRIGHT_SLOWMO_MS if PLAYWRIGHT_SLOWMO_MS > 0 else None,
        )
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)
        page.set_default_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)

        def _dbg(msg: str) -> None:
            if debug:
                _log(f"[install] {msg}")

        def click_next() -> None:
            """
            Matomo installer mixes link/button variants and sometimes includes '»'.
            We try common variants in a robust order.
            """
            candidates = [
                ("link", "Next »"),
                ("button", "Next »"),
                ("link", "Next"),
                ("button", "Next"),
                ("link", "Continue"),
                ("button", "Continue"),
                ("link", "Proceed"),
                ("button", "Proceed"),
                ("link", "Start Installation"),
                ("button", "Start Installation"),
                ("link", "Weiter"),
                ("button", "Weiter"),
                ("link", "Fortfahren"),
                ("button", "Fortfahren"),
            ]

            for role, name in candidates:
                loc = page.get_by_role(role, name=name)
                if loc.count() > 0:
                    _dbg(f"click_next(): {role} '{name}'")
                    loc.first.click()
                    return

            # last resort: some pages use same text but different element types
            loc = page.get_by_text("Next", exact=False)
            if loc.count() > 0:
                _dbg("click_next(): fallback text 'Next'")
                loc.first.click()
                return

            raise RuntimeError("Could not find a Next/Continue control in the installer UI.")

        # --- Recorded-ish flow, but made variable-based + more stable ---
        page.goto(base_url, wait_until="domcontentloaded")

        def superuser_form_visible() -> bool:
            # In your recording, the superuser "Login" field was "#login-0".
            return page.locator("#login-0").count() > 0

        # Click next until the superuser page shows up (cap to avoid infinite loops).
        for _ in range(12):
            if superuser_form_visible():
                break
            click_next()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(200)
        else:
            raise RuntimeError("Installer did not reach superuser step (login-0 not found).")

        # Superuser step
        page.locator("#login-0").click()
        page.locator("#login-0").fill(admin_user)

        page.locator("#password-0").click()
        page.locator("#password-0").fill(admin_password)

        # Repeat password (some versions have it)
        if page.locator("#password_bis-0").count() > 0:
            page.locator("#password_bis-0").click()
            page.locator("#password_bis-0").fill(admin_password)

        page.locator("#email-0").click()
        page.locator("#email-0").fill(admin_email)

        # Next
        if page.get_by_role("button", name="Next »").count() > 0:
            page.get_by_role("button", name="Next »").click()
        else:
            click_next()

        # First website
        if page.locator("#siteName-0").count() > 0:
            page.locator("#siteName-0").click()
            page.locator("#siteName-0").fill(DEFAULT_SITE_NAME)

        if page.locator("#url-0").count() > 0:
            page.locator("#url-0").click()
            page.locator("#url-0").fill(DEFAULT_SITE_URL)

        # Timezone dropdown (best-effort)
        try:
            page.get_by_role("combobox").first.click()
            page.get_by_role("listbox").get_by_text(DEFAULT_TIMEZONE).click()
        except Exception:
            _dbg("Timezone selection skipped (not found / changed UI).")

        # Ecommerce dropdown (best-effort)
        try:
            page.get_by_role("combobox").nth(2).click()
            page.get_by_role("listbox").get_by_text(DEFAULT_ECOMMERCE).click()
        except Exception:
            _dbg("Ecommerce selection skipped (not found / changed UI).")

        # Next pages to finish
        click_next()
        page.wait_for_load_state("domcontentloaded")

        if page.get_by_role("link", name="Next »").count() > 0:
            page.get_by_role("link", name="Next »").click()

        if page.get_by_role("button", name="Continue to Matomo »").count() > 0:
            page.get_by_role("button", name="Continue to Matomo »").click()

        context.close()
        browser.close()

    time.sleep(1)
    if not is_installed(base_url):
        raise RuntimeError("[install] Installer did not reach installed state.")

    _log("[install] Installation finished.")

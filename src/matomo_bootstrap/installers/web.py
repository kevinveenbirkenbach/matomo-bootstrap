from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import Installer
from ..config import Config


# Optional knobs (mostly for debugging / CI stability)
PLAYWRIGHT_HEADLESS = os.environ.get("MATOMO_PLAYWRIGHT_HEADLESS", "1").strip() not in (
    "0",
    "false",
    "False",
)
PLAYWRIGHT_SLOWMO_MS = int(os.environ.get("MATOMO_PLAYWRIGHT_SLOWMO_MS", "0"))
PLAYWRIGHT_NAV_TIMEOUT_MS = int(
    os.environ.get("MATOMO_PLAYWRIGHT_NAV_TIMEOUT_MS", "60000")
)
INSTALLER_READY_TIMEOUT_S = int(
    os.environ.get("MATOMO_INSTALLER_READY_TIMEOUT_S", "180")
)
INSTALLER_STEP_TIMEOUT_S = int(os.environ.get("MATOMO_INSTALLER_STEP_TIMEOUT_S", "30"))
INSTALLER_STEP_DEADLINE_S = int(
    os.environ.get("MATOMO_INSTALLER_STEP_DEADLINE_S", "180")
)
INSTALLER_TABLES_CREATION_TIMEOUT_S = int(
    os.environ.get("MATOMO_INSTALLER_TABLES_CREATION_TIMEOUT_S", "180")
)
INSTALLER_TABLES_ERASE_TIMEOUT_S = int(
    os.environ.get("MATOMO_INSTALLER_TABLES_ERASE_TIMEOUT_S", "120")
)
INSTALLER_DEBUG_DIR = os.environ.get(
    "MATOMO_INSTALLER_DEBUG_DIR", "/tmp/matomo-bootstrap"
).rstrip("/")

# Values used by the installer flow (recorded)
DEFAULT_SITE_NAME = os.environ.get("MATOMO_SITE_NAME", "localhost")
DEFAULT_SITE_URL = os.environ.get("MATOMO_SITE_URL", "http://localhost")
DEFAULT_TIMEZONE = os.environ.get("MATOMO_TIMEZONE", "Germany - Berlin")
DEFAULT_ECOMMERCE = os.environ.get("MATOMO_ECOMMERCE", "Ecommerce enabled")

NEXT_BUTTON_CANDIDATES: list[tuple[str, str]] = [
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

CONTINUE_TO_MATOMO_CANDIDATES: list[tuple[str, str]] = [
    ("button", "Continue to Matomo »"),
    ("button", "Continue to Matomo"),
    ("link", "Continue to Matomo »"),
    ("link", "Continue to Matomo"),
]

SUPERUSER_LOGIN_SELECTORS = (
    "#login-0",
    "#login",
    "input[name='login']",
    "form#generalsetupform input[name='login']",
)
SUPERUSER_PASSWORD_SELECTORS = (
    "#password-0",
    "#password",
    "input[name='password']",
    "form#generalsetupform input[name='password']",
)
SUPERUSER_PASSWORD_REPEAT_SELECTORS = (
    "#password_bis-0",
    "#password_bis",
    "input[name='password_bis']",
    "form#generalsetupform input[name='password_bis']",
)
SUPERUSER_EMAIL_SELECTORS = (
    "#email-0",
    "#email",
    "input[name='email']",
    "form#generalsetupform input[name='email']",
)
SUPERUSER_SUBMIT_SELECTORS = (
    "#submit-0",
    "#submit",
    "form#generalsetupform button[type='submit']",
    "form#generalsetupform input[type='submit']",
)
FIRST_WEBSITE_NAME_SELECTORS = (
    "#siteName-0",
    "#siteName",
    "input[name='siteName']",
    "form#websitesetupform input[name='siteName']",
)
FIRST_WEBSITE_URL_SELECTORS = (
    "#url-0",
    "#url",
    "input[name='url']",
    "form#websitesetupform input[name='url']",
)


def _log(msg: str) -> None:
    # IMPORTANT: logs must not pollute stdout (tests expect only token on stdout)
    print(msg, file=sys.stderr)


_TRANSIENT_NAVIGATION_ERROR_SNIPPETS = (
    "Execution context was destroyed",
    "most likely because of a navigation",
    "Cannot find context with specified id",
    "Frame was detached",
)


def _is_transient_navigation_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(snippet in msg for snippet in _TRANSIENT_NAVIGATION_ERROR_SNIPPETS)


def _count_locator(
    locator, *, timeout_s: float = 2.0, retry_interval_s: float = 0.1
) -> int:
    deadline = time.time() + timeout_s
    while True:
        try:
            return locator.count()
        except Exception as exc:
            if _is_transient_navigation_error(exc) and time.time() < deadline:
                time.sleep(retry_interval_s)
                continue
            raise


def _page_warnings(page, *, prefix: str = "[install]") -> list[str]:
    """
    Detect Matomo installer warnings/errors on the current page.

    - Does NOT change any click logic.
    - Prints found warnings/errors to stderr (stdout stays clean).
    - Returns a de-duplicated list of warning/error texts (empty if none found).
    """

    def _safe(s: str | None) -> str:
        return (s or "").strip()

    # Helpful context (doesn't spam much, but makes failures traceable)
    try:
        url = page.url
    except Exception:
        url = "<unknown-url>"
    try:
        title = page.title()
    except Exception:
        title = "<unknown-title>"

    selectors = [
        # your originals
        ".warning",
        ".alert.alert-danger",
        ".alert.alert-warning",
        ".notification",
        ".message_container",
        # common Matomo / UI patterns seen across versions
        "#notificationContainer",
        ".system-check-error",
        ".system-check-warning",
        ".form-errors",
        ".error",
        ".errorMessage",
        ".invalid-feedback",
        ".help-block.error",
        ".ui-state-error",
        ".alert-danger",
        ".alert-warning",
        "[role='alert']",
    ]

    texts: list[str] = []

    for sel in selectors:
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:
            n = 0
        if n <= 0:
            continue

        # collect all matches (not only .first)
        for i in range(min(n, 50)):  # avoid insane spam if page is weird
            try:
                t = _safe(loc.nth(i).inner_text())
            except Exception:
                t = ""
            if t:
                texts.append(t)

    # Also catch HTML5 validation bubbles / inline field errors
    # (Sometimes Matomo marks invalid inputs with aria-invalid + sibling text)
    try:
        invalid = page.locator("[aria-invalid='true']")
        n_invalid = invalid.count()
    except Exception:
        n_invalid = 0

    if n_invalid > 0:
        texts.append(f"{n_invalid} field(s) marked aria-invalid=true.")

    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append(t)

    if out:
        print(
            f"{prefix} page warnings/errors detected @ {url} ({title}):",
            file=sys.stderr,
        )
        for idx, t in enumerate(out, 1):
            print(f"{prefix}  {idx}) {t}", file=sys.stderr)

    return out


def _wait_dom_settled(page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        pass

    try:
        # Best effort: helps when the UI needs a bit more rendering time.
        page.wait_for_load_state("networkidle", timeout=2_000)
    except Exception:
        pass

    page.wait_for_timeout(250)


def _get_step_hint(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        module = (qs.get("module") or [""])[0]
        action = (qs.get("action") or [""])[0]
        if module or action:
            return f"{module}:{action}"
        return parsed.path or url
    except Exception:
        return url


def _safe_page_snapshot_name() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _dump_failure_artifacts(page, reason: str) -> None:
    os.makedirs(INSTALLER_DEBUG_DIR, exist_ok=True)
    stamp = _safe_page_snapshot_name()
    base = f"{INSTALLER_DEBUG_DIR}/installer-failure-{stamp}"
    screenshot_path = f"{base}.png"
    html_path = f"{base}.html"
    meta_path = f"{base}.txt"

    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception as exc:
        _log(f"[install] Could not write screenshot: {exc}")
        screenshot_path = "<unavailable>"

    try:
        html = page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as exc:
        _log(f"[install] Could not write HTML snapshot: {exc}")
        html_path = "<unavailable>"

    try:
        url = page.url
    except Exception:
        url = "<unknown-url>"
    try:
        title = page.title()
    except Exception:
        title = "<unknown-title>"

    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"reason: {reason}\n")
            f.write(f"url: {url}\n")
            f.write(f"title: {title}\n")
            f.write(f"step_hint: {_get_step_hint(url)}\n")
    except Exception as exc:
        _log(f"[install] Could not write metadata snapshot: {exc}")
        meta_path = "<unavailable>"

    _log("[install] Debug artifacts written:")
    _log(f"[install]   screenshot: {screenshot_path}")
    _log(f"[install]   html: {html_path}")
    _log(f"[install]   meta: {meta_path}")


def _first_next_locator(page):
    for role, name in NEXT_BUTTON_CANDIDATES:
        loc = page.get_by_role(role, name=name)
        try:
            if _count_locator(loc) > 0 and loc.first.is_visible():
                return loc.first, f"{role}:{name}"
        except Exception:
            continue

    text_loc = page.get_by_text("Next", exact=False)
    try:
        if _count_locator(text_loc) > 0 and text_loc.first.is_visible():
            return text_loc.first, "text:Next*"
    except Exception:
        pass

    return None, ""


def _first_present_css_locator(page, selectors, *, timeout_s: float = 0.2):
    for selector in selectors:
        loc = page.locator(selector)
        try:
            if _count_locator(loc, timeout_s=timeout_s) > 0:
                return loc.first, f"css:{selector}"
        except Exception:
            continue
    return None, ""


def _first_continue_to_matomo_locator(page, *, timeout_s: float = 0.2):
    for role, name in CONTINUE_TO_MATOMO_CANDIDATES:
        loc = page.get_by_role(role, name=name)
        try:
            if _count_locator(loc, timeout_s=timeout_s) > 0 and loc.first.is_visible():
                return loc.first, f"{role}:{name}"
        except Exception:
            continue

    text_loc = page.get_by_text("Continue to Matomo", exact=False)
    try:
        if (
            _count_locator(text_loc, timeout_s=timeout_s) > 0
            and text_loc.first.is_visible()
        ):
            return text_loc.first, "text:Continue to Matomo*"
    except Exception:
        pass

    return None, ""


def _has_superuser_login_field(page, *, timeout_s: float = 0.2) -> bool:
    loc, _ = _first_present_css_locator(
        page, SUPERUSER_LOGIN_SELECTORS, timeout_s=timeout_s
    )
    return loc is not None


def _has_first_website_name_field(page, *, timeout_s: float = 0.2) -> bool:
    loc, _ = _first_present_css_locator(
        page, FIRST_WEBSITE_NAME_SELECTORS, timeout_s=timeout_s
    )
    return loc is not None


def _has_continue_to_matomo_action(page, *, timeout_s: float = 0.2) -> bool:
    loc, _ = _first_continue_to_matomo_locator(page, timeout_s=timeout_s)
    return loc is not None


def _fill_required_input(page, selectors, value: str, *, label: str) -> None:
    loc, _ = _first_present_css_locator(page, selectors, timeout_s=1.0)
    if loc is None:
        raise RuntimeError(
            f"Could not locate required installer field '{label}' "
            f"(url={page.url}, step={_get_step_hint(page.url)})."
        )
    try:
        loc.click(timeout=2_000)
    except Exception:
        pass
    loc.fill(value)


def _fill_optional_input(page, selectors, value: str) -> bool:
    loc, _ = _first_present_css_locator(page, selectors, timeout_s=0.5)
    if loc is None:
        return False
    try:
        loc.click(timeout=2_000)
    except Exception:
        pass
    loc.fill(value)
    return True


def _installer_interactive(page) -> bool:
    checks = [
        _has_superuser_login_field(page),
        _has_first_website_name_field(page),
        _has_continue_to_matomo_action(page),
    ]
    loc, _ = _first_next_locator(page)
    return any(checks) or loc is not None


def _wait_for_installer_interactive(page, *, timeout_s: int) -> None:
    _log(f"[install] Waiting for interactive installer UI (timeout={timeout_s}s)...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _wait_dom_settled(page)
        if _installer_interactive(page):
            _log("[install] Installer UI looks interactive.")
            return
        page.wait_for_timeout(300)

    raise RuntimeError(
        f"Installer UI did not become interactive within {timeout_s}s "
        f"(url={page.url}, step={_get_step_hint(page.url)})."
    )


def _click_next_with_wait(page, *, timeout_s: int) -> str:
    before_url = page.url
    before_step = _get_step_hint(before_url)
    last_warning_log_at = 0.0
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        loc, label = _first_next_locator(page)
        if loc is not None:
            try:
                loc.click(timeout=2_000)
            except Exception:
                page.wait_for_timeout(250)
                continue
            _wait_dom_settled(page)
            after_url = page.url
            after_step = _get_step_hint(after_url)
            _log(
                f"[install] Clicked {label}; step {before_step} -> {after_step} "
                f"(url {before_url} -> {after_url})"
            )
            return after_step

        _wait_dom_settled(page)
        current_url = page.url
        current_step = _get_step_hint(current_url)
        if current_url != before_url or current_step != before_step:
            _log(
                "[install] Installer progressed without explicit click; "
                f"step {before_step} -> {current_step} "
                f"(url {before_url} -> {current_url})"
            )
            return current_step

        # Some installer transitions render the next form asynchronously without
        # exposing another "Next" control yet. Treat this as progress.
        if _has_superuser_login_field(page, timeout_s=0.2):
            _log(
                "[install] Superuser form became available without explicit click; "
                f"staying on step {current_step} (url {current_url})"
            )
            return current_step
        if _has_first_website_name_field(page, timeout_s=0.2):
            _log(
                "[install] First website form became available without explicit click; "
                f"staying on step {current_step} (url {current_url})"
            )
            return current_step
        if _has_continue_to_matomo_action(page, timeout_s=0.2):
            _log(
                "[install] Continue-to-Matomo action is available without explicit click; "
                f"staying on step {current_step} (url {current_url})"
            )
            return current_step

        now = time.time()
        if now - last_warning_log_at >= 5:
            _page_warnings(page)
            last_warning_log_at = now

        page.wait_for_timeout(300)

    raise RuntimeError(
        "Could not find a Next/Continue control in the installer UI "
        f"within {timeout_s}s (url={page.url}, step={_get_step_hint(page.url)})."
    )


def _first_erase_tables_locator(page):
    css_loc = page.locator("#eraseAllTables")
    try:
        if _count_locator(css_loc) > 0:
            return css_loc.first, "css:#eraseAllTables"
    except Exception:
        pass

    for role, name in [
        ("link", "Delete the detected tables »"),
        ("button", "Delete the detected tables »"),
        ("link", "Delete the detected tables"),
        ("button", "Delete the detected tables"),
    ]:
        loc = page.get_by_role(role, name=name)
        try:
            if _count_locator(loc) > 0:
                return loc.first, f"{role}:{name}"
        except Exception:
            continue

    text_loc = page.get_by_text("Delete the detected tables", exact=False)
    try:
        if _count_locator(text_loc) > 0:
            return text_loc.first, "text:Delete the detected tables*"
    except Exception:
        pass

    return None, ""


def _resolve_tables_creation_conflict(page, *, timeout_s: int) -> bool:
    before_url = page.url
    before_step = _get_step_hint(before_url)
    if "tablesCreation" not in before_step:
        return False

    loc, label = _first_erase_tables_locator(page)
    if loc is None:
        return False

    _log(
        "[install] Detected existing tables during tablesCreation. "
        f"Trying cleanup via {label}."
    )

    def _cleanup_url() -> str | None:
        try:
            href = page.locator("#eraseAllTables").first.get_attribute("href")
            if href:
                return urllib.parse.urljoin(page.url, href)
        except Exception:
            pass

        try:
            parsed = urllib.parse.urlparse(page.url)
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if (qs.get("action") or [""])[0] != "tablesCreation":
                return None
            qs["deleteTables"] = ["1"]
            return urllib.parse.urlunparse(
                parsed._replace(query=urllib.parse.urlencode(qs, doseq=True))
            )
        except Exception:
            return None

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        accepted_dialog = False

        def _accept_dialog(dialog) -> None:
            nonlocal accepted_dialog
            accepted_dialog = True
            try:
                _log(f"[install] Accepting installer dialog: {dialog.message}")
            except Exception:
                _log("[install] Accepting installer dialog.")
            try:
                dialog.accept()
            except Exception:
                pass

        page.on("dialog", _accept_dialog)
        try:
            loc.click(timeout=2_000, force=True)
            _wait_dom_settled(page)
        except Exception as exc:
            _log(f"[install] Cleanup click via {label} failed: {exc}")
            cleanup_url = _cleanup_url()
            if cleanup_url:
                try:
                    page.goto(cleanup_url, wait_until="domcontentloaded")
                    _wait_dom_settled(page)
                    _log(
                        "[install] Triggered existing-table cleanup via URL fallback: "
                        f"{cleanup_url}"
                    )
                except Exception as nav_exc:
                    _log(
                        "[install] Cleanup URL fallback failed: "
                        f"{cleanup_url} ({nav_exc})"
                    )
        finally:
            page.remove_listener("dialog", _accept_dialog)

        if accepted_dialog:
            _log("[install] Existing-table cleanup dialog accepted.")

        _wait_dom_settled(page)
        current_url = page.url
        current_step = _get_step_hint(current_url)
        if current_url != before_url or current_step != before_step:
            _log(
                "[install] Existing-table cleanup progressed installer; "
                f"step {before_step} -> {current_step} "
                f"(url {before_url} -> {current_url})"
            )
            return True

        remaining_loc, _ = _first_erase_tables_locator(page)
        if remaining_loc is None:
            _log("[install] Existing-table cleanup control is gone.")
            return True

        loc = remaining_loc
        page.wait_for_timeout(500)

    raise RuntimeError(
        "Detected existing Matomo tables but cleanup did not complete "
        f"within {timeout_s}s (url={page.url}, step={_get_step_hint(page.url)})."
    )


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
            _log(f"[install] Matomo HTTP reachable (HTTP {exc.code}).")
            return
        except Exception as exc:
            last_err = exc
            if i % 5 == 0:
                _log(
                    f"[install] still waiting ({i}/{timeout}) … ({type(exc).__name__})"
                )
            time.sleep(1)

    raise RuntimeError(
        f"Matomo did not become reachable after {timeout}s: {url} ({last_err})"
    )


def is_installed(url: str) -> bool:
    """
    Heuristic:
    - installed instances typically render login module links
    - installer renders 'installation' wizard content
    """
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            html = resp.read().decode(errors="ignore").lower()
        return (
            ("module=login" in html)
            or ("matomo › login" in html)
            or ("matomo/login" in html)
        )
    except urllib.error.HTTPError as exc:
        try:
            html = exc.read().decode(errors="ignore").lower()
            return (
                ("module=login" in html)
                or ("matomo › login" in html)
                or ("matomo/login" in html)
            )
        except Exception:
            return False
    except Exception:
        return False


class WebInstaller(Installer):
    def ensure_installed(self, config: Config) -> None:
        """
        Ensure Matomo is installed. NO-OP if already installed.
        Uses Playwright to drive the web installer (recorded flow).
        """
        base_url = config.base_url

        wait_http(base_url)

        if is_installed(base_url):
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

            try:
                page.goto(base_url, wait_until="domcontentloaded")
                _wait_for_installer_interactive(
                    page, timeout_s=INSTALLER_READY_TIMEOUT_S
                )
                _page_warnings(page)

                progress_deadline = time.time() + INSTALLER_STEP_DEADLINE_S

                while not _has_superuser_login_field(page):
                    if time.time() >= progress_deadline:
                        raise RuntimeError(
                            "Installer did not reach superuser step "
                            f"within {INSTALLER_STEP_DEADLINE_S}s "
                            f"(url={page.url}, step={_get_step_hint(page.url)})."
                        )
                    if _resolve_tables_creation_conflict(
                        page, timeout_s=INSTALLER_TABLES_ERASE_TIMEOUT_S
                    ):
                        _page_warnings(page)
                        continue
                    step_timeout = INSTALLER_STEP_TIMEOUT_S
                    if "tablesCreation" in _get_step_hint(page.url):
                        step_timeout = max(
                            step_timeout, INSTALLER_TABLES_CREATION_TIMEOUT_S
                        )
                    _click_next_with_wait(page, timeout_s=step_timeout)
                    _page_warnings(page)

                _fill_required_input(
                    page,
                    SUPERUSER_LOGIN_SELECTORS,
                    config.admin_user,
                    label="superuser login",
                )
                _fill_required_input(
                    page,
                    SUPERUSER_PASSWORD_SELECTORS,
                    config.admin_password,
                    label="superuser password",
                )
                _fill_optional_input(
                    page, SUPERUSER_PASSWORD_REPEAT_SELECTORS, config.admin_password
                )
                _fill_required_input(
                    page,
                    SUPERUSER_EMAIL_SELECTORS,
                    config.admin_email,
                    label="superuser email",
                )
                _page_warnings(page)

                submitted_superuser = False
                try:
                    submitted_superuser = bool(
                        page.evaluate(
                            """
                            ([user, password, email]) => {
                                const form = document.querySelector("form#generalsetupform");
                                if (!form) return false;

                                const loginInput = form.querySelector("input[name='login']");
                                const passwordInput = form.querySelector("input[name='password']");
                                const repeatPasswordInput = form.querySelector("input[name='password_bis']");
                                const emailInput = form.querySelector("input[name='email']");
                                if (!loginInput || !passwordInput || !emailInput) return false;

                                loginInput.value = user;
                                passwordInput.value = password;
                                if (repeatPasswordInput) {
                                    repeatPasswordInput.value = password;
                                }
                                emailInput.value = email;

                                if (typeof form.requestSubmit === "function") {
                                    form.requestSubmit();
                                } else {
                                    form.submit();
                                }
                                return true;
                            }
                            """,
                            [
                                config.admin_user,
                                config.admin_password,
                                config.admin_email,
                            ],
                        )
                    )
                except Exception:
                    submitted_superuser = False

                if submitted_superuser:
                    _wait_dom_settled(page)
                    _log("[install] Submitted superuser form via form.requestSubmit().")
                else:
                    submit_loc, submit_label = _first_present_css_locator(
                        page, SUPERUSER_SUBMIT_SELECTORS, timeout_s=0.5
                    )
                    if submit_loc is not None:
                        submit_loc.click(timeout=2_000)
                        _wait_dom_settled(page)
                        _log(
                            "[install] Submitted superuser form via "
                            f"{submit_label} fallback."
                        )
                    else:
                        _click_next_with_wait(page, timeout_s=INSTALLER_STEP_TIMEOUT_S)

                superuser_progress_deadline = time.time() + INSTALLER_STEP_TIMEOUT_S
                while time.time() < superuser_progress_deadline:
                    _wait_dom_settled(page)
                    if not _has_superuser_login_field(page):
                        break
                    page.wait_for_timeout(300)
                if _has_superuser_login_field(page):
                    _page_warnings(page)
                    raise RuntimeError(
                        "Superuser form submit did not progress to first website setup "
                        f"within {INSTALLER_STEP_TIMEOUT_S}s "
                        f"(url={page.url}, step={_get_step_hint(page.url)})."
                    )

                _page_warnings(page)

                submitted_first_website = False
                try:
                    submitted_first_website = bool(
                        page.evaluate(
                            """
                            ([siteName, siteUrl, timezoneLabel, ecommerceLabel]) => {
                                const form = document.querySelector("form#websitesetupform");
                                if (!form) return false;

                                const siteNameInput = form.querySelector("input[name='siteName']");
                                const siteUrlInput = form.querySelector("input[name='url']");
                                if (!siteNameInput || !siteUrlInput) return false;

                                siteNameInput.value = siteName;
                                siteUrlInput.value = siteUrl;

                                const timezoneSelect = form.querySelector("select[name='timezone']");
                                if (timezoneSelect) {
                                    const timezoneOption = Array.from(timezoneSelect.options).find(
                                        (opt) => (opt.textContent || "").trim() === timezoneLabel
                                    );
                                    if (timezoneOption) {
                                        timezoneSelect.value = timezoneOption.value;
                                    }
                                }

                                const ecommerceSelect = form.querySelector("select[name='ecommerce']");
                                if (ecommerceSelect) {
                                    const ecommerceOption = Array.from(ecommerceSelect.options).find(
                                        (opt) => (opt.textContent || "").trim() === ecommerceLabel
                                    );
                                    if (ecommerceOption) {
                                        ecommerceSelect.value = ecommerceOption.value;
                                    }
                                }

                                if (typeof form.requestSubmit === "function") {
                                    form.requestSubmit();
                                } else {
                                    form.submit();
                                }
                                return true;
                            }
                            """,
                            [
                                DEFAULT_SITE_NAME,
                                DEFAULT_SITE_URL,
                                DEFAULT_TIMEZONE,
                                DEFAULT_ECOMMERCE,
                            ],
                        )
                    )
                except Exception:
                    submitted_first_website = False

                if submitted_first_website:
                    _wait_dom_settled(page)
                    _log(
                        "[install] Submitted first website form via form.requestSubmit()."
                    )
                else:
                    _fill_optional_input(
                        page, FIRST_WEBSITE_NAME_SELECTORS, DEFAULT_SITE_NAME
                    )
                    _fill_optional_input(
                        page, FIRST_WEBSITE_URL_SELECTORS, DEFAULT_SITE_URL
                    )

                    _page_warnings(page)

                    try:
                        comboboxes = page.get_by_role("combobox")
                        if _count_locator(comboboxes) > 0:
                            comboboxes.first.click(timeout=2_000)
                            page.get_by_role("listbox").get_by_text(
                                DEFAULT_TIMEZONE
                            ).click(timeout=2_000)
                    except Exception:
                        _log("Timezone selection skipped (not found / changed UI).")

                    try:
                        comboboxes = page.get_by_role("combobox")
                        if _count_locator(comboboxes) > 2:
                            comboboxes.nth(2).click(timeout=2_000)
                            page.get_by_role("listbox").get_by_text(
                                DEFAULT_ECOMMERCE
                            ).click(timeout=2_000)
                    except Exception:
                        _log("Ecommerce selection skipped (not found / changed UI).")

                    _page_warnings(page)

                    _click_next_with_wait(page, timeout_s=INSTALLER_STEP_TIMEOUT_S)

                first_website_progress_deadline = time.time() + INSTALLER_STEP_TIMEOUT_S
                while time.time() < first_website_progress_deadline:
                    _wait_dom_settled(page)
                    if not _has_first_website_name_field(page):
                        break
                    page.wait_for_timeout(300)
                if _has_first_website_name_field(page):
                    _page_warnings(page)
                    raise RuntimeError(
                        "First website form submit did not progress to tracking code "
                        f"within {INSTALLER_STEP_TIMEOUT_S}s "
                        f"(url={page.url}, step={_get_step_hint(page.url)})."
                    )

                _page_warnings(page)

                if _count_locator(page.get_by_role("link", name="Next »")) > 0:
                    page.get_by_role("link", name="Next »").click()
                    _wait_dom_settled(page)
                    _page_warnings(page)

                continue_loc, _ = _first_continue_to_matomo_locator(page)
                if continue_loc is not None:
                    continue_loc.click()
                    _wait_dom_settled(page)
                    _page_warnings(page)

                page.wait_for_timeout(1_000)
                if not is_installed(base_url):
                    _page_warnings(page)
                    raise RuntimeError(
                        "[install] Installer did not reach installed state."
                    )
            except Exception as exc:
                _dump_failure_artifacts(page, reason=str(exc))
                raise
            finally:
                context.close()
                browser.close()

        _log("[install] Installation finished.")

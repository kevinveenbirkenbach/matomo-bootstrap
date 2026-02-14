import unittest

from matomo_bootstrap.installers.web import (
    _click_next_with_wait,
    _count_locator,
    _wait_for_superuser_login_field,
)


class _FlakyLocator:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def count(self) -> int:
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return int(outcome)


class _StaticLocator:
    def __init__(self, page, selector: str):
        self._page = page
        self._selector = selector

    def count(self) -> int:
        if self._selector == "#login-0":
            return 1 if self._page.login_visible else 0
        if self._selector == "#siteName-0":
            return 0
        return 0

    @property
    def first(self):
        return self

    def is_visible(self) -> bool:
        return self.count() > 0


class _RoleLocator:
    def __init__(self, count_value: int):
        self._count_value = count_value

    def count(self) -> int:
        return self._count_value

    @property
    def first(self):
        return self

    def is_visible(self) -> bool:
        return self._count_value > 0


class _NameOnlyStaticLocator:
    def __init__(self, page, selector: str):
        self._page = page
        self._selector = selector

    def count(self) -> int:
        if self._selector == "input[name='login']":
            return 1 if self._page.login_visible else 0
        if self._selector == "input[name='siteName']":
            return 0
        return 0

    @property
    def first(self):
        return self

    def is_visible(self) -> bool:
        return self.count() > 0


class _NoNextButLoginAppearsPage:
    def __init__(self):
        self.url = "http://matomo/index.php?action=setupSuperUser&module=Installation"
        self.login_visible = False
        self._wait_calls = 0

    def locator(self, selector: str):
        return _StaticLocator(self, selector)

    def get_by_role(self, role: str, name: str):
        return _RoleLocator(0)

    def get_by_text(self, *_args, **_kwargs):
        return _RoleLocator(0)

    def title(self) -> str:
        return "setupSuperUser"

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        self._wait_calls += 1
        if self._wait_calls >= 1:
            self.login_visible = True


class _NoNextButNamedLoginAppearsPage:
    def __init__(self):
        self.url = "http://matomo/index.php?action=setupSuperUser&module=Installation"
        self.login_visible = False
        self._wait_calls = 0

    def locator(self, selector: str):
        return _NameOnlyStaticLocator(self, selector)

    def get_by_role(self, role: str, name: str):
        return _RoleLocator(0)

    def get_by_text(self, *_args, **_kwargs):
        return _RoleLocator(0)

    def title(self) -> str:
        return "setupSuperUser"

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        self._wait_calls += 1
        if self._wait_calls >= 1:
            self.login_visible = True


class _DelayedSuperuserLoginPage:
    def __init__(self, *, reveal_after_wait_calls: int | None):
        self.url = "http://matomo/index.php?action=setupSuperUser&module=Installation"
        self.login_visible = False
        self._wait_calls = 0
        self._reveal_after_wait_calls = reveal_after_wait_calls

    def locator(self, selector: str):
        return _StaticLocator(self, selector)

    def get_by_role(self, role: str, name: str):
        return _RoleLocator(0)

    def get_by_text(self, *_args, **_kwargs):
        return _RoleLocator(0)

    def title(self) -> str:
        return "setupSuperUser"

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        self._wait_calls += 1
        if (
            self._reveal_after_wait_calls is not None
            and self._wait_calls >= self._reveal_after_wait_calls
        ):
            self.login_visible = True


class TestWebInstallerLocatorCountIntegration(unittest.TestCase):
    def test_retries_transient_navigation_error(self) -> None:
        locator = _FlakyLocator(
            [
                RuntimeError(
                    "Locator.count: Execution context was destroyed, most likely because of a navigation"
                ),
                RuntimeError(
                    "Locator.count: Execution context was destroyed, most likely because of a navigation"
                ),
                1,
            ]
        )

        result = _count_locator(locator, timeout_s=0.5, retry_interval_s=0.0)

        self.assertEqual(result, 1)
        self.assertEqual(locator.calls, 3)

    def test_raises_non_transient_error_without_retry(self) -> None:
        locator = _FlakyLocator([RuntimeError("Locator is not attached to DOM")])

        with self.assertRaises(RuntimeError):
            _count_locator(locator, timeout_s=0.5, retry_interval_s=0.0)

        self.assertEqual(locator.calls, 1)

    def test_click_next_wait_treats_login_form_as_progress(self) -> None:
        page = _NoNextButLoginAppearsPage()

        step = _click_next_with_wait(page, timeout_s=1)

        self.assertEqual(step, "Installation:setupSuperUser")
        self.assertTrue(page.login_visible)

    def test_click_next_wait_treats_named_login_form_as_progress(self) -> None:
        page = _NoNextButNamedLoginAppearsPage()

        step = _click_next_with_wait(page, timeout_s=1)

        self.assertEqual(step, "Installation:setupSuperUser")
        self.assertTrue(page.login_visible)

    def test_wait_for_superuser_login_field_allows_delayed_form(self) -> None:
        page = _DelayedSuperuserLoginPage(reveal_after_wait_calls=4)

        visible = _wait_for_superuser_login_field(
            page,
            timeout_s=1.0,
            poll_interval_ms=1,
        )

        self.assertTrue(visible)
        self.assertTrue(page.login_visible)

    def test_wait_for_superuser_login_field_times_out_when_absent(self) -> None:
        page = _DelayedSuperuserLoginPage(reveal_after_wait_calls=None)

        visible = _wait_for_superuser_login_field(
            page,
            timeout_s=0.01,
            poll_interval_ms=1,
        )

        self.assertFalse(visible)


if __name__ == "__main__":
    unittest.main()

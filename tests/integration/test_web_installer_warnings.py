import io
import unittest
from contextlib import redirect_stderr


# Import the function under test.
# This keeps the test close to real integration behavior without requiring Playwright.
from matomo_bootstrap.installers.web import _page_warnings


class _FakeLocatorNth:
    def __init__(self, text: str):
        self._text = text

    def inner_text(self) -> str:
        return self._text


class _FakeLocator:
    def __init__(self, texts: list[str]):
        self._texts = texts

    def count(self) -> int:
        return len(self._texts)

    def nth(self, i: int) -> _FakeLocatorNth:
        return _FakeLocatorNth(self._texts[i])


class _FakePage:
    """
    Minimal Playwright-like page stub:
    - locator(selector) -> object with count() / nth(i).inner_text()
    - url, title()
    """

    def __init__(self, *, url: str, title: str, selector_texts: dict[str, list[str]]):
        self.url = url
        self._title = title
        self._selector_texts = selector_texts

    def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._selector_texts.get(selector, []))


class TestWebInstallerWarningsIntegration(unittest.TestCase):
    def test_detects_bootstrap_alert_warning_block(self) -> None:
        """
        Matomo installer commonly renders validation errors like:
          <div class="alert alert-warning"> ... <ul><li>...</li></ul> ... </div>
        We must detect and print those messages to stderr.
        """
        page = _FakePage(
            url="http://matomo/index.php?action=setupSuperUser&module=Installation",
            title="Superuser",
            selector_texts={
                # The key selector from the observed DOM
                ".alert.alert-warning": [
                    "Please fix the following errors:\n"
                    "Password required\n"
                    "Password (repeat) required\n"
                    "The email doesn't have a valid format."
                ],
            },
        )

        buf = io.StringIO()
        with redirect_stderr(buf):
            warnings = _page_warnings(page, prefix="[install]")

        # Function must return the warning text
        self.assertEqual(len(warnings), 1)
        self.assertIn("Please fix the following errors:", warnings[0])
        self.assertIn("The email doesn't have a valid format.", warnings[0])

        # And it must print it to stderr (stdout must remain token-only in the app)
        out = buf.getvalue()
        self.assertIn("[install] page warnings/errors detected", out)
        self.assertIn("Superuser", out)
        self.assertIn("The email doesn't have a valid format.", out)

    def test_deduplicates_repeated_warning_blocks(self) -> None:
        """
        Some Matomo versions repeat the same alert in multiple containers.
        We must return/log each unique text only once.
        """
        repeated = "Please fix the following errors:\nThe email doesn't have a valid format."
        page = _FakePage(
            url="http://matomo/index.php?action=setupSuperUser&module=Installation",
            title="Superuser",
            selector_texts={
                ".alert.alert-warning": [repeated, repeated],
            },
        )

        buf = io.StringIO()
        with redirect_stderr(buf):
            warnings = _page_warnings(page, prefix="[install]")

        self.assertEqual(warnings, [repeated])

        out = buf.getvalue()
        # Only a single numbered entry should be printed
        self.assertIn("[install]  1) ", out)
        self.assertNotIn("[install]  2) ", out)

    def test_no_output_when_no_warnings(self) -> None:
        page = _FakePage(
            url="http://matomo/",
            title="Welcome",
            selector_texts={},
        )

        buf = io.StringIO()
        with redirect_stderr(buf):
            warnings = _page_warnings(page, prefix="[install]")

        self.assertEqual(warnings, [])
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

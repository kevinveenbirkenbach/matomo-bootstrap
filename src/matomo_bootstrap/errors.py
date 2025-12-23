class BootstrapError(RuntimeError):
    """Base error for matomo-bootstrap."""


class MatomoNotReadyError(BootstrapError):
    """Matomo is not reachable or not initialized."""


class TokenCreationError(BootstrapError):
    """Failed to create API token."""

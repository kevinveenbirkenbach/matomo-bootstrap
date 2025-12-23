from __future__ import annotations

import sys

from .cli import parse_args
from .config import config_from_env_and_args
from .errors import BootstrapError
from .service import run


def main() -> int:
    args = parse_args()

    try:
        config = config_from_env_and_args(args)
        token = run(config)
        print(token)
        return 0
    except ValueError as exc:
        # config validation errors
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except BootstrapError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[FATAL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

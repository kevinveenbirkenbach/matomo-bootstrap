from .cli import parse_args
from .bootstrap import run_bootstrap
from .errors import BootstrapError
import sys


def main() -> int:
    args = parse_args()

    try:
        token = run_bootstrap(args)
        print(token)
        return 0
    except BootstrapError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[FATAL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

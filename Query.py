"""
Legacy wrapper that preserves the old `python Query.py` entrypoint.

The project now ships a proper package with `fhtoolkit` as the preferred CLI.
This module is simply proxies to the new implementation.
"""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fhtoolkit.query import main


if __name__ == "__main__":
    raise SystemExit(main())

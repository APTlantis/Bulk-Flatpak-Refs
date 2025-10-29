"""
Legacy wrapper that preserves the old `python Download.py` entrypoint.

Prefer using the packaged CLI: `fhtoolkit download ...`.
"""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fhtoolkit.download import main


if __name__ == "__main__":
    raise SystemExit(main())

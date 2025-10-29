from __future__ import annotations

import argparse
import sys
from typing import Iterable

from . import download, query


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fhtoolkit", description="Flatpak refs utility toolkit.")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    query.add_subparser(subparsers)
    download.add_subparser(subparsers)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

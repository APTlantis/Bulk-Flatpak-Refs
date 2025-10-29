from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable, List, Sequence, Set

PRIMARY_TMPL = "https://dl.flathub.org/repo/appstream/{app_id}.flatpakref"
FALLBACK_TMPL = "https://flathub.org/repo/appstream/{app_id}.flatpakref"

REF_LINE_RE = re.compile(r"^\s*app/([^/]+)/([^/]+)/([^/]+)\s*$")

essential_headers = {
    "User-Agent": "fhtoolkit/1.0 (+https://flathub.org/)",
}


def parse_refs_file(path: str) -> Set[str]:
    app_ids: Set[str] = set()
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = REF_LINE_RE.match(stripped)
            if not match:
                continue
            app_id = match.group(1)
            if "." not in app_id:
                continue
            app_ids.add(app_id)
    return app_ids


def urlretrieve(url: str, dest: str, timeout: int = 30) -> None:
    request = urllib.request.Request(url, headers=essential_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    with open(dest, "wb") as handle:
        handle.write(payload)


def download_flatpakref(app_id: str, out_dir: str, skip_existing: bool = True, timeout: int = 30) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{app_id}.flatpakref")

    if skip_existing and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    urls = [
        PRIMARY_TMPL.format(app_id=app_id),
        FALLBACK_TMPL.format(app_id=app_id),
    ]
    last_error: Exception | None = None
    for url in urls:
        try:
            urlretrieve(url, out_path, timeout=timeout)
            return out_path
        except urllib.error.HTTPError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unknown download failure.")


def collect_app_ids(refs_files: Iterable[str]) -> List[str]:
    collected: Set[str] = set()
    for path in refs_files:
        try:
            collected.update(parse_refs_file(path))
        except FileNotFoundError:
            print(f"Warning: refs file not found: {path}", file=sys.stderr)
    return sorted(collected)


def find_refs_in_dir(refs_dir: str) -> List[str]:
    result: List[str] = []
    for name in os.listdir(refs_dir):
        if name.lower().endswith(".refs"):
            result.append(os.path.join(refs_dir, name))
    return sorted(result)


def _iter_subjects(refs_files: Sequence[str], base_out: str) -> Iterable[tuple[str, str, str]]:
    for refs_path in refs_files:
        subject = os.path.splitext(os.path.basename(refs_path))[0]
        yield subject, refs_path, os.path.join(base_out, subject)


def run(args: argparse.Namespace) -> int:
    refs_files: list[str] = []
    if args.refs_dir:
        if not os.path.isdir(args.refs_dir):
            print(f"Error: --refs-dir does not exist or is not a directory: {args.refs_dir}", file=sys.stderr)
            return 2
        refs_files.extend(find_refs_in_dir(args.refs_dir))
    if args.refs_files:
        refs_files.extend(args.refs_files)

    if not refs_files:
        print("Nothing to do. Provide --refs-file and/or --refs-dir.", file=sys.stderr)
        return 2

    ok = 0
    fail = 0
    seen: set[tuple[str, str]] = set()

    for subject, refs_path, subject_out in _iter_subjects(refs_files, args.out):
        try:
            app_ids = sorted(parse_refs_file(refs_path))
        except FileNotFoundError:
            print(f"Warning: refs file not found: {refs_path}", file=sys.stderr)
            continue

        if not app_ids:
            print(f"No app IDs found in refs file: {refs_path}", file=sys.stderr)
            continue

        print(f"Subject '{subject}': {len(app_ids)} app IDs from {refs_path}")

        for app_id in app_ids:
            if args.limit and ok >= args.limit:
                break

            key = (subject, app_id)
            if key in seen:
                continue

            try:
                out_path = download_flatpakref(
                    app_id,
                    subject_out,
                    skip_existing=args.skip_existing,
                    timeout=args.timeout,
                )
            except Exception as exc:
                fail += 1
                print(f"Error downloading {app_id} (subject {subject}): {exc}", file=sys.stderr)
            else:
                ok += 1
                seen.add(key)
                print(f"[{ok}] Saved {out_path}")

            if args.throttle > 0:
                time.sleep(args.throttle)

        if args.limit and ok >= args.limit:
            break

    print("\n== Summary ==")
    print(f"Successful: {ok}")
    print(f"Failed:     {fail}")
    return 0 if ok > 0 else 1


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--refs-file", "-f", dest="refs_files", action="append",
                        help="Path to a .refs file (repeatable).")
    parser.add_argument("--refs-dir", help="Directory containing *.refs files.")
    parser.add_argument("--out", default="flatpakrefs",
                        help="Directory to store downloaded .flatpakref files (default: flatpakrefs).")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip downloads when the destination file already exists.")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false",
                        help="Overwrite existing files instead of skipping.")
    parser.add_argument("--throttle", type=float, default=0.0,
                        help="Seconds to sleep between downloads to be gentle on the server.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after downloading this many files (0 = no limit).")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout for each download in seconds (default: 30).")
    parser.set_defaults(handler=run)
    return parser


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("download", help="Download .flatpakref files from refs lists.")
    configure_parser(parser)
    parser.set_defaults(command="download")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download .flatpakref descriptors for Flatpak apps.")
    return configure_parser(parser)


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 1
    return args.handler(args)


__all__ = [
    "PRIMARY_TMPL",
    "FALLBACK_TMPL",
    "parse_refs_file",
    "urlretrieve",
    "download_flatpakref",
    "collect_app_ids",
    "find_refs_in_dir",
    "run",
    "configure_parser",
    "add_subparser",
    "build_parser",
    "main",
]

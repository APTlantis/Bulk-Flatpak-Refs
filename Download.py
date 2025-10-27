"""
Download .flatpakref files for apps listed in one or more .refs files produced by Query.py.

Refs format (one per line):
  app/<app_id>/<arch>/<branch>

This script extracts <app_id> and downloads its .flatpakref from Flathub.

Examples:
  # Download .flatpakref files for a single refs file into flatpakrefs/
  python Download.py --refs-file refs/WebBrowser.refs

  # Download for all .refs files in refs/ into out/ directory
  python Download.py --refs-dir refs --out out

  # Combine multiple refs files
  python Download.py -f refs/WebBrowser.refs -f refs/Development.refs

Notes:
- Primary URL used: https://dl.flathub.org/repo/appstream/<app_id>.flatpakref
- Fallback URL:      https://flathub.org/repo/appstream/<app_id>.flatpakref
- This script downloads only the tiny .flatpakref descriptor files, not the app bundles themselves.
"""

import argparse
import os
import re
import sys
import time
from typing import Iterable, Set, List
import urllib.error
import urllib.request

PRIMARY_TMPL = "https://dl.flathub.org/repo/appstream/{app_id}.flatpakref"
FALLBACK_TMPL = "https://flathub.org/repo/appstream/{app_id}.flatpakref"

REF_LINE_RE = re.compile(r"^\s*app/([^/]+)/([^/]+)/([^/]+)\s*$")


def parse_refs_file(path: str) -> Set[str]:
    app_ids: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = REF_LINE_RE.match(line)
            if not m:
                # Ignore malformed lines silently
                continue
            app_id = m.group(1)
            # Basic sanity: App IDs usually contain at least one dot
            if "." not in app_id:
                continue
            app_ids.add(app_id)
    return app_ids


essential_headers = {
    "User-Agent": "Query-Flathub-Downloader/1.0 (+https://flathub.org/)"
}


def urlretrieve(url: str, dest: str, timeout: int = 30) -> None:
    req = urllib.request.Request(url, headers=essential_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)


def download_flatpakref(app_id: str, out_dir: str, skip_existing: bool = True, timeout: int = 30) -> str:
    """Download .flatpakref for given app_id. Returns the output path or raises on failure."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{app_id}.flatpakref")

    if skip_existing and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    # Try primary then fallback
    urls = [PRIMARY_TMPL.format(app_id=app_id), FALLBACK_TMPL.format(app_id=app_id)]
    last_err: Exception | None = None
    for url in urls:
        try:
            urlretrieve(url, out_path, timeout=timeout)
            return out_path
        except urllib.error.HTTPError as e:
            # 404 or other HTTP error: try next
            last_err = e
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("Unknown download failure")


def collect_app_ids(refs_files: Iterable[str]) -> List[str]:
    all_ids: Set[str] = set()
    for rf in refs_files:
        try:
            ids = parse_refs_file(rf)
            all_ids.update(ids)
        except FileNotFoundError:
            print(f"Warning: refs file not found: {rf}", file=sys.stderr)
    return sorted(all_ids)


def find_refs_in_dir(refs_dir: str) -> List[str]:
    out: List[str] = []
    for name in os.listdir(refs_dir):
        if name.lower().endswith(".refs"):
            out.append(os.path.join(refs_dir, name))
    return sorted(out)


def main():
    p = argparse.ArgumentParser(description="Download .flatpakref files for apps listed in .refs files.")
    p.add_argument("--refs-file", "-f", action="append", dest="refs_files", help="Path to a .refs file (repeatable)")
    p.add_argument("--refs-dir", help="Directory containing *.refs files")
    p.add_argument("--out", default="flatpakrefs", help="Output base directory for downloaded .flatpakref files (default: flatpakrefs). When multiple refs files are provided, files are saved under per-subject subdirectories named after each .refs filename.")
    p.add_argument("--skip-existing", action="store_true", default=True, help="Skip downloads if the .flatpakref already exists (default: on)")
    p.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="Do not skip existing files; overwrite")
    p.add_argument("--throttle", type=float, default=0.0, help="Seconds to sleep between downloads to be gentle on server")
    p.add_argument("--limit", type=int, default=0, help="Stop after downloading this many .flatpakref files (0 = no limit)")
    args = p.parse_args()

    refs_files: List[str] = []
    if args.refs_dir:
        if not os.path.isdir(args.refs_dir):
            print(f"Error: --refs-dir does not exist or is not a directory: {args.refs_dir}", file=sys.stderr)
            sys.exit(2)
        refs_files.extend(find_refs_in_dir(args.refs_dir))
    if args.refs_files:
        refs_files.extend(args.refs_files)

    if not refs_files:
        print("Nothing to do. Provide --refs-file and/or --refs-dir.", file=sys.stderr)
        sys.exit(2)

    # Process per refs file to organize by subject (filename stem)
    ok = 0
    fail = 0
    seen_in_subject: set[tuple[str, str]] = set()  # (subject, app_id)

    for rf in refs_files:
        subject = os.path.splitext(os.path.basename(rf))[0]
        subject_out_dir = os.path.join(args.out, subject)
        try:
            app_ids = sorted(parse_refs_file(rf))
        except FileNotFoundError:
            print(f"Warning: refs file not found: {rf}", file=sys.stderr)
            continue

        if not app_ids:
            print(f"No app IDs found in refs file: {rf}", file=sys.stderr)
            continue

        print(f"Subject '{subject}': {len(app_ids)} app IDs from {rf}")

        for app_id in app_ids:
            if args.limit and ok >= args.limit:
                break
            key = (subject, app_id)
            if key in seen_in_subject:
                continue  # already handled for this subject
            try:
                out_path = download_flatpakref(app_id, subject_out_dir, skip_existing=args.skip_existing)
                ok += 1
                seen_in_subject.add(key)
                print(f"[{ok}] Saved {out_path}")
            except Exception as e:
                fail += 1
                print(f"Error downloading {app_id} (subject {subject}): {e}", file=sys.stderr)
            if args.throttle > 0:
                time.sleep(args.throttle)
        if args.limit and ok >= args.limit:
            break

    print("\n== Summary ==")
    print(f"Successful: {ok}")
    print(f"Failed:     {fail}")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

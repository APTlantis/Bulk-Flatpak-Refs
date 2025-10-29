from __future__ import annotations

import argparse
import gzip
import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from typing import Iterable, Iterator

APPSTREAM_URL_TMPL = "https://dl.flathub.org/repo/appstream/{arch}/appstream.xml.gz"


def fetch_appstream(arch: str) -> bytes:
    """Fetch and decompress the AppStream XML for the given architecture."""
    url = APPSTREAM_URL_TMPL.format(arch=arch)
    with urllib.request.urlopen(url) as response:
        payload = response.read()
    return gzip.decompress(payload)


def iter_components(xml_bytes: bytes) -> Iterator[dict[str, object]]:
    """Stream AppStream components to keep memory usage low."""
    ctx = ET.iterparse(io.BytesIO(xml_bytes), events=("start", "end"))
    _, root = next(ctx)
    in_component = False
    comp: dict[str, object] = {}
    cats: list[str] = []

    for event, elem in ctx:
        tag = elem.tag.split("}")[-1]

        if event == "start" and tag == "component":
            in_component = True
            comp = {"type": elem.attrib.get("type", "")}
            cats = []
            continue

        if event != "end" or not in_component:
            continue

        if tag == "id":
            comp["id"] = (elem.text or "").strip()
        elif tag == "category":
            val = (elem.text or "").strip()
            if val:
                cats.append(val)
        elif tag == "categories":
            comp["categories"] = cats[:]
        elif tag == "component":
            yield comp
            comp = {}
            cats = []
            in_component = False
            root.clear()


def normalize_category(cat: str) -> str:
    return cat.strip().replace(" ", "")


def make_ref(app_id: str, arch: str, branch: str) -> str:
    return f"app/{app_id}/{arch}/{branch}"


def _write_file(path: str, lines: Iterable[str]) -> None:
    uniq = sorted(set(lines))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for line in uniq:
            handle.write(line + "\n")
    print(f"Wrote {path}  ({len(uniq)} refs)")


def run(args: argparse.Namespace) -> int:
    if not args.dump_categories and not args.all and not args.categories:
        print("Nothing to do. Use --dump-categories, --all, or -c/--category.", file=sys.stderr)
        return 2

    xml_bytes = fetch_appstream(args.arch)

    by_cat: dict[str, set[str]] = defaultdict(set)
    cat_counter: Counter[str] = Counter()

    for component in iter_components(xml_bytes):
        app_id = str(component.get("id", "")).strip()
        cats = component.get("categories", []) or []

        if not app_id or "." not in app_id:
            continue

        for category in cats:
            norm = normalize_category(category)
            cat_counter[norm] += 1
            by_cat[norm].add(app_id)

    if args.dump_categories:
        print("== Category counts ==")
        for cat, count in cat_counter.most_common():
            print(f"{cat:20} {count}")
        return 0

    os.makedirs(args.out, exist_ok=True)

    if args.all:
        for cat, ids in sorted(by_cat.items()):
            refs = (make_ref(app_id, args.arch, args.branch) for app_id in ids)
            _write_file(os.path.join(args.out, f"{cat}.refs"), refs)
        return 0

    selected = [normalize_category(c) for c in (args.categories or [])]
    unknown = [c for c in selected if c not in by_cat]
    if unknown:
        print("Warning: no matches for categories: " + ", ".join(unknown), file=sys.stderr)

    if args.merge_to:
        merged: list[str] = []
        for category in selected:
            merged.extend(make_ref(app_id, args.arch, args.branch) for app_id in by_cat.get(category, []))
        _write_file(os.path.join(args.out, args.merge_to), merged)
        return 0

    for category in selected:
        refs = [make_ref(app_id, args.arch, args.branch) for app_id in by_cat.get(category, [])]
        if not refs:
            print(f"Note: {category} had 0 refs.", file=sys.stderr)
        _write_file(os.path.join(args.out, f"{category}.refs"), refs)
    return 0


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("-c", "--category", dest="categories", action="append",
                        help="AppStream category to include (repeatable).")
    parser.add_argument("--all", action="store_true",
                        help="Generate refs for all categories (one file per category).")
    parser.add_argument("--dump-categories", action="store_true",
                        help="Print category counts and exit.")
    parser.add_argument("--arch", default="x86_64", help="Flatpak architecture (default: x86_64).")
    parser.add_argument("--branch", default="stable", help="Flatpak branch (default: stable).")
    parser.add_argument("--out", default="refs", help="Output directory for *.refs files (default: refs).")
    parser.add_argument("--merge-to", default=None,
                        help="If set, merge refs into a single file with this name.")
    parser.set_defaults(handler=run)
    return parser


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("dump", help="Generate Flatpak ref lists from Flathub AppStream.")
    return configure_parser(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Flatpak refs from Flathub AppStream.")
    return configure_parser(parser)


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 1
    return args.handler(args)


__all__ = [
    "APPSTREAM_URL_TMPL",
    "fetch_appstream",
    "iter_components",
    "normalize_category",
    "make_ref",
    "run",
    "configure_parser",
    "add_subparser",
    "build_parser",
    "main",
]

""""
Generate Flatpak ref lists from Flathub AppStream by category.

Examples:
  # Dump category counts (no files written)
  ./flathub_select_refs.py --dump-categories

  # Generate refs for browsers + development (x86_64, stable) into refs/
  ./flathub_select_refs.py -c WebBrowser -c Development

  # Generate ALL categories into refs/ (one file per category)
  ./flathub_select_refs.py --all

  # Merge multiple categories into a single file (Browsers+Dev.refs)
  ./flathub_select_refs.py -c WebBrowser -c Development --merge-to Browsers+Dev.refs

  # Different arch/branch and an output dir
  ./flathub_select_refs.py -c Development --arch aarch64 --branch stable --out refs-aarch64
"""

import argparse
import gzip
import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

APPSTREAM_URL_TMPL = "https://dl.flathub.org/repo/appstream/{arch}/appstream.xml.gz"

def fetch_appstream(arch: str) -> bytes:
    url = APPSTREAM_URL_TMPL.format(arch=arch)
    with urllib.request.urlopen(url) as r:
        gz = r.read()
    return gzip.decompress(gz)

def iter_components(xml_bytes: bytes):
    # Stream parse to keep memory low
    ctx = ET.iterparse(io.BytesIO(xml_bytes), events=("start", "end"))
    _, root = next(ctx)  # get root element
    in_component = False
    comp = {}
    cats = []

    for event, elem in ctx:
        tag = elem.tag.split('}')[-1]  # strip namespace if present

        if event == "start" and tag == "component":
            in_component = True
            comp = {"type": elem.attrib.get("type", "")}
            cats = []

        elif event == "end":
            if in_component:
                if tag == "id":
                    comp["id"] = (elem.text or "").strip()
                elif tag == "category":
                    val = (elem.text or "").strip()
                    if val:
                        cats.append(val)
                elif tag == "categories":
                    comp["categories"] = cats[:]
                elif tag == "component":
                    # yield once per component
                    yield comp
                    # clear to free memory
                    comp = {}
                    cats = []
                    in_component = False
                    root.clear()

def normalize_category(cat: str) -> str:
    # Keep original, but you can tweak a few common aliases here if you want.
    # For example, AppStream uses "Network" not "Internet", etc.
    return cat.strip().replace(" ", "")

def make_ref(app_id: str, arch: str, branch: str) -> str:
    return f"app/{app_id}/{arch}/{branch}"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--category", dest="categories", action="append",
                   help="AppStream category to include (repeatable). Example: WebBrowser, Development")
    p.add_argument("--all", action="store_true",
                   help="Generate refs for ALL categories (one file per category).")
    p.add_argument("--dump-categories", action="store_true",
                   help="Just print category counts and exit.")
    p.add_argument("--arch", default="x86_64", help="Flatpak arch (default: x86_64)")
    p.add_argument("--branch", default="stable", help="Flatpak branch (default: stable)")
    p.add_argument("--out", default="refs", help="Output directory for *.refs files (default: refs)")
    p.add_argument("--merge-to", default=None,
                   help="If set, merge refs from the selected categories into a single file with this name")
    args = p.parse_args()

    if not args.dump_categories and not args.all and not args.categories:
        print("Nothing to do. Use --dump-categories, --all, or -c/--category.", file=sys.stderr)
        sys.exit(2)

    xml_bytes = fetch_appstream(args.arch)

    # Build: cat -> set(app_ids)
    by_cat = defaultdict(set)
    cat_counter = Counter()

    # We’ll include only desktop apps and apps with plausible IDs.
    for comp in iter_components(xml_bytes):
        app_id = comp.get("id", "")
        ctype = comp.get("type", "")
        cats = comp.get("categories", []) or []

        if not app_id or "." not in app_id:
            continue  # skip garbage IDs

        # Restrict to apps; you can relax this if you want extensions/addons
        if ctype and ctype not in ("desktop", "desktop-application", "console-application", "web-application", "agile"):
            # AppStream varies; we keep the common interactive types.
            pass  # not strictly filtering by type; flathub contains mixed types; keep flexibility

        # Track category counts
        for c in cats:
            cat_counter[normalize_category(c)] += 1

        # Assign the app to each normalized category it declares
        for c in cats:
            by_cat[normalize_category(c)].add(app_id)

    if args.dump_categories:
        print("== Category counts ==")
        for cat, cnt in cat_counter.most_common():
            print(f"{cat:20} {cnt}")
        return

    os.makedirs(args.out, exist_ok=True)

    def write_file(path, lines):
        uniq = sorted(set(lines))
        with open(path, "w", encoding="utf-8") as f:
            for line in uniq:
                f.write(line + "\n")
        print(f"Wrote {path}  ({len(uniq)} refs)")

    if args.all:
        for cat, ids in sorted(by_cat.items()):
            refs = [make_ref(i, args.arch, args.branch) for i in ids]
            write_file(os.path.join(args.out, f"{cat}.refs"), refs)
        return

    # Specific categories
    selected = [normalize_category(c) for c in (args.categories or [])]
    unknown = [c for c in selected if c not in by_cat]
    if unknown:
        print("Warning: no matches for categories:", ", ".join(unknown), file=sys.stderr)

    if args.merge_to:
        merged = []
        for c in selected:
            merged.extend(make_ref(i, args.arch, args.branch) for i in by_cat.get(c, []))
        write_file(os.path.join(args.out, args.merge_to), merged)
    else:
        for c in selected:
            refs = [make_ref(i, args.arch, args.branch) for i in by_cat.get(c, [])]
            if not refs:
                print(f"Note: {c} had 0 refs.", file=sys.stderr)
            write_file(os.path.join(args.out, f"{c}.refs"), refs)

if __name__ == "__main__":
    main()
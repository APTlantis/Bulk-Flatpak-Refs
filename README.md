# Flathub Refs Toolkit

[![PyCharm](https://img.shields.io/badge/PyCharm-000?logo=pycharm&logoColor=fff)](#)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=fff)](#)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff)](#)
[![PyPI](https://img.shields.io/badge/PyPI-3775A9?logo=pypi&logoColor=fff)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Generate category-based Flatpak ref lists from Flathub AppStream metadata and download the matching `.flatpakref` descriptors. The toolkit now ships as an installable package that exposes a single `fhtoolkit` command with dedicated `dump` and `download` subcommands.

## Features
- Stream the AppStream catalog by architecture to produce `.refs` files per category or as a merged list.
- Download `.flatpakref` descriptor files for every app contained in any `.refs` list.
- Uses only the Python standard library; no external dependencies required.
- Distribute as a Python package or run straight from the provided Docker image.

## Installation

### Local environment (pip / pipx)
```bash
python -m pip install .
# or, for an editable install during development:
python -m pip install --editable .
```
This adds `fhtoolkit` to your PATH. Use `pipx install .` if you prefer isolated command installations.

### Docker
```bash
docker build -t fhtoolkit .
docker run --rm fhtoolkit --help
```
Mount host directories when generating output, for example:
```bash
# Windows PowerShell example
docker run --rm -v "$PWD\refs:/refs" fhtoolkit dump --all --out /refs
```

## Usage

### Dump refs from AppStream
```bash
# Print category counts
fhtoolkit dump --dump-categories

# Generate refs for two categories into refs/
fhtoolkit dump -c WebBrowser -c Development --out refs

# Dump every category (one file per category)
fhtoolkit dump --all --out ref_lists

# Merge multiple categories into a single file
fhtoolkit dump -c WebBrowser -c Development --merge-to Browsers+Dev.refs --out refs

# Switch architecture or branch
fhtoolkit dump -c Graphics --arch aarch64 --branch stable --out refs-aarch64
```

### Download `.flatpakref` descriptors
```bash
# From a single refs file
fhtoolkit download --refs-file refs/WebBrowser.refs --out flatpakrefs

# From every refs file in a directory
fhtoolkit download --refs-dir refs --out flatpakrefs

# Combine explicit refs files
fhtoolkit download -f refs/WebBrowser.refs -f refs/Development.refs --out flatpakrefs
```
Helpful flags:
- `--throttle <seconds>`: pause between downloads to be gentle on the server.
- `--limit <N>`: stop after N successful downloads (`0` = no limit).
- `--no-skip-existing`: overwrite `.flatpakref` files instead of skipping them.

### Legacy scripts
`Query.py` and `Download.py` remain as thin wrappers so existing automation keeps working:
```bash
python Query.py --all --out refs
python Download.py --refs-dir refs --out flatpakrefs
```

## `.refs` format
Each line contains a Flatpak ref in the form:
```
app/<app_id>/<arch>/<branch>
```
Comments and blank lines are ignored by the downloader.

## Troubleshooting
- 404/HTTP errors: the app might not expose a `.flatpakref` at the expected location; the downloader automatically retries using the Flathub web mirror.
- Empty output: double check category names with `fhtoolkit dump --dump-categories` and verify the chosen architecture/branch combination.
- On Windows, remember to quote paths that contain spaces.

## Attribution
Data is sourced from the public Flathub AppStream catalog and `.flatpakref` endpoints.

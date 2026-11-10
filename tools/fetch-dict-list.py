#!/usr/bin/env python3
"""fetch-dict-list.py — Generate the bundled dictionary download catalog.

This script fetches the release assets from the
``libreoffice-dictionaries-collection`` GitHub repository and writes the
``dictionaries.json`` catalog that ships as package data under
``pyqt6_linguistic_tools/data/``.

Usage:
  python3 tools/fetch-dict-list.py [--tag TAG] [--output PATH]

  By default it fetches the latest release and writes
  ``src/pyqt6_linguistic_tools/data/dictionaries.json``.

  Pass ``--tag v1.0-dictionaries-thesaurus`` to pin a release, and
  ``--output`` to write a different file.

Output:
  A JSON object with ``source`` and ``dictionaries`` entries. When GitHub
  exposes an asset digest, the corresponding ``sha256`` field is included.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path


REPO = "wachin/libreoffice-dictionaries-collection"
API_URL = f"https://api.github.com/repos/{REPO}/releases"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = (
    REPO_ROOT / "src" / "pyqt6_linguistic_tools" / "data" / "dictionaries.json"
)
_SHA256_DIGEST = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


def fetch_release(tag: str | None = None) -> dict:
    """Fetch release data from GitHub API."""
    url = f"{API_URL}/tags/{tag}" if tag else f"{API_URL}/latest"
    print(f"Fetching: {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def build_dict_list(release: dict) -> list[dict]:
    """Build a sorted list of dictionaries from release assets.

    Each entry has the shape::

        {
            "code": "en_US",
            "name": "English (US)",
            "url": "https://github.com/.../dict-en.tar.gz",
            "size": 6930000
        }
    """
    lang_labels = {
        "af": "Afrikaans",
        "an": "Aragonese",
        "ar": "Arabic",
        "be": "Belarusian",
        "bg": "Bulgarian",
        "bn": "Bengali",
        "bo": "Classical Tibetan",
        "br": "Breton",
        "bs": "Bosnian",
        "ca": "Catalan",
        "ckb": "Central Kurdish",
        "cs": "Czech",
        "da": "Danish",
        "de": "German",
        "el": "Modern Greek",
        "en": "English",
        "eo": "Esperanto",
        "es": "Spanish",
        "et": "Estonian",
        "fa": "Persian",
        "fr": "French",
        "gd": "Scottish Gaelic",
        "gl": "Galician",
        "gu": "Gujarati",
        "he": "Hebrew",
        "hi": "Hindi",
        "hr": "Croatian",
        "hu": "Hungarian",
        "id": "Indonesian",
        "is": "Icelandic",
        "it": "Italian",
        "ko": "Korean",
        "lo": "Lao",
        "lt": "Lithuanian",
        "lv": "Latvian",
        "mn": "Mongolian",
        "ne": "Nepali",
        "nl": "Dutch",
        "no": "Norwegian",
        "oc": "Occitan",
        "pl": "Polish",
        "pt-BR": "Portuguese (Brazil)",
        "pt-PT": "Portuguese (Portugal)",
        "ro": "Romanian",
        "ru": "Russian",
        "si": "Sinhalese",
        "sk": "Slovak",
        "sl": "Slovenian",
        "sq": "Albanian",
        "sr": "Serbian",
        "sv": "Swedish",
        "te": "Telugu",
        "th": "Thai",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "vi": "Vietnamese",
        "zu": "Zulu",
    }

    # Match asset names like "dict-en.tar.gz" → code "en"
    pattern = re.compile(r"^dict-([a-zA-Z-]+)\.tar\.gz$")
    entries: list[dict] = []

    for asset in release.get("assets", []):
        name = asset["name"]
        m = pattern.match(name)
        if not m:
            continue
        code = m.group(1)
        # Map dict-pt-BR → code "pt_BR" for the spell checker
        lang_code = code.replace("-", "_")
        label = lang_labels.get(code, code.replace("-", " ").title())
        digest = asset.get("digest")
        digest_match = (
            _SHA256_DIGEST.match(digest) if isinstance(digest, str) else None
        )
        entry = {
            "code": lang_code,
            "name": label,
            "url": asset["browser_download_url"],
            "size": asset["size"],
        }
        if digest_match is not None:
            entry["sha256"] = digest_match.group(1).lower()
        entries.append(entry)

    entries.sort(key=lambda e: e["code"])
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the bundled dictionary catalog from GitHub release assets"
    )
    parser.add_argument(
        "--tag",
        help="Release tag (default: latest)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output catalog path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    release = fetch_release(args.tag)
    entries = build_dict_list(release)

    payload = {
        "source": f"{REPO}/releases/tag/{args.tag or release['tag_name']}",
        "dictionaries": entries,
    }
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as catalog_file:
        json.dump(payload, catalog_file, indent=2, ensure_ascii=False)
        catalog_file.write("\n")

    print(f"Written {len(entries)} dictionaries to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
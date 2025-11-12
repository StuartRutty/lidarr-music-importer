#!/usr/bin/env python3
"""
Smoke-friendly universal parser CLI for `--help` validation and quick checks.

This minimal script intentionally implements only a small subset of the real
universal parser to avoid touching the larger, in-progress `universal_parser.py`.
Use this for smoke tests and CI checks that confirm the CLI surface is stable.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from typing import List


@dataclass
class AlbumEntry:
    artist: str
    album: str


class UniversalParser:
    def __init__(self, fuzzy_threshold: int = 85, normalize: bool = True):
        self.fuzzy_threshold = fuzzy_threshold
        self.normalize = normalize
        self.entries: List[AlbumEntry] = []
        self.stats = {"raw_entries": 0}

    def detect_format(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                first = f.readline()
        except Exception:
            return "unknown"

        if "Track Name" in first or "Artist Name" in first:
            return "spotify_csv"
        if "," in first:
            return "simple_csv"
        if "\t" in first:
            return "tsv"
        if " - " in first:
            return "text_dash"
        return "unknown"

    def parse_file(self, path: str) -> None:
        fmt = self.detect_format(path)
        self.stats["format_detected"] = fmt
        try:
            with open(path, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    self.stats["raw_entries"] += 1
                    if " - " in ln:
                        a, b = [p.strip() for p in ln.split(" - ", 1)]
                        self.entries.append(AlbumEntry(a, b))
        except FileNotFoundError:
            raise

    def write_output(self, out_path: str) -> None:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["artist", "album"])
            for e in self.entries:
                w.writerow([e.artist, e.album])

    def print_statistics(self) -> None:
        print(f"Format detected: {self.stats.get('format_detected', 'unknown')}")
        print(f"Raw entries parsed: {self.stats.get('raw_entries', 0)}")
        print(f"Final unique pairs: {len(self.entries)}")


def build_parser() -> argparse.ArgumentParser:
    epilog = """
EXAMPLES:
  py -3 scripts/universal_parser_smoke.py input.txt -o albums.csv

QUICK ALIAS (optional):
  PowerShell (add to $PROFILE):
    function up { py -3 "C:\\path\\to\\repo\\scripts\\universal_parser_smoke.py" @args }

  Bash:
    alias up='py -3 /path/to/repo/scripts/universal_parser_smoke.py'
"""

    p = argparse.ArgumentParser(
        description="Universal parser (smoke CLI)",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("input", help="Input file (CSV, TSV, or text)")
    p.add_argument("-o", "--output", default="albums.csv", help="Output CSV file (default: albums.csv)")
    p.add_argument("--dry-run", action="store_true", help="Parse and show stats without writing output")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    up = UniversalParser()
    try:
        up.parse_file(args.input)
    except FileNotFoundError:
        logging.error(f"File not found: {args.input}")
        sys.exit(1)

    up.print_statistics()

    if not args.dry_run:
        up.write_output(args.output)
        logging.info(f"Wrote output to {args.output}")


if __name__ == '__main__':
    main()

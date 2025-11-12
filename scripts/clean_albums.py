#!/usr/bin/env python3
"""
Clean special characters from albums.csv for MusicBrainz and Lidarr compatibility.
Removes problematic characters like brackets, dollar signs, and other special chars
that can cause issues with music database lookups.
"""

"""Clean albums CSV using library IO and text helpers.

This script is a thin wrapper that reads `albums.csv`, applies `clean_text`
to `artist` and `album` fields, and writes the CSV back (creating a timestamped backup).
"""

from pathlib import Path
from typing import List, Dict
import argparse
import logging

from lib.parser_utils import clean_text, read_csv_to_rows, write_rows_to_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean artist/album fields in a CSV file")
    parser.add_argument('input', nargs='?', default='albums.csv', help='Path to CSV file (default: albums.csv)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input)
    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}")
        return

    rows, fieldnames = read_csv_to_rows(input_path)
    cleaned = 0
    out_rows: List[Dict[str, str]] = []

    for r in rows:
        original = r.copy()
        if 'artist' in r and 'album' in r:
            r['artist'] = clean_text(r.get('artist', ''))
            r['album'] = clean_text(r.get('album', ''))
        if r != original:
            cleaned += 1
            logging.info(f"Cleaned: '{original.get('artist','')}' -> '{r.get('artist','')}', '{original.get('album','')}' -> '{r.get('album','')}'")
        out_rows.append(r)

    write_rows_to_csv(input_path, out_rows, fieldnames, make_backup=True)

    print(f"\nCleaning complete — {len(rows)} rows processed, {cleaned} cleaned.")


if __name__ == '__main__':
    main()
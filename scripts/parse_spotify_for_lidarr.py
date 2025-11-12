#!/usr/bin/env python3
"""
parse_spotify_for_lidarr.py

Parse Spotify liked music CSV export to create artist/album pairs for Lidarr import.
Filters out artists with <3 total saved songs and albums with <2 total saved songs.

Output formats:
- CSV: artist,album for direct import to modified add_artists_to_lidarr.py
- JSON: structured data with counts for analysis
"""

import csv
import json
import argparse
import logging
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional

from lib.parser_utils import parse_spotify_export, filter_artist_albums, generate_artist_album_output, print_spotify_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def parse_spotify_csv(csv_path: str) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """Wrapper that delegates to lib.parser_utils.parse_spotify_export."""
    return parse_spotify_export(csv_path)


def filter_data(artist_albums: Dict[str, Dict[str, int]], artist_totals: Dict[str, int], min_artist_songs: int = 3, min_album_songs: int = 2) -> Dict[str, Dict[str, int]]:
    return filter_artist_albums(artist_albums, artist_totals, min_artist_songs=min_artist_songs, min_album_songs=min_album_songs)


def generate_output(filtered_data: Dict[str, Dict[str, int]], output_csv: str, output_json: Optional[str] = None):
    return generate_artist_album_output(filtered_data, output_csv, output_json)


def print_statistics(artist_totals: Dict[str, int], filtered_data: Dict[str, Dict[str, int]], min_artist_songs: int, min_album_songs: int):
    return print_spotify_stats(artist_totals, filtered_data, min_artist_songs, min_album_songs)


def main():
    parser = argparse.ArgumentParser(
        description="Parse Spotify CSV for Lidarr import",
        epilog="""
QUICK ALIAS (optional):
  Add a short wrapper if you like (replace /path/to/repo):

    PowerShell (add to $PROFILE):
        function ps2pairs { py -3 "C:\\path\\to\\repo\\scripts\\parse_spotify_for_lidarr.py" @args }

    Bash (add to ~/.bashrc):
        alias ps2pairs='py -3 /path/to/repo/scripts/parse_spotify_for_lidarr.py'

Run directly:
    py -3 scripts/parse_spotify_for_lidarr.py my_spotify_export.csv
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_csv", help="Path to Spotify liked songs CSV export")
    parser.add_argument("-o", "--output", default="artist_album_pairs.csv", 
                       help="Output CSV file (default: artist_album_pairs.csv)")
    parser.add_argument("--json", help="Optional JSON output file for analysis")
    parser.add_argument("--min-artist-songs", type=int, default=3,
                       help="Minimum songs per artist (default: 3)")
    parser.add_argument("--min-album-songs", type=int, default=2,
                       help="Minimum songs per album (default: 2)")
    parser.add_argument("--stats-only", action="store_true",
                       help="Only show statistics, don't generate output files")
    
    args = parser.parse_args()
    
    # Parse the CSV
    logging.info(f"Parsing Spotify CSV: {args.input_csv}")
    artist_albums, artist_totals = parse_spotify_csv(args.input_csv)
    
    # Apply filters
    filtered_data = filter_data(artist_albums, artist_totals, 
                               args.min_artist_songs, args.min_album_songs)
    
    # Show statistics
    print_statistics(artist_totals, filtered_data, 
                    args.min_artist_songs, args.min_album_songs)
    
    # Generate output files (unless stats-only)
    if not args.stats_only:
        generate_output(filtered_data, args.output, args.json)


if __name__ == "__main__":
    main()
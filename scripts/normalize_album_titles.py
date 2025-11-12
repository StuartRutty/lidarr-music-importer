#!/usr/bin/env python3
"""
normalize_album_titles.py - Album Title Preprocessing for Lidarr Import

This script preprocesses a CSV file containing artist/album pairs by normalizing
album titles to improve MusicBrainz lookup success rates. It removes common
edition qualifiers that often interfere with searches.

FEATURES:
- Removes edition markers like (Deluxe), (Remastered), [Explicit], etc.
- Preserves original titles in a backup column for reference
- Only processes albums with specific statuses (configurable)
- Creates a backup of the original file
- Detailed logging of all changes made

USAGE:
    py -3 normalize_album_titles.py albums.csv
    py -3 normalize_album_titles.py albums.csv --dry-run
    py -3 normalize_album_titles.py albums.csv --status-filter pending_refresh,skip_no_musicbrainz

The script will:
1. Create a backup: albums_backup_YYYYMMDD_HHMMSS.csv
2. Add an 'original_album' column to preserve original titles
3. Normalize album titles in the 'album' column
4. Log all changes to the console

EXAMPLES OF NORMALIZATION:
    "Drip Season 3 (Deluxe)" -> "Drip Season 3"
    "Good Kid M.A.A.D City (Deluxe Edition)" -> "Good Kid M.A.A.D City"
    "Born Sinner (Remastered)" -> "Born Sinner"
    "The Life Of Pablo [Explicit]" -> "The Life Of Pablo"
    "Views (Deluxe Version)" -> "Views"

QUICK ALIAS (optional):
    If you'd like a short command to run this script interactively, add one of the
    following to your shell (replace /path/to/repo):

    PowerShell (add to $PROFILE):
        function nat { py -3 "C:\\path\\to\\repo\\scripts\\normalize_album_titles.py" @args }

    Bash (add to ~/.bashrc):
        alias nat='py -3 /path/to/repo/scripts/normalize_album_titles.py'
"""

import csv
import re
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Any, Optional
from lib.parser_utils import normalize_album_title, needs_normalization, process_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)



# process_csv and create_backup moved to lib.parser_utils; we import process_csv above

def main():
    parser = argparse.ArgumentParser(
        description="Normalize album titles in CSV file to improve MusicBrainz lookup success",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'csv_file',
        type=Path,
        help='Path to the CSV file containing artist/album data'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying the file'
    )
    
    parser.add_argument(
        '--status-filter',
        type=str,
        help='Comma-separated list of status values to process (e.g., "pending_refresh,skip_no_musicbrainz")'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse status filter
    status_filter = None
    if args.status_filter:
        status_filter = set(s.strip() for s in args.status_filter.split(','))
        logging.info(f"Processing only rows with status: {sorted(status_filter)}")
    
    try:
        if args.dry_run:
            logging.info("DRY RUN MODE - No changes will be made to the file")

        stats = process_csv(args.csv_file, status_filter, args.dry_run)
        
        # Print summary
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total rows in file: {stats['total_rows']}")
        print(f"Rows processed: {stats['processed_rows']}")
        print(f"Rows changed: {stats['changed_rows']}")
        print(f"Rows skipped (status filter): {stats['skipped_by_status']}")
        
        if stats['changes']:
            print(f"\nCHANGES MADE:")
            for change in stats['changes']:
                print(f"  Row {change['row']}: {change['artist']}")
                print(f"    Before: {change['original']}")
                print(f"    After:  {change['normalized']}")
                print(f"    Status: {change['status']}")
        
        if args.dry_run and stats['changed_rows'] > 0:
            print(f"\nTo apply these changes, run without --dry-run")
        elif not args.dry_run and stats['changed_rows'] > 0:
            print(f"\nChanges saved to: {args.csv_file}")
            
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
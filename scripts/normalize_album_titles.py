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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def normalize_album_title(album_title: str) -> str:
    """
    Normalize album titles by removing common edition qualifiers that might interfere 
    with MusicBrainz searches while preserving meaningful qualifiers.
    
    This function intelligently removes edition markers like (Deluxe), (Remastered), etc.,
    while preserving important qualifiers like volume numbers, subtitle descriptors, 
    collaborators, and unique identifiers that are part of the actual album title.
    
    REMOVES (edition markers):
        - (Deluxe), (Deluxe Edition), (Deluxe Version)
        - (Remastered), (Remastered Edition), (20th Anniversary Remaster)
        - (Extended), (Complete), (Expanded Edition)
        - (Explicit), (Clean)
        - (Collector's Edition), (Special Edition)
        
    KEEPS (meaningful qualifiers):
        - (Vol. 2), (Volume 1) - volume numbers
        - (& Metro Boomin) - collaborators
        - (Heroes Version) - distinct version names
        - (Shake the City) - subtitles/descriptors
        - (sic) - intentional misspelling markers
        - (EP), (LP) - when part of actual title
        - (Instrumentals), (ChopNotSlop) - when it's a distinct version with different content
    
    Args:
        album_title: Original album title
        
    Returns:
        Normalized album title with edition markers removed
    """
    if not album_title:
        return album_title
    
    # Patterns to EXCLUDE from removal (preserve these)
    preserve_patterns = [
        r'\(sic\)',  # Luv(sic) Hexalogy
        r'\([Vv]ol\.?\s*\d+\)',  # (Vol. 2), (Vol 1)
        r'\([Vv]olume\s+\d+\)',  # (Volume 1)
        r'\(#\d+\)',  # (#2)
        r'\([Pp]t\.?\s*\d+\)',  # (Pt. 1), (Part 2)
        r'\(&[^)]+\)',  # (& Metro Boomin) - collaborators
        r'\([^)]{3,}(?:Version|Mode)\)',  # (Heroes Version), (GetBackMode) - but NOT just "Version"
        r'\([^)]{10,}\)',  # Long descriptive titles like (Shake the City), (A Netflix Original...)
    ]
    
    # Check if any preserve patterns match - if so, skip normalization for this title
    for preserve in preserve_patterns:
        if re.search(preserve, album_title):
            # Check if it ONLY has preservable content, or if it has edition markers too
            temp = album_title
            for p in preserve_patterns:
                temp = re.sub(p, '', temp)
            
            # If after removing preservable patterns, there are still parentheses with edition markers, process those
            if not re.search(r'\([^)]*(?:deluxe|remaster|edition|explicit|complete|extended|expanded|collector)\s*[^)]*\)', temp, re.IGNORECASE):
                return album_title  # Nothing to normalize
    
    # Edition marker patterns to remove (case insensitive)
    # These are carefully crafted to match edition markers but not meaningful qualifiers
    edition_patterns = [
        # Standalone edition markers in parentheses
        r'\s*\(\s*deluxe\s*\)',
        r'\s*\(\s*deluxe\s+edition\s*\)',
        r'\s*\(\s*deluxe\s+version\s*\)',
        r'\s*\(\s*deluxe\s*-?\s*edition\s*\)',
        r'\s*\(\s*expanded\s*\)',
        r'\s*\(\s*expanded\s+edition\s*\)',
        r'\s*\(\s*remaster\s*\)',
        r'\s*\(\s*remastered\s*\)',
        r'\s*\(\s*remastered\s+edition\s*\)',
        r'\s*\(\s*the\s+remaster\s*\)',
        r'\s*\(\s*\d{4}\s+remaster\s*\)',  # (2015 Remaster)
        r'\s*\(\s*\d+(?:th|st|nd|rd)\s+anniversary[^)]*\)',  # (20th Anniversary...)
        r'\s*\(\s*explicit\s*\)',
        r'\s*\(\s*clean\s*\)',
        r'\s*\(\s*complete\s*\)',
        r'\s*\(\s*complete\s+edition\s*\)',
        r'\s*\(\s*extended\s*\)',
        r'\s*\(\s*extended\s+version\s*\)',
        r'\s*\(\s*special\s+edition\s*\)',
        r'\s*\(\s*collector\'?s\s+edition\s*\)',
        r'\s*\(\s*limited\s+edition\s*\)',
        r'\s*\(\s*bonus\s+track\s+version\s*\)',
        r'\s*\(\s*platinum\s+edition\s*\)',
        r'\s*\(\s*gold\s+edition\s*\)',
        
        # Square brackets with edition markers
        r'\s*\[\s*explicit\s*\]',
        r'\s*\[\s*clean\s*\]',
        r'\s*\[\s*deluxe\s*\]',
        r'\s*\[\s*remastered\s*\]',
    ]
    
    normalized = album_title
    
    for pattern in edition_patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    
    # Clean up any double spaces and trim
    normalized = ' '.join(normalized.split())
    normalized = normalized.strip()
    
    # Don't return empty strings
    if not normalized:
        return album_title
    
    # Remove trailing punctuation that might be left over
    normalized = re.sub(r'\s*[,\-:;]+\s*$', '', normalized).strip()
    
    return normalized if normalized else album_title

def needs_normalization(album_title: str) -> bool:
    """Check if an album title would benefit from normalization."""
    if not album_title:
        return False
    
    normalized = normalize_album_title(album_title)
    return normalized != album_title

def create_backup(csv_file: Path) -> Path:
    """Create a timestamped backup of the original CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{csv_file.stem}_backup_{timestamp}{csv_file.suffix}"
    backup_path = csv_file.parent / backup_name
    
    backup_path.write_text(csv_file.read_text(encoding='utf-8'), encoding='utf-8')
    logging.info(f"Created backup: {backup_path}")
    return backup_path

def process_csv(csv_file: Path, status_filter: Optional[Set[str]] = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Process the CSV file and normalize album titles.
    
    Args:
        csv_file: Path to the CSV file to process
        status_filter: Set of status values to filter by (None = process all)
        dry_run: If True, only show what would be changed without modifying the file
        
    Returns:
        Dictionary with processing statistics
    """
    
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")
    
    # Read the CSV file
    with open(csv_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    if not fieldnames:
        raise ValueError("CSV file appears to be empty or invalid")
    
    # Validate required columns
    required_columns = ['artist', 'album', 'status']
    missing_columns = [col for col in required_columns if col not in fieldnames]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # Add 'original_album' column if it doesn't exist
    if 'original_album' not in fieldnames:
        fieldnames = list(fieldnames)
        # Insert original_album after album column
        album_index = fieldnames.index('album')
        fieldnames.insert(album_index + 1, 'original_album')
    
    # Process rows
    stats = {
        'total_rows': len(rows),
        'processed_rows': 0,
        'changed_rows': 0,
        'skipped_by_status': 0,
        'changes': []
    }
    
    for i, row in enumerate(rows):
        artist = row.get('artist', '')
        album = row.get('album', '')
        status = row.get('status', '')
        
        # Skip rows based on status filter
        if status_filter and status not in status_filter:
            stats['skipped_by_status'] += 1
            continue
        
        stats['processed_rows'] += 1
        
        # Check if normalization is needed
        if needs_normalization(album):
            normalized_album = normalize_album_title(album)
            
            # Store original album title if not already set
            if not row.get('original_album'):
                row['original_album'] = album
            
            if not dry_run:
                row['album'] = normalized_album
            
            change_info = {
                'row': i + 1,
                'artist': artist,
                'original': album,
                'normalized': normalized_album,
                'status': status
            }
            stats['changes'].append(change_info)
            stats['changed_rows'] += 1
            
            logging.info(f"Row {i+1}: '{artist} - {album}' -> '{normalized_album}'")
    
    # Write the modified CSV if not dry run
    if not dry_run and stats['changed_rows'] > 0:
        # Create backup first
        backup_path = create_backup(csv_file)
        
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logging.info(f"Updated CSV file: {csv_file}")
    
    return stats

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
#!/usr/bin/env python3
"""
universal_parser.py - Universal Artist/Album Data Parser & Normalizer

This script intelligently parses artist/album data from multiple input formats and produces
a clean, normalized CSV ready for Lidarr import. Uses rapidfuzz for smart deduplication
and fuzzy matching to handle variations in artist/album names.

SUPPORTED INPUT FORMATS:
1. Spotify CSV Export (with headers: Track Name, Artist Name(s), Album Name, etc.)
2. Simple CSV (artist,album or album,artist with/without headers)
3. Text file with "Artist - Album" lines
4. Text file with "Album by Artist" lines
5. Tab-separated values
6. Any reasonable manual copy-paste format

FEATURES:
- Auto-detects input format (Spotify vs simple CSV vs text)
- Intelligently identifies which column is artist vs album
- Uses rapidfuzz to detect and merge near-duplicate entries
- Normalizes artist names (handles Unicode, apostrophes, whitespace)
- Cleans album titles (removes edition markers, special chars)
- Filters by minimum track counts (for Spotify exports)
- Deduplicates using fuzzy matching (configurable threshold)
- Enriches with MusicBrainz IDs by default for optimal import performance
- Outputs clean albums.csv ready for add_albums_to_lidarr.py

USAGE:
    # Auto-detect format and parse
    python universal_parser.py input.csv -o albums.csv
    
    # Spotify export with filtering
    python universal_parser.py spotify_export.csv --min-artist-songs 3 --min-album-songs 2
    
    # Manual data with aggressive deduplication
    python universal_parser.py manual_list.txt --fuzzy-threshold 90
    
    # Dry run to preview cleaning
    python universal_parser.py input.csv --dry-run
    
    # Skip normalization (keep original titles)
    python universal_parser.py input.csv --no-normalize
    
    # Filter by specific artist
    python universal_parser.py input.csv --artist "Henry Rutty"
    
    # Filter by specific album
    python universal_parser.py input.csv --album "Bedtime"

EXAMPLES:
    Input formats automatically detected:
    
    Spotify CSV:
        Track Name,Artist Name(s),Album Name,Album Artist Name(s),...
        Song1,Artist1,Album1,Artist1,...
    
    Simple CSV (auto-detected):
        artist,album
        Kendrick Lamar,DAMN.
        
        OR
        
        album,artist
        DAMN.,Kendrick Lamar
    
    Text file:
        Kendrick Lamar - DAMN.
        Drake - Views
        
        OR
        
        DAMN. by Kendrick Lamar
        Views by Drake
"""

import csv
import re
import argparse
import logging
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from rapidfuzz import fuzz, process
from tqdm import tqdm

# Add lib directory to Python path for imports
lib_path = Path(__file__).parent.parent / 'lib'
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

from text_utils import (
    normalize_artist_name,
    normalize_album_title_for_matching,
    clean_csv_input,
    strip_album_suffixes
)
from musicbrainz_client import MusicBrainzClient
from config_manager import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

@dataclass
class AlbumEntry:
    """Represents a single artist/album pair with metadata."""
    artist: str
    album: str
    track_count: int = 1
    source_format: str = "unknown"
    matching_risk: bool = False  # Flag for entries that may have MusicBrainz matching issues
    risk_reason: str = ""  # Why this entry is flagged as risky
    mb_artist_id: str = ""  # MusicBrainz artist ID (optional, populated with --enrich-musicbrainz)
    mb_release_id: str = ""  # MusicBrainz release group ID (optional, populated with --enrich-musicbrainz)
    
    def __hash__(self):
        return hash((self.artist.lower(), self.album.lower()))
    
    def __eq__(self, other):
        return (self.artist.lower(), self.album.lower()) == (other.artist.lower(), other.album.lower())


class UniversalParser:
    """
    Universal parser for artist/album data from various formats.
    
    This class provides a clean, modular architecture for parsing and normalizing
    artist/album data from multiple input formats. Key design principles:
    
    - **Separation of Concerns**: Each parsing format has its own method
    - **Reusable Helpers**: Common operations extracted to private methods
    - **Risk Flagging**: Transparent tracking of potentially problematic entries
    - **Configurable**: Fuzzy matching threshold and normalization can be adjusted
    
    Private Helper Methods:
        _is_various_artists(): Check if artist is a compilation
        _flag_risk(): Mark an entry as potentially risky
        _get_risk_info(): Retrieve risk status for an entry
        _clean_artist_album(): Normalize artist/album names
        _create_entry(): Factory method for creating AlbumEntry with risk flags
        _apply_spotify_filters(): Apply Spotify-specific filtering logic
        _detect_csv_column_order_from_header(): Determine CSV column order from headers
        _detect_csv_column_order_from_data(): Auto-detect CSV columns from content
        _process_csv_row(): Process a single CSV row
        _log_simple_csv_results(): Log parsing results for CSV files
        _extract_artist_album_from_line(): Parse text lines into artist/album
        _group_entries_by_artist(): Group entries for fuzzy matching
        _merge_fuzzy_albums_in_group(): Merge similar albums within artist group
        _apply_fuzzy_merge(): Apply merge logic with risk flagging
        _append_risk_reason(): Append to existing risk reasons
    """
    
    def __init__(self, fuzzy_threshold: int = 85, normalize: bool = True):
        """
        Initialize parser with configuration.
        
        Args:
            fuzzy_threshold: Similarity threshold (0-100) for fuzzy deduplication
            normalize: Whether to normalize artist/album names
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.normalize = normalize
        self.entries: List[AlbumEntry] = []
        self.stats = {
            'raw_entries': 0,
            'duplicate_exact': 0,
            'duplicate_fuzzy': 0,
            'spotify_filtered_artists': 0,
            'spotify_filtered_albums': 0,
            'format_detected': 'unknown',
            'mb_enriched': 0,
            'mb_failed': 0
        }
        self._risk_flags: Dict[Tuple[str, str], str] = {}  # Store risk flags during parsing
        self.mb_client: Optional[MusicBrainzClient] = None  # Lazy-initialized when enrichment is enabled
    
    def _is_various_artists(self, artist: str) -> bool:
        """Check if artist name represents a compilation."""
        return artist.lower() in ['various artists', 'various', 'va']
    
    def _flag_risk(self, artist: str, album: str, reason: str) -> None:
        """Flag an artist/album pair as potentially risky for matching."""
        key = (artist, album)
        self._risk_flags[key] = reason
    
    def _get_risk_info(self, artist: str, album: str) -> Tuple[bool, str]:
        """Get risk flag status for an artist/album pair."""
        key = (artist, album)
        has_risk = key in self._risk_flags
        risk_reason = self._risk_flags.get(key, "")
        return has_risk, risk_reason
    
    def _clean_artist_album(self, artist: str, album: str) -> Tuple[str, str]:
        """Clean and normalize artist/album names if normalization is enabled."""
        if self.normalize:
            artist = clean_csv_input(artist, is_artist=True)
            album = clean_csv_input(album, is_artist=False)
        return artist, album
    
    def _create_entry(self, artist: str, album: str, source_format: str, 
                     track_count: int = 1) -> AlbumEntry:
        """Create an AlbumEntry with risk flags applied."""
        matching_risk, risk_reason = self._get_risk_info(artist, album)
        return AlbumEntry(
            artist=artist,
            album=album,
            track_count=track_count,
            source_format=source_format,
            matching_risk=matching_risk,
            risk_reason=risk_reason
        )
    
    def detect_format(self, file_path: str) -> str:
        """
        Auto-detect input file format.
        
        Returns:
            'spotify_csv', 'simple_csv', 'text_dash', 'text_by', 'tsv', or 'unknown'
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read first few lines
            lines = [f.readline().strip() for _ in range(5) if f.readable()]
            f.seek(0)
            first_line = lines[0] if lines else ""
            
            # Check for Spotify CSV (has specific columns)
            if 'Track Name' in first_line or 'Artist Name(s)' in first_line:
                logging.info("📊 Detected format: Spotify CSV Export")
                return 'spotify_csv'
            
            # Check for simple CSV with headers
            if ',' in first_line and ('artist' in first_line.lower() or 'album' in first_line.lower()):
                logging.info("📊 Detected format: Simple CSV (with headers)")
                return 'simple_csv'
            
            # Check for TSV (tab-separated)
            if '\t' in first_line and len(first_line.split('\t')) >= 2:
                logging.info("📊 Detected format: Tab-separated values")
                return 'tsv'
            
            # Check for "Artist - Album" format
            dash_pattern = re.compile(r'^[^-]+ - [^-]+$')
            if any(dash_pattern.match(line) for line in lines[1:3] if line):
                logging.info("📊 Detected format: Text file (Artist - Album)")
                return 'text_dash'
            
            # Check for "Album by Artist" format
            by_pattern = re.compile(r'^.+ by .+$', re.IGNORECASE)
            if any(by_pattern.match(line) for line in lines[1:3] if line):
                logging.info("📊 Detected format: Text file (Album by Artist)")
                return 'text_by'
            
            # Check for headerless CSV
            if ',' in first_line and len(first_line.split(',')) >= 2:
                logging.info("📊 Detected format: Simple CSV (no headers)")
                return 'simple_csv'
            
            logging.warning("⚠️  Could not auto-detect format, will try best-effort parsing")
            return 'unknown'
    
    def parse_spotify_csv(self, file_path: str, min_artist_songs: int = 3, 
                         min_album_songs: int = 2) -> None:
        """Parse Spotify CSV export with filtering."""
        artist_albums = defaultdict(lambda: defaultdict(int))
        artist_totals = defaultdict(int)
        various_artists_count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                self.stats['raw_entries'] += 1
                
                # Extract artist and album with fallbacks
                artist = row.get('Album Artist Name(s)', row.get('Artist Name(s)', '')).strip()
                album = row.get('Album Name', '').strip()
                
                if not artist or not album:
                    continue
                
                # Handle multiple artists
                if ',' in artist:
                    artist = artist.split(',')[0].strip()
                
                # Clean inputs
                artist, album = self._clean_artist_album(artist, album)
                
                artist_albums[artist][album] += 1
                artist_totals[artist] += 1
        
        # Apply Spotify-specific filters and create entries
        self._apply_spotify_filters(artist_albums, artist_totals, 
                                    min_artist_songs, min_album_songs)
    
    def _apply_spotify_filters(self, artist_albums, artist_totals,
                              min_artist_songs: int, min_album_songs: int) -> None:
        """Apply filtering criteria and create entries from Spotify data."""
        filtered_count = 0
        various_artists_count = 0
        
        for artist, albums in artist_albums.items():
            if artist_totals[artist] < min_artist_songs:
                self.stats['spotify_filtered_artists'] += 1
                continue
            
            for album, count in albums.items():
                if count < min_album_songs:
                    self.stats['spotify_filtered_albums'] += 1
                    continue
                
                entry = self._create_entry(artist, album, 'spotify_csv', track_count=count)
                
                if entry.matching_risk and "Various Artists" in entry.risk_reason:
                    various_artists_count += 1
                
                self.entries.append(entry)
                filtered_count += 1
        
        logging.info(f"✅ Parsed {filtered_count} artist/album pairs from Spotify export")
        if various_artists_count > 0:
            logging.info(f"   ⚠️  {various_artists_count} 'Various Artists' entries flagged (may have matching issues)")
        logging.info(f"   Filtered out: {self.stats['spotify_filtered_artists']} artists, "
                    f"{self.stats['spotify_filtered_albums']} albums")
    
    def parse_simple_csv(self, file_path: str) -> None:
        """Parse simple CSV (artist,album or album,artist)."""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # Try to detect if first line is header
            first_line = f.readline().strip()
            has_header = 'artist' in first_line.lower() or 'album' in first_line.lower()
            
            if not has_header:
                f.seek(0)  # Reset to beginning
            
            reader = csv.reader(f)
            
            if has_header:
                artist_col, album_col = self._detect_csv_column_order_from_header(next(reader))
            else:
                artist_col, album_col = self._detect_csv_column_order_from_data(reader)
            
            # Process remaining rows
            for row in reader:
                if len(row) < 2:
                    continue
                    
                self.stats['raw_entries'] += 1
                artist = row[artist_col].strip()
                album = row[album_col].strip()
                
                if not artist or not album:
                    continue
                
                artist, album = self._clean_artist_album(artist, album)
                
                self.entries.append(self._create_entry(artist, album, 'simple_csv'))
        
        # Log results
        self._log_simple_csv_results()
    
    def _detect_csv_column_order_from_header(self, header: List[str]) -> Tuple[int, int]:
        """Determine artist/album column order from CSV header."""
        header = [h.strip().lower() for h in header]
        
        if 'artist' in header[0]:
            return 0, 1  # artist_col, album_col
        elif 'artist' in header[1]:
            return 1, 0
        else:
            # Default to artist first if unclear
            logging.debug(f"Header unclear, defaulting to artist,album order")
            return 0, 1
    
    def _detect_csv_column_order_from_data(self, reader) -> Tuple[int, int]:
        """Auto-detect artist/album column order using heuristics."""
        first_row = next(reader, None)
        if not first_row or len(first_row) < 2:
            logging.error("❌ CSV file has fewer than 2 columns")
            return 0, 1  # Default
        
        # Heuristic: artist names are usually shorter and have fewer special chars
        col1_len = len(first_row[0])
        col2_len = len(first_row[1])
        col1_special = sum(c in first_row[0] for c in '()[]')
        col2_special = sum(c in first_row[1] for c in '()[]')
        
        if col1_len < col2_len or col1_special < col2_special:
            artist_col, album_col = 0, 1
        else:
            artist_col, album_col = 1, 0
        
        # Process the first row we already read
        self._process_csv_row(first_row, artist_col, album_col, 'simple_csv')
        
        return artist_col, album_col
    
    def _process_csv_row(self, row: List[str], artist_col: int, album_col: int, 
                        source_format: str) -> None:
        """Process a single CSV row and create entry."""
        if len(row) < 2:
            return
        
        artist = row[artist_col].strip()
        album = row[album_col].strip()
        
        if not artist or not album:
            return
        
        artist, album = self._clean_artist_album(artist, album)
        
        if self._is_various_artists(artist):
            self._flag_risk(artist, album, "Various Artists compilation")
        
        self.entries.append(self._create_entry(artist, album, source_format))
        self.stats['raw_entries'] += 1
    
    def _log_simple_csv_results(self) -> None:
        """Log parsing results for simple CSV files."""
        logging.info(f"✅ Parsed {len(self.entries)} entries from CSV")
    
    def parse_text_format(self, file_path: str, format_type: str) -> None:
        """Parse text file with various formats."""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                self.stats['raw_entries'] += 1
                artist, album = self._extract_artist_album_from_line(line, format_type)
                
                if artist and album:
                    artist, album = self._clean_artist_album(artist, album)
                    
                    self.entries.append(self._create_entry(artist, album, format_type))
        
        logging.info(f"✅ Parsed {len(self.entries)} entries from text file")
    
    def _extract_artist_album_from_line(self, line: str, format_type: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract artist and album from a line of text based on format type."""
        artist, album = None, None
        
        if format_type == 'text_dash':
            # "Artist - Album" format
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                artist, album = parts[0].strip(), parts[1].strip()
        
        elif format_type == 'text_by':
            # "Album by Artist" format
            match = re.match(r'^(.+?)\s+by\s+(.+)$', line, re.IGNORECASE)
            if match:
                album, artist = match.groups()
                artist, album = artist.strip(), album.strip()
        
        elif format_type == 'tsv':
            # Tab-separated
            parts = line.split('\t')
            if len(parts) >= 2:
                # Try to detect which is artist vs album
                if len(parts[0]) < len(parts[1]):
                    artist, album = parts[0].strip(), parts[1].strip()
                else:
                    album, artist = parts[0].strip(), parts[1].strip()
        
        return artist, album
    
    def deduplicate_exact(self) -> None:
        """Remove exact duplicates (case-insensitive)."""
        seen = {}
        unique = []
        
        for entry in self.entries:
            key = (entry.artist.lower(), entry.album.lower())
            if key in seen:
                # Merge track counts
                seen[key].track_count += entry.track_count
                self.stats['duplicate_exact'] += 1
            else:
                seen[key] = entry
                unique.append(entry)
        
        self.entries = unique
        logging.info(f"🔍 Removed {self.stats['duplicate_exact']} exact duplicates")
    
    def deduplicate_fuzzy(self) -> None:
        """Remove fuzzy duplicates using rapidfuzz."""
        if self.fuzzy_threshold >= 100:
            return  # Skip if threshold is 100 (exact matches only)
        
        # Group by normalized artist name first (for efficiency)
        by_artist = self._group_entries_by_artist()
        
        unique = []
        merged_count = 0
        
        for artist_group in by_artist.values():
            merged_count += self._merge_fuzzy_albums_in_group(artist_group, unique)
        
        self.entries = unique
        self.stats['duplicate_fuzzy'] = merged_count
        
        if merged_count > 0:
            logging.info(f"🔍 Merged {merged_count} fuzzy duplicates "
                        f"(threshold: {self.fuzzy_threshold}%)")
    
    def _group_entries_by_artist(self) -> Dict[str, List[AlbumEntry]]:
        """Group entries by normalized artist name."""
        by_artist = defaultdict(list)
        for entry in self.entries:
            normalized = normalize_artist_name(entry.artist)
            by_artist[normalized].append(entry)
        return by_artist
    
    def _merge_fuzzy_albums_in_group(self, artist_group: List[AlbumEntry], 
                                     unique: List[AlbumEntry]) -> int:
        """Merge fuzzy album matches within a single artist group."""
        processed = set()
        merged_count = 0
        
        for i, entry in enumerate(artist_group):
            if i in processed:
                continue
            
            # Check if this album fuzzy-matches any later albums
            album_normalized = normalize_album_title_for_matching(entry.album)
            
            for j in range(i + 1, len(artist_group)):
                if j in processed:
                    continue
                
                other_album = normalize_album_title_for_matching(artist_group[j].album)
                similarity = fuzz.ratio(album_normalized, other_album)
                
                if similarity >= self.fuzzy_threshold:
                    self._apply_fuzzy_merge(entry, artist_group[j], similarity)
                    processed.add(j)
                    merged_count += 1
                    
                    logging.debug(f"   Merged: '{entry.album}' ≈ '{artist_group[j].album}' "
                                f"(similarity: {similarity}%)")
            
            unique.append(entry)
        
        return merged_count
    
    def _apply_fuzzy_merge(self, target_entry: AlbumEntry, 
                          merged_entry: AlbumEntry, similarity: float) -> None:
        """Apply fuzzy merge logic and flag risks appropriately."""
        # Flag as risky if similarity is low (close to threshold)
        if similarity < self.fuzzy_threshold + 10:  # Within 10 points of threshold
            target_entry.matching_risk = True
            risk_msg = f"Low fuzzy match ({similarity:.1f}%)"
            target_entry.risk_reason = self._append_risk_reason(target_entry.risk_reason, risk_msg)
        else:
            # Still flag that it was merged, but not as risky
            target_entry.matching_risk = True
            risk_msg = f"Merged duplicate ({similarity:.1f}%)"
            target_entry.risk_reason = self._append_risk_reason(target_entry.risk_reason, risk_msg)
        
        # Merge - keep the shorter/cleaner title
        if len(target_entry.album) <= len(merged_entry.album):
            target_entry.track_count += merged_entry.track_count
        else:
            # Swap to keep the cleaner entry
            target_entry.album = merged_entry.album
            target_entry.track_count += merged_entry.track_count
    
    def _append_risk_reason(self, existing_reason: str, new_reason: str) -> str:
        """Append a new reason to existing risk reasons."""
        if existing_reason:
            return f"{existing_reason}; {new_reason}"
        return new_reason
    
    def enrich_with_musicbrainz(self, mb_delay: float = 2.0, output_path: Optional[str] = None) -> None:
        """
        Enrich parsed entries with MusicBrainz IDs for artists and albums.
        
        This method looks up each artist/album pair on MusicBrainz and stores
        the MusicBrainz IDs in the entry. This allows the import script to skip
        redundant lookups and process much faster.
        
        Args:
            mb_delay: Delay between MusicBrainz requests (min: 1.0 sec per MB TOS)
        """
        if not self.entries:
            logging.warning("⚠️  No entries to enrich")
            return
        
        # Initialize MusicBrainz client if needed
        if self.mb_client is None:
            try:
                # Try to load config for MB settings
                config = Config()
                self.mb_client = MusicBrainzClient(
                    delay=max(mb_delay, 1.0),
                    user_agent={
                        'app_name': 'lidarr-album-import-universal-parser',
                        'version': '2.1',
                        'contact': getattr(config, 'musicbrainz_contact', 'your.email@example.com')
                    }
                )
            except Exception as e:
                logging.warning(f"⚠️  Could not load config: {e}")
                # Fallback to default client
                self.mb_client = MusicBrainzClient(
                    delay=max(mb_delay, 1.0),
                    user_agent={
                        'app_name': 'lidarr-album-import-universal-parser',
                        'version': '2.1',
                        'contact': 'your.email@example.com'
                    }
                )
        
        logging.info(f"🔍 Enriching {len(self.entries)} entries with MusicBrainz metadata...")
        logging.info(f"   Rate limit: {mb_delay:.1f}s between requests (this may take a while)")
        if output_path:
            logging.info(f"   📝 Will update CSV after each item: {output_path}")
        
        # Use tqdm for progress bar with file=sys.stderr to avoid conflicts with logging
        import sys
        progress_bar = tqdm(
            self.entries, 
            desc="MusicBrainz lookup", 
            unit="album",
            file=sys.stderr,
            disable=logging.getLogger().level == logging.DEBUG  # Disable if verbose mode
        )
        
        for entry in progress_bar:
            # Update progress bar with current album
            progress_bar.set_postfix_str(f"{entry.artist[:30]}...", refresh=False)
            
            try:
                # Step 1: Lookup artist to get MusicBrainz artist ID
                mb_artist = self.mb_client.search_artists(entry.artist, limit=1)
                artist_list = mb_artist.get('artist-list', [])
                
                if artist_list and len(artist_list) > 0:
                    best_artist = artist_list[0]
                    entry.mb_artist_id = best_artist.get('id', '')
                    logging.info(f"✅ Artist '{entry.artist}' → '{best_artist.get('name')}' (ID: {entry.mb_artist_id})")
                else:
                    logging.info(f"❌ Artist '{entry.artist}' → No match found")
                
                # Step 2: Lookup release group (album) to get MusicBrainz release ID
                mb_release = self.mb_client.search_release_groups(
                    entry.artist,
                    entry.album,
                    limit=5
                )
                release_list = mb_release.get('release-group-list', [])
                
                if release_list and len(release_list) > 0:
                    # Pick the best match (highest score)
                    best_release = release_list[0]
                    entry.mb_release_id = best_release.get('id', '')
                    
                    logging.info(f"✅ Album '{entry.album}' → '{best_release.get('title', '')}' (ID: {entry.mb_release_id}, Score: {best_release.get('ext:score', 'N/A')})")
                    
                    # Check if match quality is questionable
                    score = int(best_release.get('ext:score', '100'))
                    if score < 85:
                        # Flag low-confidence matches
                        if not entry.matching_risk:
                            entry.matching_risk = True
                            entry.risk_reason = f"Low MB match score: {score}"
                        else:
                            entry.risk_reason = self._append_risk_reason(
                                entry.risk_reason,
                                f"Low MB match score: {score}"
                            )
                    
                    self.stats['mb_enriched'] += 1
                else:
                    # Album not found, but we may still have artist ID
                    logging.info(f"❌ Album '{entry.album}' → No match found")
                    if entry.mb_artist_id:
                        self.stats['mb_enriched'] += 1  # Count as enriched if we have artist ID
                    else:
                        self.stats['mb_failed'] += 1
                    
            except Exception as e:
                logging.error(f"❌ Error processing '{entry.artist}' - '{entry.album}': {e}")
                self.stats['mb_failed'] += 1
            
            # Write updated CSV after each item if output_path is provided
            if output_path:
                try:
                    self.write_output(output_path, include_risk_column=False, skip_risky=False)
                except Exception as e:
                    logging.warning(f"⚠️  Failed to update CSV after processing '{entry.artist}' - '{entry.album}': {e}")
        
        # Summary
        enriched = self.stats['mb_enriched']
        failed = self.stats['mb_failed']
        total = len(self.entries)
        
        logging.info(f"✅ MusicBrainz enrichment complete:")
        logging.info(f"   📍 {enriched}/{total} albums matched ({enriched/total*100:.1f}%)")
        if failed > 0:
            logging.info(f"   ❌ {failed} lookups failed")
    
    def parse_file(self, file_path: str, **kwargs) -> None:
        """Main entry point - detect format and parse accordingly."""
        format_type = self.detect_format(file_path)
        self.stats['format_detected'] = format_type
        
        if format_type == 'spotify_csv':
            self.parse_spotify_csv(
                file_path,
                min_artist_songs=kwargs.get('min_artist_songs', 3),
                min_album_songs=kwargs.get('min_album_songs', 2)
            )
        elif format_type == 'simple_csv':
            self.parse_simple_csv(file_path)
        elif format_type in ['text_dash', 'text_by', 'tsv']:
            self.parse_text_format(file_path, format_type)
        else:
            # Try multiple parsing strategies
            logging.info("🔄 Trying best-effort parsing...")
            try:
                self.parse_simple_csv(file_path)
            except Exception as e:
                logging.error(f"❌ Failed to parse file: {e}")
                return
        
        # Post-processing
        if not self.entries:
            logging.error("❌ No valid entries found in input file")
            return
        
        self.deduplicate_exact()
        self.deduplicate_fuzzy()
        
        logging.info(f"✨ Final result: {len(self.entries)} unique artist/album pairs")
    
    def write_output(self, output_path: str, include_risk_column: bool = False, 
                    skip_risky: bool = False) -> None:
        """
        Write cleaned data to CSV file.
        
        Args:
            output_path: Path to output CSV file
            include_risk_column: If True, add columns for matching_risk and risk_reason
            skip_risky: If True, exclude entries flagged as risky
        """
        # Filter entries if requested
        entries_to_write = self.entries
        if skip_risky:
            entries_to_write = [e for e in self.entries if not e.matching_risk]
            skipped = len(self.entries) - len(entries_to_write)
            if skipped > 0:
                logging.info(f"   Skipped {skipped} risky entries")
        
        # Sort by artist, then album
        entries_to_write.sort(key=lambda e: (e.artist.lower(), e.album.lower()))
        
        # Determine if we have MB IDs to write
        has_mb_ids = any(e.mb_artist_id or e.mb_release_id for e in entries_to_write)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            header = ['artist', 'album']
            if has_mb_ids:
                header.extend(['mb_artist_id', 'mb_release_id'])
            if include_risk_column:
                header.extend(['matching_risk', 'risk_reason'])
            writer.writerow(header)
            
            # Write data
            for entry in entries_to_write:
                row = [entry.artist, entry.album]
                if has_mb_ids:
                    row.extend([entry.mb_artist_id, entry.mb_release_id])
                if include_risk_column:
                    row.extend([
                        'TRUE' if entry.matching_risk else 'FALSE',
                        entry.risk_reason
                    ])
                writer.writerow(row)
        
        logging.info(f"💾 Wrote {len(entries_to_write)} entries to {output_path}")
        if has_mb_ids:
            enriched_count = sum(1 for e in entries_to_write if e.mb_release_id)
            logging.info(f"   📍 {enriched_count} entries have MusicBrainz IDs")
    
    def print_statistics(self) -> None:
        """Print detailed parsing statistics."""
        risky_count = sum(1 for e in self.entries if e.matching_risk)
        enriched_count = sum(1 for e in self.entries if e.mb_release_id)
        
        print("\n" + "="*70)
        print("📊 PARSING STATISTICS")
        print("="*70)
        print(f"Format detected:       {self.stats['format_detected']}")
        print(f"Raw entries parsed:    {self.stats['raw_entries']}")
        print(f"Exact duplicates:      {self.stats['duplicate_exact']}")
        print(f"Fuzzy duplicates:      {self.stats['duplicate_fuzzy']}")
        
        if self.stats['format_detected'] == 'spotify_csv':
            print(f"Filtered artists:      {self.stats['spotify_filtered_artists']}")
            print(f"Filtered albums:       {self.stats['spotify_filtered_albums']}")
        
        if self.stats['mb_enriched'] > 0 or self.stats['mb_failed'] > 0:
            print(f"\nMusicBrainz Enrichment:")
            print(f"  Successfully enriched: {self.stats['mb_enriched']}")
            print(f"  Failed lookups:        {self.stats['mb_failed']}")
        
        print(f"\n✨ Final unique pairs:  {len(self.entries)}")
        if enriched_count > 0:
            print(f"📍 With MusicBrainz IDs: {enriched_count}")
        if risky_count > 0:
            print(f"⚠️  Risky entries:       {risky_count} (may have matching issues)")
        print("="*70)
        
        # Show sample entries
        if self.entries:
            print("\n📝 Sample entries (first 5):")
            for entry in self.entries[:5]:
                risk_indicator = " ⚠️" if entry.matching_risk else ""
                mb_indicator = " 📍" if entry.mb_release_id else ""
                print(f"   • {entry.artist} - {entry.album}{risk_indicator}{mb_indicator}")
            
            if len(self.entries) > 5:
                print(f"   ... and {len(self.entries) - 5} more")
        
        # Show risky entries if any
        if risky_count > 0 and risky_count <= 10:
            print(f"\n⚠️  Risky entries (may have MusicBrainz matching issues):")
            for entry in [e for e in self.entries if e.matching_risk]:
                print(f"   • {entry.artist} - {entry.album}")
                print(f"     Reason: {entry.risk_reason}")
        elif risky_count > 10:
            print(f"\n⚠️  {risky_count} risky entries found. Use --include-risk-info to see details in output CSV.")
        
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Universal parser for artist/album data with intelligent normalization",
        epilog="""
EXAMPLES:
  # Parse and enrich with MusicBrainz IDs (default behavior)
  python universal_parser.py spotify_export.csv
  
  # Parse manual list with aggressive deduplication  
  python universal_parser.py my_list.txt --fuzzy-threshold 90
  
  # Parse without normalization (keep original formatting)
  python universal_parser.py input.csv --no-normalize
  
  # Dry run to preview results
  python universal_parser.py input.csv --dry-run
  
  # Custom output file
  python universal_parser.py input.csv -o cleaned_albums.csv
  
  # Include risk info columns for review
  python universal_parser.py input.csv --include-risk-info
  
  # Exclude risky entries (Various Artists, low fuzzy matches)
  python universal_parser.py input.csv --skip-risky
  
  # Skip MusicBrainz enrichment (faster, but requires manual MB ID resolution)
  python universal_parser.py input.csv --no-enrich-musicbrainz
  
  # Filter by specific artist (case-insensitive partial match)
  python universal_parser.py input.csv --artist "Henry Rutty"
  
  # Filter by specific album (case-insensitive partial match)
  python universal_parser.py input.csv --album "Bedtime"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("input", help="Input file (CSV, TSV, or text)")
    parser.add_argument("-o", "--output", default="albums.csv",
                       help="Output CSV file (default: albums.csv)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Parse and show stats without writing output")
    parser.add_argument("--fuzzy-threshold", type=int, default=85,
                       help="Fuzzy matching threshold 0-100 (default: 85, use 100 to disable)")
    parser.add_argument("--no-normalize", action="store_true",
                       help="Skip normalization (keep original formatting)")
    parser.add_argument("--min-artist-songs", type=int, default=3,
                       help="For Spotify: minimum songs per artist (default: 3)")
    parser.add_argument("--min-album-songs", type=int, default=2,
                       help="For Spotify: minimum songs per album (default: 2)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose debug logging")
    parser.add_argument("--include-risk-info", action="store_true",
                       help="Include matching_risk and risk_reason columns in output CSV")
    parser.add_argument("--skip-risky", action="store_true",
                       help="Exclude entries flagged as risky from output")
    parser.add_argument('--no-enrich-musicbrainz', action='store_true',
                        help='Skip MusicBrainz enrichment (faster, but requires manual MB ID resolution in import script)')
    parser.add_argument("--mb-delay", type=float, default=2.0,
                       help="Delay between MusicBrainz requests in seconds (default: 2.0, min: 1.0)")
    parser.add_argument("--artist", type=str,
                       help="Process only albums by specific artist (case-insensitive partial match)")
    parser.add_argument("--album", type=str,
                       help="Process only albums matching specific title (case-insensitive partial match)")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize parser
    universal_parser = UniversalParser(
        fuzzy_threshold=args.fuzzy_threshold,
        normalize=not args.no_normalize
    )
    
    # Parse input file
    logging.info(f"🚀 Starting universal parser...")
    logging.info(f"📂 Input: {args.input}")
    
    try:
        universal_parser.parse_file(
            args.input,
            min_artist_songs=args.min_artist_songs,
            min_album_songs=args.min_album_songs
        )
    except FileNotFoundError:
        logging.error(f"❌ File not found: {args.input}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Apply artist filter if specified
    if args.artist:
        artist_filter = args.artist.lower()
        entries_before = len(universal_parser.entries)
        universal_parser.entries = [entry for entry in universal_parser.entries if artist_filter in entry.artist.lower()]
        filtered_count = entries_before - len(universal_parser.entries)
        if filtered_count > 0:
            logging.info(f"Artist filter '{args.artist}': {len(universal_parser.entries)} items match, {filtered_count} filtered out")
        if not universal_parser.entries:
            logging.info(f"No items found matching artist filter: {args.artist}")
            sys.exit(0)
    
    # Apply album filter if specified
    if args.album:
        album_filter = args.album.lower()
        entries_before = len(universal_parser.entries)
        universal_parser.entries = [entry for entry in universal_parser.entries if album_filter in entry.album.lower()]
        filtered_count = entries_before - len(universal_parser.entries)
        if filtered_count > 0:
            logging.info(f"Album filter '{args.album}': {len(universal_parser.entries)} items match, {filtered_count} filtered out")
        if not universal_parser.entries:
            logging.info(f"No items found matching album filter: {args.album}")
            sys.exit(0)
    
    # Enrich with MusicBrainz if not explicitly disabled
    if not args.no_enrich_musicbrainz:
        try:
            output_path = args.output if not args.dry_run else None
            universal_parser.enrich_with_musicbrainz(mb_delay=args.mb_delay, output_path=output_path)
        except Exception as e:
            logging.error(f"❌ Error during MusicBrainz enrichment: {e}")
            logging.warning("⚠️  Continuing without enrichment...")
            import traceback
            traceback.print_exc()
    
    # Show statistics
    universal_parser.print_statistics()
    
    # Write output
    if not args.dry_run:
        universal_parser.write_output(
            args.output, 
            include_risk_column=args.include_risk_info,
            skip_risky=args.skip_risky
        )
        logging.info(f"✅ Done! Output ready for: add_albums_to_lidarr.py {args.output}")
    else:
        logging.info("🔍 Dry run complete - no output file written")


if __name__ == "__main__":
    main()

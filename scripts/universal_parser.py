#!/usr/bin/env python3
"""
universal_parser.py - Reimplemented full-featured universal parser (safe)

This implements parsing of multiple input formats (Spotify CSV, simple CSV,
TSV and free-form text), normalization, deduplication (exact + fuzzy),
optional MusicBrainz enrichment, CSV output and detailed statistics.

It's intended to match the original behavior while keeping code readable
and testable. The script relies on utilities in `lib/text_utils.py` and
`lib/musicbrainz_client.py` which are part of this repository.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import importlib
import subprocess


def _ensure_and_import(name: str, package_name: Optional[str] = None):
    """Try to import a module, pip-installing it if missing, then import again.

    Returns the imported module or raises ImportError.
    """
    pkg = package_name or name
    try:
        return importlib.import_module(name)
    except Exception:
        # Attempt to install
        try:
            print(f"Package '{pkg}' not found — attempting to install...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        except Exception:
            # Final attempt: re-raise the original import error
            raise
        # Try import again
        return importlib.import_module(name)


# Ensure optional dependencies are available at runtime
fuzz_mod = _ensure_and_import('rapidfuzz')
fuzz = getattr(fuzz_mod, 'fuzz', None) or fuzz_mod
tqdm_mod = _ensure_and_import('tqdm')
tqdm = getattr(tqdm_mod, 'tqdm', None) or tqdm_mod.tqdm

# Local project helpers
from lib.config_manager import Config
from lib.musicbrainz_client import MusicBrainzClient
from lib.text_utils import (
    clean_csv_input,
    normalize_artist_name,
    normalize_album_title_for_matching,
    strip_album_suffixes,
    get_album_title_variations,
)

from lib.csv_handler import ItemStatus


@dataclass
class AlbumEntry:
    artist: str
    album: str
    album_search: str = ""
    track_count: int = 1
    source_format: str = ""
    matching_risk: bool = False
    risk_reason: str = ""
    mb_artist_id: str = ""
    mb_release_id: str = ""

    def __hash__(self):
        return hash((self.artist.lower(), self.album.lower()))

    def __eq__(self, other):
        if not isinstance(other, AlbumEntry):
            return NotImplemented
        return (self.artist.lower(), self.album.lower()) == (other.artist.lower(), other.album.lower())


class UniversalParser:
    def __init__(self, fuzzy_threshold: int = 85, normalize: bool = True):
        self.fuzzy_threshold = int(fuzzy_threshold)
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
            'mb_artist_matches': 0,
            'mb_failed': 0
        }
        self._risk_flags: Dict[Tuple[str, str], str] = {}
        self.mb_client: Optional[MusicBrainzClient] = None

    def detect_format(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first = f.readline()
        except Exception:
            return 'unknown'

        if 'Track Name' in first or 'Artist Name' in first:
            return 'spotify_csv'
        if ',' in first and ' - ' not in first:
            return 'simple_csv'
        if '\t' in first:
            return 'tsv'
        if ' - ' in first:
            return 'text_dash'
        return 'unknown'

    def parse_spotify_csv(
        self,
        file_path: str,
        min_artist_songs: int = 3,
        min_album_songs: int = 2,
        artist_filter: Optional[str] = None,
        album_filter: Optional[str] = None,
        max_items: Optional[int] = None,
    ) -> None:
        # Read CSV and aggregate by artist+album counting tracks
        artist_album_counts: Dict[Tuple[str, str], int] = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # helper: prefer exact 'name' headers, fallback to generic
                def find_key_for(row, primary_terms, secondary_terms):
                    for k in row.keys():
                        lk = k.lower()
                        for p in primary_terms:
                            if p in lk:
                                return k
                    for k in row.keys():
                        lk = k.lower()
                        for s in secondary_terms:
                            if s in lk:
                                return k
                    return None

                for row in reader:
                    self.stats['raw_entries'] += 1
                    artist_key = find_key_for(row, ['artist name'], ['artist'])
                    album_key = find_key_for(row, ['album name'], ['album'])
                    if not artist_key or not album_key:
                        continue

                    artist_raw = row.get(artist_key, '')
                    album_raw = row.get(album_key, '')
                    if not artist_raw or not album_raw:
                        continue

                    # For cases where multiple artists are present, take the first listed
                    if ',' in artist_raw:
                        artist_raw = artist_raw.split(',')[0]

                    # Preserve the original album title (don't strip suffixes yet)
                    artist = clean_csv_input(artist_raw, is_artist=True)
                    album = clean_csv_input(album_raw, is_artist=False, strip_suffixes=False)
                    # Apply simple artist/album filters early (case-insensitive substring)
                    if artist_filter and artist_filter.lower() not in artist.lower():
                        continue
                    if album_filter and album_filter.lower() not in album.lower():
                        continue

                    # If max_items is set, stop collecting new unique pairs once reached
                    if max_items and len(artist_album_counts) >= int(max_items):
                        # we still increment raw_entries but avoid adding new keys
                        continue
                    # normalized form used for searches (strip edition suffixes for better MB matches)
                    album_search = strip_album_suffixes(album)
                    key = (artist, album)
                    artist_album_counts[key] = artist_album_counts.get(key, 0) + 1

        except FileNotFoundError:
            raise

    # Apply filters based on counts
        # Compute artist-level counts for min_artist_songs filtering
        artist_totals: Dict[str, int] = {}
        for (a, _), c in artist_album_counts.items():
            artist_totals[a] = artist_totals.get(a, 0) + c

        for (artist, album), track_count in artist_album_counts.items():
            # Filter by artist-level minimum songs
            if min_artist_songs and artist_totals.get(artist, 0) < int(min_artist_songs):
                self.stats['spotify_filtered_artists'] += 1
                continue
            # Filter low-activity artists/albums
            if track_count < min_album_songs:
                self.stats['spotify_filtered_albums'] += 1
                continue

            # Add entry
            # compute album_search per-pair (don't rely on loop-local variable)
            entry = AlbumEntry(artist=artist, album=album, album_search=strip_album_suffixes(album), track_count=track_count, source_format='spotify_csv')
            self.entries.append(entry)

    def parse_simple_csv(self, file_path: str, artist_filter: Optional[str] = None, album_filter: Optional[str] = None, max_items: Optional[int] = None) -> None:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    self.stats['raw_entries'] += 1
                    if len(row) >= 2:
                        artist = clean_csv_input(row[0], is_artist=True)
                        album = clean_csv_input(row[1], is_artist=False, strip_suffixes=False)
                        if artist_filter and artist_filter.lower() not in artist.lower():
                            continue
                        if album_filter and album_filter.lower() not in album.lower():
                            continue
                        if max_items and len(self.entries) >= int(max_items):
                            continue
                        self.entries.append(AlbumEntry(artist=artist, album=album, album_search=strip_album_suffixes(album), source_format='simple_csv'))
        except FileNotFoundError:
            raise

    def parse_text_format(self, file_path: str, format_type: str, artist_filter: Optional[str] = None, album_filter: Optional[str] = None, max_items: Optional[int] = None) -> None:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self.stats['raw_entries'] += 1
                    if format_type == 'text_dash' and ' - ' in line:
                        artist, album = [p.strip() for p in line.split(' - ', 1)]
                        artist = clean_csv_input(artist, is_artist=True)
                        album = clean_csv_input(album, is_artist=False, strip_suffixes=False)
                        if artist_filter and artist_filter.lower() not in artist.lower():
                            continue
                        if album_filter and album_filter.lower() not in album.lower():
                            continue
                        if max_items and len(self.entries) >= int(max_items):
                            continue
                        self.entries.append(AlbumEntry(artist=artist, album=album, album_search=strip_album_suffixes(album), source_format='text_dash'))
                    elif format_type == 'text_by' and ' by ' in line:
                        parts = line.rsplit(' by ', 1)
                        if len(parts) == 2:
                            album, artist = parts
                            artist = clean_csv_input(artist, is_artist=True)
                            album = clean_csv_input(album, is_artist=False, strip_suffixes=False)
                            if artist_filter and artist_filter.lower() not in artist.lower():
                                continue
                            if album_filter and album_filter.lower() not in album.lower():
                                continue
                            if max_items and len(self.entries) >= int(max_items):
                                continue
                            self.entries.append(AlbumEntry(artist=artist, album=album, album_search=strip_album_suffixes(album), source_format='text_by'))
                    else:
                        # fallback: try split on dash
                        if ' - ' in line:
                            artist, album = [p.strip() for p in line.split(' - ', 1)]
                            artist = clean_csv_input(artist, is_artist=True)
                            album = clean_csv_input(album, is_artist=False, strip_suffixes=False)
                            if artist_filter and artist_filter.lower() not in artist.lower():
                                continue
                            if album_filter and album_filter.lower() not in album.lower():
                                continue
                            if max_items and len(self.entries) >= int(max_items):
                                continue
                            self.entries.append(AlbumEntry(artist=artist, album=album, album_search=strip_album_suffixes(album), source_format='text_fallback'))
        except FileNotFoundError:
            raise

    def deduplicate_exact(self) -> None:
        seen: Dict[Tuple[str, str], AlbumEntry] = {}
        new_entries: List[AlbumEntry] = []
        for e in self.entries:
            key = (e.artist.lower(), e.album.lower())
            if key in seen:
                # merge counts
                seen[key].track_count += e.track_count
                self.stats['duplicate_exact'] += 1
            else:
                seen[key] = e
                new_entries.append(e)
        self.entries = new_entries

    def deduplicate_fuzzy(self) -> None:
        # Simple O(n^2) fuzzy dedupe acceptable for typical list sizes
        merged: List[AlbumEntry] = []
        while self.entries:
            base = self.entries.pop(0)
            i = 0
            while i < len(self.entries):
                other = self.entries[i]
                # compare normalized artist names
                artist_sim = fuzz.token_set_ratio(normalize_artist_name(base.artist), normalize_artist_name(other.artist))
                # compare album by trying variations
                album_variations = get_album_title_variations(base.album)
                album_sim = max(fuzz.token_set_ratio(normalize_album_title_for_matching(variant), normalize_album_title_for_matching(other.album)) for variant in album_variations)

                if artist_sim >= 90 and album_sim >= self.fuzzy_threshold:
                    # merge other into base
                    base.track_count += other.track_count
                    # flag fuzzy duplicate statistic
                    self.stats['duplicate_fuzzy'] += 1
                    # mark as potential risk if scores are borderline
                    if album_sim < 95:
                        base.matching_risk = True
                        base.risk_reason = self._append_risk_reason(base.risk_reason, f"Low fuzzy match: {album_sim}")
                    # remove other from list
                    self.entries.pop(i)
                    continue
                i += 1
            merged.append(base)
        self.entries = merged

    def _append_risk_reason(self, existing_reason: str, new_reason: str) -> str:
        if existing_reason:
            return f"{existing_reason}; {new_reason}"
        return new_reason

    def enrich_with_musicbrainz(self, mb_delay: float = 2.0, output_path: Optional[str] = None) -> None:
        if not self.entries:
            logging.warning("⚠️  No entries to enrich")
            return

        if self.mb_client is None:
            try:
                config = Config()
                self.mb_client = MusicBrainzClient(
                    delay=max(mb_delay, 1.0),
                    user_agent={
                        'app_name': 'lidarr-album-import-universal-parser',
                        'version': '2.1',
                        'contact': getattr(config, 'musicbrainz_contact', 'your.email@example.com')
                    }
                )
            except Exception:
                logging.warning("⚠️  Could not load config for MusicBrainz - using defaults")
                self.mb_client = MusicBrainzClient(
                    delay=max(mb_delay, 1.0),
                    user_agent={
                        'app_name': 'lidarr-album-import-universal-parser',
                        'version': '2.1',
                        'contact': 'your.email@example.com'
                    }
                )

        logging.info(f"🔍 Enriching {len(self.entries)} entries with MusicBrainz metadata...")
        logging.info(f"   Rate limit: {mb_delay:.1f}s between requests")
        # Dump entries state so we can verify album vs album_search per entry
        logging.debug("Entries queued for enrichment:")
        for i, e in enumerate(self.entries):
            logging.debug(f"  [{i}] {e.artist} - {e.album} (album_search: {e.album_search})")

        progress_bar = tqdm(self.entries, desc="MusicBrainz lookup", unit="album", file=sys.stderr)
        for entry in progress_bar:
            progress_bar.set_postfix_str(f"{entry.artist[:30]}...", refresh=False)
            logging.debug(f"Processing entry for MB lookup: {entry.artist} - {entry.album} (album_search: {entry.album_search})")
            try:
                mb_artist = self.mb_client.search_artists(entry.artist, limit=1)
                artist_list = mb_artist.get('artist-list', [])
                if artist_list:
                    best_artist = artist_list[0]
                    entry.mb_artist_id = best_artist.get('id', '')
                    logging.info(f"✅ Artist '{entry.artist}' → '{best_artist.get('name')}' (ID: {entry.mb_artist_id})")
                else:
                    logging.info(f"❌ Artist '{entry.artist}' → No match found")

                # Use a normalized album_search title (stripped of edition suffixes) for more reliable matches
                search_album = entry.album_search or entry.album
                # When we have an MB artist id, pass it to release-group search to query by arid: which is more deterministic
                mb_release = self.mb_client.search_release_groups(entry.artist, search_album, limit=5, artist_mbid=entry.mb_artist_id if entry.mb_artist_id else None)
                release_list = mb_release.get('release-group-list', [])
                if release_list:
                    best_release = release_list[0]
                    entry.mb_release_id = best_release.get('id', '')
                    logging.info(f"✅ Album '{entry.album}' → '{best_release.get('title', '')}' (ID: {entry.mb_release_id}, Score: {best_release.get('ext:score', 'N/A')})")
                    try:
                        score = int(best_release.get('ext:score', '100'))
                    except Exception:
                        score = 100
                    if score < 85:
                        if not entry.matching_risk:
                            entry.matching_risk = True
                            entry.risk_reason = f"Low MB match score: {score}"
                        else:
                            entry.risk_reason = self._append_risk_reason(entry.risk_reason, f"Low MB match score: {score}")
                else:
                    logging.info(f"❌ Album '{entry.album}' → No match found")
                    # we'll compute overall counters after loop; mark failures where neither artist nor release were found
                    if not entry.mb_artist_id:
                        self.stats['mb_failed'] += 1
            except Exception as e:
                logging.error(f"❌ Error processing '{entry.artist}' - '{entry.album}': {e}")
                self.stats['mb_failed'] += 1

            if output_path:
                try:
                    self.write_output(output_path, include_risk_column=False, skip_risky=False)
                except Exception as e:
                    logging.warning(f"⚠️  Failed to update CSV after processing '{entry.artist}' - '{entry.album}': {e}")

        # Recompute summary counters from entry fields so logs are consistent with output
        release_matches = sum(1 for e in self.entries if e.mb_release_id)
        artist_only = sum(1 for e in self.entries if e.mb_artist_id and not e.mb_release_id)
        failed = self.stats.get('mb_failed', 0)
        self.stats['mb_enriched'] = release_matches
        self.stats['mb_artist_matches'] = artist_only

        total = len(self.entries)
        logging.info(f"✅ MusicBrainz enrichment complete: {release_matches}/{total} albums have release matches")
        if artist_only > 0:
            logging.info(f"   ℹ️ {artist_only} entries matched artist only (no release)")
        if failed > 0:
            logging.info(f"   ❌ {failed} lookups failed")

    def parse_file(self, file_path: str, **kwargs) -> None:
        format_type = self.detect_format(file_path)
        self.stats['format_detected'] = format_type

        if format_type == 'spotify_csv':
            self.parse_spotify_csv(
                file_path,
                min_artist_songs=kwargs.get('min_artist_songs', 3),
                min_album_songs=kwargs.get('min_album_songs', 2),
                artist_filter=kwargs.get('artist'),
                album_filter=kwargs.get('album'),
                max_items=kwargs.get('max_items')
            )
        elif format_type == 'simple_csv':
            self.parse_simple_csv(file_path, artist_filter=kwargs.get('artist'), album_filter=kwargs.get('album'), max_items=kwargs.get('max_items'))
        elif format_type in ['text_dash', 'text_by', 'tsv']:
            self.parse_text_format(file_path, format_type, artist_filter=kwargs.get('artist'), album_filter=kwargs.get('album'), max_items=kwargs.get('max_items'))
        else:
            logging.info("🔄 Trying best-effort parsing...")
            try:
                self.parse_simple_csv(file_path)
            except Exception as e:
                logging.error(f"❌ Failed to parse file: {e}")
                return

        if not self.entries:
            logging.error("❌ No valid entries found in input file")
            return

        self.deduplicate_exact()
        self.deduplicate_fuzzy()
        logging.info(f"✨ Final result: {len(self.entries)} unique artist/album pairs")

    def write_output(self, output_path: str, include_risk_column: bool = False, skip_risky: bool = False) -> None:
        # Work on a shallow copy so we don't mutate self.entries while other
        # processes (e.g. the enrichment loop) may be iterating over it.
        entries_to_write = list(self.entries)
        if skip_risky:
            entries_to_write = [e for e in self.entries if not e.matching_risk]
            skipped = len(self.entries) - len(entries_to_write)
            if skipped > 0:
                logging.info(f"   Skipped {skipped} risky entries")

        entries_to_write.sort(key=lambda e: (e.artist.lower(), e.album.lower()))
        has_mb_ids = any(e.mb_artist_id or e.mb_release_id for e in entries_to_write)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Include album_search column so downstream tools can use a normalized title for lookups
            header = ['artist', 'album', 'album_search']
            if has_mb_ids:
                header.extend(['mb_artist_id', 'mb_release_id'])
            if include_risk_column:
                header.extend(['matching_risk', 'risk_reason'])
            writer.writerow(header)

            for entry in entries_to_write:
                # Only write album_search if it differs from the original album
                album_search_value = entry.album_search if entry.album_search and entry.album_search != entry.album else ''
                row = [entry.artist, entry.album, album_search_value]
                if has_mb_ids:
                    row.extend([entry.mb_artist_id, entry.mb_release_id])
                if include_risk_column:
                    row.extend(['TRUE' if entry.matching_risk else 'FALSE', entry.risk_reason])
                writer.writerow(row)

        logging.info(f"💾 Wrote {len(entries_to_write)} entries to {output_path}")

    def print_statistics(self) -> None:
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

        if self.entries:
            print("\n📝 Sample entries (first 5):")
            for entry in self.entries[:5]:
                risk_indicator = " ⚠️" if entry.matching_risk else ""
                mb_indicator = " 📍" if entry.mb_release_id else ""
                print(f"   • {entry.artist} - {entry.album}{risk_indicator}{mb_indicator}")
            if len(self.entries) > 5:
                print(f"   ... and {len(self.entries) - 5} more")

        if risky_count > 0 and risky_count <= 10:
            print(f"\n⚠️  Risky entries (may have MusicBrainz matching issues):")
            for entry in [e for e in self.entries if e.matching_risk]:
                print(f"   • {entry.artist} - {entry.album}")
                print(f"     Reason: {entry.risk_reason}")
        elif risky_count > 10:
            print(f"\n⚠️  {risky_count} risky entries found. Use --include-risk-info to see details in output CSV.")


def build_parser() -> argparse.ArgumentParser:
    epilog = """
EXAMPLES:
  py -3 scripts/universal_parser.py input.txt -o albums.csv

QUICK ALIAS (optional):
  PowerShell (add to $PROFILE):
    function up { py -3 "C:\\path\\to\\repo\\scripts\\universal_parser.py" @args }

  Bash:
    alias up='py -3 /path/to/repo/scripts/universal_parser.py'
"""

    parser = argparse.ArgumentParser(
        description="Universal parser for artist/album data with intelligent normalization",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input', help='Input file (CSV, TSV, or text)')
    parser.add_argument('-o', '--output', default='albums.csv', help='Output CSV file (default: albums.csv)')
    parser.add_argument('--dry-run', action='store_true', help='Parse and show stats without writing output')
    parser.add_argument('--fuzzy-threshold', type=int, default=85, help='Fuzzy matching threshold 0-100 (default: 85)')
    parser.add_argument('--no-normalize', action='store_true', help='Skip normalization (keep original formatting)')
    parser.add_argument('--min-artist-songs', type=int, default=3, help='For Spotify: minimum songs per artist (default: 3)')
    parser.add_argument('--min-album-songs', type=int, default=2, help='For Spotify: minimum songs per album (default: 2)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose debug logging')
    parser.add_argument('--max-items', type=int, help='Limit number of items to process (useful for debugging)')
    parser.add_argument('--include-risk-info', action='store_true', help='Include matching_risk and risk_reason columns in output CSV')
    parser.add_argument('--skip-risky', action='store_true', help='Exclude entries flagged as risky from output')
    parser.add_argument('--no-enrich-musicbrainz', action='store_true', help='Skip MusicBrainz enrichment (faster, but requires manual MB ID resolution in import script)')
    parser.add_argument('--mb-delay', type=float, default=2.0, help='Delay between MusicBrainz requests in seconds (default: 2.0, min: 1.0)')
    parser.add_argument('--artist', type=str, help='Process only albums by specific artist (case-insensitive partial match)')
    parser.add_argument('--album', type=str, help='Process only albums matching specific title (case-insensitive partial match)')

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    up = UniversalParser(fuzzy_threshold=args.fuzzy_threshold, normalize=not args.no_normalize)

    try:
        up.parse_file(
            args.input,
            min_artist_songs=args.min_artist_songs,
            min_album_songs=args.min_album_songs,
            artist=args.artist,
            album=args.album,
            max_items=args.max_items,
        )
    except FileNotFoundError:
        logging.error(f"File not found: {args.input}")
        sys.exit(1)
    except Exception as exc:
        logging.error(f"Error parsing file: {exc}")
        sys.exit(1)

    # Note: artist/album/max-items filters are applied during parsing to avoid
    # unnecessary MusicBrainz lookups. They are passed into parse_file above.

    if not args.no_enrich_musicbrainz:
        try:
            output_path = args.output if not args.dry_run else None
            up.enrich_with_musicbrainz(mb_delay=args.mb_delay, output_path=output_path)
        except Exception as e:
            logging.error(f"❌ Error during MusicBrainz enrichment: {e}")
            logging.warning("⚠️  Continuing without enrichment...")

    up.print_statistics()

    if not args.dry_run:
        up.write_output(args.output, include_risk_column=args.include_risk_info, skip_risky=args.skip_risky)
        logging.info(f"✅ Done! Output ready for: py -3 add_albums_to_lidarr.py {args.output}")
    else:
        logging.info("🔍 Dry run complete - no output file written")


if __name__ == '__main__':
    main()


def apply_item_filters(
    items: List[Dict[str, str]],
    *,
    skip_completed: bool = True,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    status: Optional[str] = None,
    exclude_status: Optional[str] = None,
    max_items: Optional[int] = None,
    skip_existing: bool = False,
    existing_artists: Optional[Dict[str, Dict[str, Any]]] = None,
    csv_handler: Optional[Any] = None,
) -> List[Dict[str, str]]:
    """Apply common item-level filters (moved from add_albums_to_lidarr).

    This centralizes filtering so callers (scripts) can delegate parsing
    and filtering logic to the universal parser module.
    """
    # 1) Skip completed / permanent failures using CSVHandler helper if available
    if skip_completed and csv_handler is not None:
        items = csv_handler.filter_items_by_status(items, skip_completed=True, skip_permanent_failures=True)
    elif skip_completed:
        items = [it for it in items if not ItemStatus.is_success(it.get('status', '')) and not ItemStatus.is_skip(it.get('status', ''))]

    # 2) (legacy) Only failures handled via `status='failed'` token

    # 3) Artist filter
    if artist:
        af = artist.lower()
        items = [it for it in items if af in it['artist'].lower()]

    # 4) Album filter
    if album:
        af = album.lower()
        items = [it for it in items if af in it['album'].lower()]

    # 5) Status filter - supports comma-separated values and special tokens
    #    Special tokens: 'new' => blank status; 'failed' => statuses where should_retry is True
    def _matches_status_token(st: str, token: str) -> bool:
        tl = token.lower()
        if tl in ('new', 'blank', 'none', 'empty'):
            return not (st or '').strip()
        if tl in ('failed', 'failure', 'fail', 'retry'):
            return ItemStatus.should_retry(st)
        # Exact-match comparisons are case-insensitive for convenience
        return (st or '').lower() == tl

    if status:
        tokens = [t.strip() for t in status.split(',') if t.strip()]
        filtered = []
        for it in items:
            st = (it.get('status') or '').strip()
            for token in tokens:
                if _matches_status_token(st, token):
                    filtered.append(it)
                    break
        items = filtered

    # 6) Only-new (blank status) - use status='new' token instead of legacy flag

    # 7) Exclude particular statuses (comma-separated). Support same special tokens as --status
    if exclude_status:
        tokens = [t.strip() for t in exclude_status.split(',') if t.strip()]
        filtered = []
        for it in items:
            st = (it.get('status') or '').strip()
            exclude = False
            for token in tokens:
                if _matches_status_token(st, token):
                    exclude = True
                    break
            if not exclude:
                filtered.append(it)
        items = filtered

    # 8) Skip existing artists (requires existing_artists dict with lowercased keys)
    if skip_existing and existing_artists is not None:
        items = [it for it in items if it['artist'].lower() not in existing_artists]

    # 9) Limit items
    if max_items and isinstance(max_items, int):
        items = items[:max_items]

    return items

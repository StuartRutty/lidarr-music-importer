"""Parser utility helpers extracted from the universal parser.

This module provides small, testable functions for Spotify ID
normalization and aggregation of CSV rows into per-(artist,album)
metadata buckets.
"""
from typing import Dict, Tuple, Any, Iterable, List, Set
import re
import csv
import json
from collections import defaultdict
from typing import Optional
from pathlib import Path
from datetime import datetime
import logging


def normalize_spotify_id(value: str) -> str:
    """Normalize a Spotify URI/URL or bare id into a bare Spotify id string.

    Returns empty string when the value cannot be interpreted as a Spotify id.
    """
    if not value:
        return ''
    v = str(value).strip()
    # spotify:album:ID or spotify:artist:ID
    if v.startswith('spotify:'):
        parts = v.split(':')
        if len(parts) >= 3:
            return parts[-1]
        return ''
    # https://open.spotify.com/album/ID?si=...
    if 'open.spotify.com/album/' in v:
        try:
            tail = v.split('open.spotify.com/album/', 1)[1]
            return tail.split('?')[0].split('/')[0]
        except Exception:
            return ''
    # plain URL maybe with /album/<id>
    if '/album/' in v:
        try:
            tail = v.split('/album/', 1)[1]
            return tail.split('?')[0].split('/')[0]
        except Exception:
            return ''
    # Otherwise, it might already be an ID (alphanumeric, length >= 10)
    if re.match(r'^[A-Za-z0-9]{8,}$', v):
        return v
    return ''


def aggregate_spotify_rows(rows: Iterable[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Aggregate an iterable of CSV-like rows (dicts) into per-(artist,album)
    metadata buckets.

    The returned mapping maps (artist, album) -> meta dict with keys:
      spotify_album_id, spotify_artist_id, spotify_album_url, release_date,
      track_titles (list), track_isrcs (list)
    """
    meta_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def find_key_for(row: Dict[str, str], primary_terms, secondary_terms):
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

    for row in rows:
        # best-effort header/key detection
        artist_key = find_key_for(row, ['artist name'], ['artist'])
        album_key = find_key_for(row, ['album name'], ['album'])
        if not artist_key or not album_key:
            continue
        artist_raw = row.get(artist_key, '')
        album_raw = row.get(album_key, '')
        if not artist_raw or not album_raw:
            continue
        # prefer first artist if comma separated
        if ',' in artist_raw:
            artist_raw = artist_raw.split(',')[0]
        artist = artist_raw.strip()
        album = album_raw.strip()
        key = (artist, album)
        if key not in meta_map:
            meta_map[key] = {
                'spotify_album_id': '',
                'spotify_artist_id': '',
                'spotify_album_url': '',
                'release_date': '',
                'track_titles': [],
                'track_isrcs': [],
            }

        album_meta = row.get(find_key_for(row, ['album id', 'album uri'], ['id', 'uri']) or '', '')
        artist_meta = row.get(find_key_for(row, ['artist id'], ['artist id', 'artistid']) or '', '')
        album_url = row.get(find_key_for(row, ['album url', 'album uri', 'track url'], ['url', 'uri']) or '', '')
        release_date = row.get(find_key_for(row, ['release date', 'album release date'], ['release']) or '', '')
        track_name = row.get(find_key_for(row, ['track name'], ['track']) or '', '')
        isrc = row.get(find_key_for(row, ['isrc'], ['isrc']) or '', '')

        # Normalize IDs using the shared helper
        norm_album_id = normalize_spotify_id(album_meta) or normalize_spotify_id(album_url)
        if norm_album_id and not meta_map[key]['spotify_album_id']:
            meta_map[key]['spotify_album_id'] = norm_album_id
        norm_artist_id = normalize_spotify_id(artist_meta)
        if norm_artist_id and not meta_map[key]['spotify_artist_id']:
            meta_map[key]['spotify_artist_id'] = norm_artist_id
        if album_url and not meta_map[key]['spotify_album_url']:
            meta_map[key]['spotify_album_url'] = album_url
        if release_date and not meta_map[key]['release_date']:
            meta_map[key]['release_date'] = release_date
        if track_name:
            meta_map[key]['track_titles'].append(track_name)
        if isrc:
            meta_map[key]['track_isrcs'].append(isrc)

    # Deduplicate track lists
    for m in meta_map.values():
        if m.get('track_titles'):
            # preserve order while deduping
            seen: List[str] = []
            out: List[str] = []
            for t in m['track_titles']:
                if t not in seen:
                    seen.append(t)
                    out.append(t)
            m['track_titles'] = out
        if m.get('track_isrcs'):
            seen = []
            out = []
            for i in m['track_isrcs']:
                if i not in seen:
                    seen.append(i)
                    out.append(i)
            m['track_isrcs'] = out

    return meta_map


def parse_spotify_export(csv_path: str) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """Parse a Spotify liked songs CSV export (row-based) and return artist->album counts

    Returns the same shape as the legacy script: (artist_albums, artist_totals)
    where artist_albums is {artist: {album: track_count}} and artist_totals is {artist: total_tracks}
    """
    artist_albums = defaultdict(lambda: defaultdict(int))
    artist_totals = defaultdict(int)

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return {}, {}

        for row in reader:
            if len(row) < 6:
                continue

            # Best-effort mapping for common Spotify export columns (legacy script used indices)
            # The original script used indices 3 (Artist Name), 5 (Album Name), 7 (Album Artist)
            artist_names = row[3].strip() if len(row) > 3 else ''
            album_name = row[5].strip() if len(row) > 5 else ''
            album_artist = row[7].strip() if len(row) > 7 else ''

            primary_artist = album_artist if album_artist else artist_names
            if ',' in primary_artist:
                primary_artist = primary_artist.split(',')[0].strip()

            if not primary_artist or not album_name:
                continue

            artist_albums[primary_artist][album_name] += 1
            artist_totals[primary_artist] += 1

    return dict(artist_albums), dict(artist_totals)


def filter_artist_albums(artist_albums: Dict[str, Dict[str, int]], artist_totals: Dict[str, int], min_artist_songs: int = 3, min_album_songs: int = 2) -> Dict[str, Dict[str, int]]:
    """Filter artist/album counts by minimum thresholds.

    Keeps only artists with total tracks >= min_artist_songs and albums with count >= min_album_songs.
    """
    filtered = {}
    for artist, albums in artist_albums.items():
        if artist_totals.get(artist, 0) < min_artist_songs:
            continue
        filtered_albums = {album: count for album, count in albums.items() if count >= min_album_songs}
        if filtered_albums:
            filtered[artist] = filtered_albums
    return filtered


def generate_artist_album_output(filtered_data: Dict[str, Dict[str, int]], output_csv: str, output_json: Optional[str] = None) -> None:
    """Write CSV (artist,album) and optional JSON analysis file from filtered artist->albums map."""
    artist_album_pairs = []
    for artist, albums in filtered_data.items():
        for album in albums.keys():
            artist_album_pairs.append([artist, album])
    artist_album_pairs.sort(key=lambda x: (x[0].lower(), x[1].lower()))

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['artist', 'album'])
        writer.writerows(artist_album_pairs)

    logging.info(f"Created CSV with {len(artist_album_pairs)} artist/album pairs: {output_csv}")

    if output_json:
        analysis_data = {
            'metadata': {
                'total_artists': len(filtered_data),
                'total_albums': sum(len(albums) for albums in filtered_data.values()),
                'total_artist_album_pairs': len(artist_album_pairs)
            },
            'artists': {}
        }
        for artist, albums in filtered_data.items():
            analysis_data['artists'][artist] = {
                'total_songs': sum(albums.values()),
                'albums': albums
            }
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Created analysis JSON: {output_json}")


def print_spotify_stats(artist_totals: Dict[str, int], filtered_data: Dict[str, Dict[str, int]], min_artist_songs: int, min_album_songs: int) -> None:
    total_artists = len(artist_totals)
    total_songs = sum(artist_totals.values())
    filtered_artists = len(filtered_data)
    filtered_albums = sum(len(albums) for albums in filtered_data.values())
    filtered_songs = sum(sum(albums.values()) for albums in filtered_data.values())

    print(f"\n=== FILTERING STATISTICS ===")
    print(f"Original data:")
    print(f"  - {total_artists} artists")
    print(f"  - {total_songs} total songs")

    print(f"\nFiltered data (≥{min_artist_songs} songs per artist, ≥{min_album_songs} songs per album):")
    if total_artists:
        print(f"  - {filtered_artists} artists ({filtered_artists/total_artists*100:.1f}%)")
    else:
        print(f"  - {filtered_artists} artists")
    print(f"  - {filtered_albums} albums")
    print(f"  - {filtered_songs} songs")

    print(f"\nTop 10 artists by album count:")
    artist_album_counts = [(artist, len(albums)) for artist, albums in filtered_data.items()]
    artist_album_counts.sort(key=lambda x: x[1], reverse=True)
    for artist, album_count in artist_album_counts[:10]:
        song_count = sum(filtered_data[artist].values())
        print(f"  - {artist}: {album_count} albums, {song_count} songs")


def normalize_album_title(album_title: str) -> str:
    """Expose the title normalization function here (moved from scripts).

    This keeps the repository's normalization logic in one shared place.
    """
    # Reuse the earlier logic from normalize_album_titles.py but keep it smaller/focused
    if not album_title:
        return album_title

    preserve_patterns = [
        r'\(sic\)',
        r'\([Vv]ol\.?\s*\d+\)',
        r'\([Vv]olume\s+\d+\)',
        r'\(#\d+\)',
        r'\([Pp]t\.?\s*\d+\)',
        r'\(&[^)]+\)',
        r'\([^)]{3,}(?:Version|Mode)\)',
    ]

    for preserve in preserve_patterns:
        if re.search(preserve, album_title):
            temp = album_title
            for p in preserve_patterns:
                temp = re.sub(p, '', temp)
            if not re.search(r'\([^)]*(?:deluxe|remaster|edition|explicit|complete|extended|expanded|collector)\s*[^)]*\)', temp, re.IGNORECASE):
                return album_title

    edition_patterns = [
        r'\s*\(\s*deluxe\s*\)',
        r'\s*\(\s*deluxe\s+edition\s*\)',
        r'\s*\(\s*deluxe\s+version\s*\)',
        r'\s*\(\s*remaster(ed)?\s*\)',
        r'\s*\(\s*\d{4}\s+remaster\s*\)',
        # Match forms like (2015 Remaster) or (2015 Remastered Edition)
        r'\s*\(\s*\d{4}[^)]*remaster(?:ed)?[^)]*\)'
        r'\s*\(\s*\d+(?:th|st|nd|rd)\s+anniversary[^)]*\)',
        r'\s*\(\s*explicit\s*\)',
        r'\s*\(\s*clean\s*\)',
        r'\s*\[\s*explicit\s*\]',
        r'\s*\[\s*deluxe\s*\]',
    ]

    normalized = album_title
    for pattern in edition_patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    normalized = ' '.join(normalized.split()).strip()
    if not normalized:
        return album_title
    normalized = re.sub(r'\s*[,\-:;]+\s*$', '', normalized).strip()
    return normalized if normalized else album_title


def needs_normalization(album_title: str) -> bool:
    if not album_title:
        return False
    return normalize_album_title(album_title) != album_title


def clean_text(text: str) -> str:
    """Clean special characters from artist/album names (moved from scripts)."""
    if not text:
        return text
    # Remove brackets around entire field
    text = re.sub(r'^\[([^\]]+)\]$', r'\1', text)
    # Remove brackets but keep content
    text = re.sub(r'\[([^\]]*)\]', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def create_backup(csv_file: Path) -> Path:
    """Create a timestamped backup of the original CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{csv_file.stem}_backup_{timestamp}{csv_file.suffix}"
    backup_path = csv_file.parent / backup_name

    backup_path.write_text(csv_file.read_text(encoding='utf-8'), encoding='utf-8')
    logging.info(f"Created backup: {backup_path}")
    return backup_path


def process_csv(csv_file: Path, status_filter: Optional[Set[str]] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Process the CSV file and normalize album titles.

    This function mirrors the behavior in `scripts/normalize_album_titles.py` but
    is now available as a reusable library function for tests and other scripts.
    """
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    # Read the CSV file
    rows, fieldnames = read_csv_to_rows(csv_file)

    if not fieldnames:
        raise ValueError("CSV file appears to be empty or invalid")

    # Use the pure transform to get modified rows/fieldnames and stats
    new_rows, new_fieldnames, stats = normalize_rows(rows, list(fieldnames), status_filter=status_filter, apply_changes=not dry_run)

    # Write modified CSV if not dry run and changes made
    if not dry_run and stats['changed_rows'] > 0:
        write_rows_to_csv(csv_file, new_rows, new_fieldnames, make_backup=True)

    return stats


def normalize_rows(rows: List[Dict[str, str]], fieldnames: List[str], status_filter: Optional[Set[str]] = None, apply_changes: bool = True) -> Tuple[List[Dict[str, str]], List[str], Dict[str, Any]]:
    """Pure transform: normalize album titles in given rows.

    Args:
        rows: list of row dicts (as returned by csv.DictReader)
        fieldnames: original fieldnames list
        status_filter: optional set of allowed status values (rows with other statuses are skipped)
        apply_changes: if False, returns stats and rows unchanged but reports what would change

    Returns:
        (new_rows, new_fieldnames, stats)
    """
    # Validate required columns
    required_columns = ['artist', 'album', 'status']
    missing_columns = [col for col in required_columns if col not in fieldnames]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Ensure original_album exists in fieldnames
    new_fieldnames = list(fieldnames)
    if 'original_album' not in new_fieldnames:
        album_index = new_fieldnames.index('album')
        new_fieldnames.insert(album_index + 1, 'original_album')

    stats = {
        'total_rows': len(rows),
        'processed_rows': 0,
        'changed_rows': 0,
        'skipped_by_status': 0,
        'changes': []
    }

    new_rows: List[Dict[str, str]] = []
    for i, row in enumerate(rows):
        artist = row.get('artist', '')
        album = row.get('album', '')
        status = row.get('status', '')

        if status_filter and status not in status_filter:
            stats['skipped_by_status'] += 1
            new_rows.append(row.copy())
            continue

        stats['processed_rows'] += 1

        if needs_normalization(album):
            normalized_album = normalize_album_title(album)
            out_row = row.copy()
            if not out_row.get('original_album'):
                out_row['original_album'] = album
            if apply_changes:
                out_row['album'] = normalized_album

            change_info = {
                'row': i + 1,
                'artist': artist,
                'original': album,
                'normalized': normalized_album,
                'status': status
            }
            stats['changes'].append(change_info)
            stats['changed_rows'] += 1
            new_rows.append(out_row)
        else:
            new_rows.append(row.copy())

    return new_rows, new_fieldnames, stats


def read_csv_to_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    """Read a CSV file into a list of row dicts and return (rows, fieldnames).

    `path` may be a Path or string. Uses utf-8 encoding.
    """
    p = Path(path)
    with p.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, list(fieldnames)


def write_rows_to_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str], make_backup: bool = True) -> None:
    """Write rows (list of dict) to CSV at `path` with given fieldnames.

    If make_backup is True and the destination exists, a timestamped backup will
    be created using `create_backup`.
    """
    p = Path(path)
    if make_backup and p.exists():
        create_backup(p)
    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

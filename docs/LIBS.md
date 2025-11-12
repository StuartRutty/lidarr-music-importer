## Library reference (lib/)

This page summarizes the purpose and public helpers in the `lib/` package.
It is intended as a quick reference for contributors who want to reuse
parsing, normalization, I/O and MusicBrainz client logic from scripts and tests.

Each section lists the primary public functions, a short description, and an example usage.

---

### lib/models.py

Purpose: shared data models used across scripts and tests.

Public:
- AlbumEntry (dataclass)
  - Represents a single artist/album item that the universal parser and enrichers work with.
  - Use when you need a stable shape for album data in code and tests.

Example:

```py
from lib.models import AlbumEntry

ae = AlbumEntry(artist='Nirvana', album='Nevermind')
print(ae.artist, ae.album)
```

---

### lib/parser_utils.py

Purpose: pure parsing and normalization helpers extracted from the scripts. Keep logic here
so it can be tested without side-effects.

Key public helpers (signatures):
- normalize_spotify_id(value: str) -> str
  - Normalize Spotify URIs/URLs or bare IDs to the bare Spotify id string.

- aggregate_spotify_rows(rows: Iterable[Dict[str,str]]) -> Dict[Tuple[str,str], Dict[str,Any]]
  - Aggregate CSV-like rows into per-(artist,album) metadata buckets (spotify ids, urls, track lists).

- parse_spotify_export(csv_path: str) -> Tuple[Dict[str, Dict[str,int]], Dict[str,int]]
  - Parse a Spotify liked-songs CSV export into artist->album track counts and per-artist totals.

- filter_artist_albums(artist_albums: Dict[str,Dict[str,int]], artist_totals: Dict[str,int], min_artist_songs: int = 3, min_album_songs: int = 2) -> Dict[str,Dict[str,int]]
  - Filter out artists/albums below thresholds.

- generate_artist_album_output(filtered_data: Dict[str,Dict[str,int]], output_csv: str, output_json: Optional[str] = None) -> None
  - Write a CSV and optional JSON analysis from filtered artist->album mapping.

- normalize_album_title(album_title: str) -> str
  - Normalize album title text (strip common edition tokens while preserving explicit volume/part/sic qualifiers when appropriate).

- needs_normalization(album_title: str) -> bool
  - Quick predicate to test if a title would change by normalization.

- clean_text(text: str) -> str
  - Small utility to normalize whitespace/strip brackets from artist/album strings.

- normalize_rows(rows: List[Dict[str,str]], fieldnames: List[str], status_filter: Optional[Set[str]] = None, apply_changes: bool = True) -> Tuple[List[Dict[str,str]], List[str], Dict[str,Any]]
  - Pure transform: normalize album titles in a list of dict rows. Returns (new_rows, new_fieldnames, stats).

- process_csv(csv_file: Path, status_filter: Optional[Set[str]] = None, dry_run: bool = False) -> Dict[str,Any]
  - IO wrapper around `normalize_rows` which reads/writes CSV files and returns stats. Uses `lib.io_utils` for file operations.

- read_csv_to_rows(path: Path) -> Tuple[List[Dict[str,str]], List[str]]
- write_rows_to_csv(path: Path, rows: List[Dict[str,str]], fieldnames: List[str], make_backup: bool = True) -> None
  - Convenience functions for reading/writing CSVs. These are thin wrappers; after the IO refactor these call into `lib.io_utils`.

Example: normalize a CSV in-place with a dry run

```py
from pathlib import Path
from lib.parser_utils import process_csv

stats = process_csv(Path('albums.csv'), dry_run=True)
print(stats['changes'][:5])
```

Notes:
- `normalize_rows` is pure and recommended for unit testing because it doesn't touch disk.
- `process_csv` will create a timestamped backup before overwriting the original file (unless `dry_run=True`).

---

### lib/io_utils.py

Purpose: centralize CSV file I/O and backup semantics. Scripts use this module so all file operations behave consistently.

Public helpers (signatures):
- create_backup(csv_file: Path) -> Path
  - Create a timestamped copy of `csv_file` in the same directory and return the backup Path.

- read_csv_to_rows(path: Path) -> Tuple[List[Dict[str,str]], List[str]]
  - Read a CSV file and return (rows, fieldnames). Rows are list of dicts (csv.DictReader semantics).

- write_rows_to_csv(path: Path, rows: List[Dict[str,str]], fieldnames: List[str], make_backup: bool = True) -> None
  - Write rows to `path` using the provided fieldnames. When `make_backup` is True and the destination exists, a timestamped backup is created.

Example:

```py
from pathlib import Path
from lib.io_utils import read_csv_to_rows, write_rows_to_csv

rows, fieldnames = read_csv_to_rows(Path('albums.csv'))
# modify rows in memory...
write_rows_to_csv(Path('albums.csv'), rows, fieldnames)
```

---

### lib/musicbrainz_client.py

Purpose: wrapper around MusicBrainz release/artist search logic. Includes helpers and heuristics to
prefer Spotify relations when selecting the best-release match and to decode JSON responses first
with an XML fallback (some servers return either format).

Public notes:
- The client exposes search functions used by the universal parser/enricher. It will attempt
  to populate release and artist identifiers (`mb_release_id`, `mb_artist_id`) even when a release
  match is not found (artist-only matches are supported).
- Heuristics summary (high-level):
  - Prefer releases that include Spotify relations matching the parsed Spotify album id.
  - Prefer exact-title matches and year-matching when available.
  - Use fuzzy matching as a fallback.

Example usage is in `scripts/universal_parser.py`; tests exercise the selection heuristics in `tests/test_musicbrainz_client.py`.

---

Migration notes & tips

- If you previously copied small read/write helper code in multiple `scripts/` files, switch imports to
  `from lib.io_utils import read_csv_to_rows, write_rows_to_csv` to centralize behavior.

- Prefer `normalize_rows` for unit tests because it does not touch the filesystem. Use `process_csv` only in
  CLI scripts or integration tests where file changes are intended.

- When using the MusicBrainz client from tests, prefer constructing small controlled response fixtures rather
  than hitting the network. The test suite includes mocks for MusicBrainz responses.

---

If anything here is unclear or you'd like runnable examples added for a particular helper, tell me which helpers
you want expanded and I'll add short snippets and tests demonstrating common scenarios.

---

## Short examples (quick start)

These tiny snippets show common patterns for using the `lib` helpers directly from scripts or a REPL.

- Read a CSV into rows and fieldnames (useful for small scripts and experiments):

```python
from pathlib import Path
from lib import read_csv_to_rows

rows, fieldnames = read_csv_to_rows(Path('albums.csv'))
print(f"Read {len(rows)} rows, fields: {fieldnames}")
for r in rows[:5]:
  print(r.get('artist'), '-', r.get('album'))
```

- Use `process_csv` to normalize album titles in-place (creates a timestamped backup unless dry_run=True):

```python
from pathlib import Path
from lib import process_csv

# Dry-run to see what would change
stats = process_csv(Path('albums.csv'), status_filter=None, dry_run=True)
print(stats['changed_rows'], 'rows would change')

# To apply changes:
# process_csv(Path('albums.csv'), status_filter=None, dry_run=False)
```

- Create and inspect an `AlbumEntry` object (useful when composing in-memory flows or writing tests):

```python
from lib import AlbumEntry

ae = AlbumEntry(artist='Taylor Swift', album='1989')
print(ae.artist, ae.album, ae.album_search)
```

- Aggregate Spotify export rows for per-(artist,album) metadata (IDs, URLs, track lists):

```python
from pathlib import Path
from lib import read_csv_to_rows, aggregate_spotify_rows

rows, _ = read_csv_to_rows(Path('spotify_export.csv'))
meta = aggregate_spotify_rows(rows)
for (artist, album), m in list(meta.items())[:10]:
  print(artist, '-', album, '→', m.get('spotify_album_id'))
```

- Clean a single field using the shared text helper:

```python
from lib import clean_text

print(clean_text('[Explicit] The Album (Deluxe)'))
# → 'The Album (Deluxe)'
```

---

Try these snippets in a small script or the Python REPL. If you'd like I can add a `scripts/examples/` folder with short runnable scripts demonstrating these flows (and CI checks for them).

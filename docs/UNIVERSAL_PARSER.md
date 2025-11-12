# Universal Parser - Intelligent Artist/Album Data Parser

## Overview

`universal_parser.py` is an all-purpose parser and normalizer that intelligently handles artist/album data from multiple input formats. It uses **rapidfuzz** for smart deduplication and fuzzy matching to clean data before creating `albums.csv` for Lidarr import.

## Key Features

✨ **Auto-Format Detection** - Automatically identifies input format  
🔍 **Fuzzy Deduplication** - Merges near-duplicate entries using rapidfuzz  
🧹 **Intelligent Normalization** - Cleans artist/album names consistently  
📊 **Multi-Format Support** - Handles Spotify exports, CSV, text files  
🎯 **Smart Column Detection** - Figures out which column is artist vs album  
📈 **Detailed Statistics** - Shows exactly what was cleaned and merged  

## Supported Input Formats

### 1. Spotify CSV Export
The full export from Spotify with all metadata columns:
```csv
Track Name,Artist Name(s),Album Name,Album Artist Name(s),...
DNA.,Kendrick Lamar,DAMN.,Kendrick Lamar,...
```

**Features:**
- Uses album artist when available
- Filters by minimum track counts per artist/album
- Handles multiple artists (comma-separated)

### 2. Simple CSV (with headers)
```csv
artist,album
Kendrick Lamar,DAMN.
Drake,Views
```

OR

```csv
album,artist
DAMN.,Kendrick Lamar
Views,Drake
```

**Auto-detects column order!**

### 3. Simple CSV (without headers)
```csv
Kendrick Lamar,DAMN.
Drake,Views
```

Uses heuristics to determine which column is artist vs album.

### 4. Text File - Dash Format
```
Kendrick Lamar - DAMN.
Drake - Views
The Weeknd - Starboy
```

### 5. Text File - "by" Format
```
DAMN. by Kendrick Lamar
Views by Drake
Starboy by The Weeknd
```

### 6. Tab-Separated Values
```
Kendrick Lamar	DAMN.
Drake	Views
```

## Usage

### Basic Usage
```bash
# Auto-detect format and parse
py -3 universal_parser.py input.csv

# Outputs: albums.csv (ready for add_albums_to_lidarr.py)
```

### Spotify Export with Filtering
```bash
# Filter out artists with <3 songs and albums with <2 songs
py -3 universal_parser.py spotify_export.csv --min-artist-songs 3 --min-album-songs 2
```

### Custom Fuzzy Threshold
```bash
# More aggressive deduplication (90% similarity merges entries)
py -3 universal_parser.py my_list.txt --fuzzy-threshold 90

# Disable fuzzy matching (exact matches only)
py -3 universal_parser.py my_list.txt --fuzzy-threshold 100
```

### Preview Mode
```bash
# Dry run - see what would be parsed without creating output
py -3 universal_parser.py input.csv --dry-run
```

### Skip Normalization
```bash
# Keep original formatting (no cleaning)
py -3 universal_parser.py input.csv --no-normalize
```

### Custom Output File
```bash
py -3 universal_parser.py input.csv -o my_albums.csv
```

### Verbose Mode
```bash
# Show detailed debug logging
py -3 universal_parser.py input.csv -v
```

## Fuzzy Matching Examples

The fuzzy deduplication intelligently merges variations:

| Entry 1 | Entry 2 | Similarity | Action |
|---------|---------|------------|--------|
| `DAMN.` | `DAMN. (Deluxe)` | 87% | ✅ Merged |
| `Views` | `Views (Deluxe Edition)` | 88% | ✅ Merged |
| `good kid, m.A.A.d city` | `Good Kid M.A.A.D City` | 92% | ✅ Merged |
| `The Life of Pablo` | `The Life Of Pablo [Explicit]` | 94% | ✅ Merged |
| `Blonde` | `Blond` | 91% | ✅ Merged |
| `DAMN.` | `2014 Forest Hills Drive` | 15% | ❌ Kept separate |

Default threshold: **85%** (configurable with `--fuzzy-threshold`)

## Normalization Features

### Artist Name Normalization
- Strips extra whitespace: `"  Drake  "` → `"Drake"`
- Normalizes Unicode quotes: `"Ol' Burger Beats"` → `"Ol' Burger Beats"`
- Handles special characters: `"$uicideboy$"` → preserved correctly

### Album Title Normalization
- Removes edition markers: `"DAMN. (Deluxe)"` → `"DAMN."`
- Cleans brackets: `"[Album Name]"` → `"Album Name"`
- Strips extra whitespace and formatting
- Preserves meaningful qualifiers like `(Vol. 2)`, `(EP)`

See `lib/text_utils.py` for full normalization logic.

## Output Format

Creates a clean CSV with the standard format:

```csv
artist,album
Drake,Views
Kendrick Lamar,DAMN.
The Weeknd,Starboy
```

This format is **directly compatible** with `add_albums_to_lidarr.py`.

## Statistics Output

The parser provides detailed statistics:

```
📊 PARSING STATISTICS
======================================================================
Format detected:       spotify_csv
Raw entries parsed:    1523
Exact duplicates:      47
Fuzzy duplicates:      23
Filtered artists:      12
Filtered albums:       8

✨ Final unique pairs:  1433
======================================================================

📝 Sample entries (first 5):
   • Drake - Views
   • J. Cole - 2014 Forest Hills Drive
   • Kendrick Lamar - DAMN.
   • The Weeknd - Starboy
   • Travis Scott - ASTROWORLD
   ... and 1428 more
```

## Integration with Lidarr Import

After parsing, use the output directly:

```bash
# 1. Parse and normalize your data
py -3 universal_parser.py spotify_export.csv

# 2. Import to Lidarr
py -3 add_albums_to_lidarr.py albums.csv
```

## Command Line Options

```
positional arguments:
  input                 Input file (CSV, TSV, or text)

options:
  -h, --help            Show help message
  -o OUTPUT, --output OUTPUT
                        Output CSV file (default: albums.csv)
  --dry-run             Parse and show stats without writing output
  --fuzzy-threshold N   Fuzzy matching threshold 0-100 (default: 85)
  --no-normalize        Skip normalization (keep original formatting)
  --min-artist-songs N  For Spotify: minimum songs per artist (default: 3)
  --min-album-songs N   For Spotify: minimum songs per album (default: 2)
  -v, --verbose         Enable verbose debug logging
```

## Testing

Run the test suite to verify all format parsers:

```bash
py -3 -m pytest tests/test_universal_parser.py
```

Tests include:
- Spotify CSV export format
- Simple CSV with headers
- Headerless CSV with auto-detection
- Text file (Artist - Album)
- Text file (Album by Artist)
- Tab-separated values

## Common Workflows

### Workflow 1: Spotify Export
```bash
# Export your Spotify liked songs to CSV
# Parse with filtering
py -3 universal_parser.py spotify_liked_songs.csv --min-artist-songs 3

# Import to Lidarr
py -3 add_albums_to_lidarr.py albums.csv
```

### Workflow 2: Manual Copy-Paste List
```bash
# Copy artist/album pairs from anywhere and paste into a text file
# Format: "Artist - Album" (one per line)

# Parse and clean
py -3 universal_parser.py my_manual_list.txt

# Import to Lidarr
py -3 add_albums_to_lidarr.py albums.csv
```

### Workflow 3: Existing CSV Cleanup
```bash
# You have a messy CSV with duplicates and variations
py -3 universal_parser.py messy_data.csv --fuzzy-threshold 90 -o cleaned.csv

# Review the statistics to see what was merged
# Then import
py -3 add_albums_to_lidarr.py cleaned.csv
```

## Troubleshooting

### "No valid entries found"
- Check that your file has at least 2 columns (artist and album)
- Verify file encoding is UTF-8
- Use `--verbose` to see detailed parsing logs

### Too many duplicates merged
- Increase fuzzy threshold: `--fuzzy-threshold 95`
- Or disable fuzzy matching: `--fuzzy-threshold 100`

### Not enough duplicates merged
- Lower fuzzy threshold: `--fuzzy-threshold 80`
- Be careful not to go too low (risk of false positives)

### Format not detected
- The parser will attempt best-effort parsing
- Try explicitly formatting your data as CSV with headers
- Use `--verbose` to see detection logic

## Advanced Usage

### Chain with other tools

```bash
# Parse → Normalize titles → Clean → Import
py -3 universal_parser.py spotify.csv
py -3 normalize_album_titles.py albums.csv
py -3 clean_albums.py
py -3 add_albums_to_lidarr.py albums.csv
```

### Filter output programmatically

```bash
# Parse everything first
py -3 universal_parser.py all_music.csv

# Then filter with add_albums_to_lidarr.py options
py -3 add_albums_to_lidarr.py albums.csv --artist "Kendrick"
```

## Dependencies

- Python 3.7+
- rapidfuzz (for fuzzy matching)
- Standard library: csv, re, argparse, logging, collections

Install dependencies:
```bash
py -3 -m pip install rapidfuzz
```

## Related Tools

- `add_albums_to_lidarr.py` - Main import script
- `normalize_album_titles.py` - Additional title normalization
- `clean_albums.py` - Character cleaning
- `lib/text_utils.py` - Text normalization utilities
- `lib/csv_handler.py` - CSV read/write utilities

## Contributing

The parser uses modular design:
- `UniversalParser` class handles all parsing logic
- `AlbumEntry` dataclass represents each artist/album pair
- Format detection is extensible (add new formats easily)

To add a new format:
1. Add detection logic to `detect_format()`
2. Create a `parse_<format>()` method
3. Update the format routing in `parse_file()`

## License

Part of the lidarr-music-importer project.

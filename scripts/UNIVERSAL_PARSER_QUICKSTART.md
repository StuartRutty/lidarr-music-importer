# Universal Parser - Quick Start Guide

## What It Does

**Universal Parser** automatically detects your input format and creates a clean `albums.csv` file ready for Lidarr import. It handles Spotify exports, CSV files, text lists, and more!

## Quick Examples

### Example 1: Parse a Spotify Export
```bash
py -3 universal_parser.py spotify_export.csv
# Output: albums.csv (filtered and cleaned)
```

### Example 2: Parse a Manual List
Create a text file `my_music.txt`:
 py -3 universal_parser.py spotify_export.csv
Kendrick Lamar - DAMN.
Drake - Views
The Weeknd - Starboy
```

Parse it:
```bash
py -3 universal_parser.py my_music.txt
# Output: albums.csv
```

### Example 3: Parse a Simple CSV
Create `music.csv`:
 py -3 universal_parser.py my_music.txt
artist,album
Kendrick Lamar,DAMN.
Drake,Views
```

Parse it:
```bash
py -3 universal_parser.py music.csv
# Output: albums.csv
```

## What Gets Cleaned
````markdown
# Universal Parser - Quick Start Guide

## What It Does

The Universal Parser auto-detects common input formats (Spotify CSV, plain CSV, or simple text lists) and outputs a cleaned `albums.csv` suitable for Lidarr import.

## Quick Examples

### Parse a Spotify export
```bash
py -3 universal_parser.py spotify_export.csv
# produces: albums.csv
```

### Parse a simple text list
Create `my_music.txt` with one album per line in the form `Artist - Album`:
```
Kendrick Lamar - DAMN.
Drake - Views
The Weeknd - Starboy
```

Then run:
```bash
py -3 universal_parser.py my_music.txt
# produces: albums.csv
```

### Parse a CSV with headers
Create `music.csv`:
```csv
artist,album
Kendrick Lamar,DAMN.
Drake,Views
```

Then run:
```bash
py -3 universal_parser.py music.csv
# produces: albums.csv
```

## Common Options

```bash
# Preview only (no file written)
py -3 universal_parser.py input.csv --dry-run

# Custom output filename
py -3 universal_parser.py input.csv -o my_albums.csv

# Verbose debugging
py -3 universal_parser.py input.csv -v

# Disable fuzzy merging (exact-only)
py -3 universal_parser.py input.csv --fuzzy-threshold 100

# Skip normalization / keep original formatting
py -3 universal_parser.py input.csv --no-normalize

# Spotify-specific filters: keep artists/albums with minimum track counts
py -3 universal_parser.py spotify.csv --min-artist-songs 5 --min-album-songs 3
```

## Workflow

1. Parse your raw data:

```bash
py -3 universal_parser.py my_music_list.txt
```

2. (Optional) Inspect `albums.csv` and make adjustments.

3. Import into Lidarr:

```bash
py -3 add_albums_to_lidarr.py albums.csv
```

Run the test suite for the parser:
```bash
py -3 -m pytest tests/test_universal_parser.py
```

## Supported Input Formats

| Format | Example | Auto-detected |
|--------|---------|---------------|
| Spotify CSV | `Track Name,Artist Name(s),...` | ✅ |
| CSV with headers | `artist,album` | ✅ |
| CSV without headers | `Drake,Views` | ✅ |
| Text: `Artist - Album` | `Drake - Views` | ✅ |
| Text: `Album by Artist` | `Views by Drake` | ✅ |
| Tab-separated | `Drake\tViews` | ✅ |

## Troubleshooting

- "No valid entries found": ensure file encoding is UTF-8 and each row contains artist and album columns or uses an accepted text format.
- If too many albums are merged, raise `--fuzzy-threshold`.
- If duplicates remain, lower `--fuzzy-threshold` slightly.

## Tips

- Always run a dry run first: `py -3 universal_parser.py input.csv --dry-run`.
- Use `-v` to get debug output explaining why lines were accepted/filtered.
- Test with a small sample before processing your full library.

## See also

- Full docs: `docs/UNIVERSAL_PARSER.md`
- Parser utilities: `lib/text_utils.py`

Run `py -3 universal_parser.py --help` for the full list of options.

````
# Only include artists with 5+ songs, albums with 3+ songs

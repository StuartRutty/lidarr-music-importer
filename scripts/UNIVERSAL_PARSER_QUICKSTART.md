# Universal Parser - Quick Start Guide

## What It Does

**Universal Parser** automatically detects your input format and creates a clean `albums.csv` file ready for Lidarr import. It handles Spotify exports, CSV files, text lists, and more!

## Quick Examples

### Example 1: Parse a Spotify Export
```bash
python universal_parser.py spotify_export.csv
# Output: albums.csv (filtered and cleaned)
```

### Example 2: Parse a Manual List
Create a text file `my_music.txt`:
```
Kendrick Lamar - DAMN.
Drake - Views
The Weeknd - Starboy
```

Parse it:
```bash
python universal_parser.py my_music.txt
# Output: albums.csv
```

### Example 3: Parse a Simple CSV
Create `music.csv`:
```csv
artist,album
Kendrick Lamar,DAMN.
Drake,Views
```

Parse it:
```bash
python universal_parser.py music.csv
# Output: albums.csv
```

## What Gets Cleaned

### Exact Duplicates Removed
- `Drake, Views` (line 1)
- `Drake, Views` (line 2)
→ **Merged into one entry**

### Fuzzy Duplicates Merged (85% similarity threshold)
- `DAMN.`
- `DAMN. (Deluxe Edition)`
→ **Merged into: `DAMN.`**

- `Views`
- `Views (Deluxe)`
→ **Merged into: `Views`**

### Whitespace Cleaned
- `  Drake  ` → `Drake`
- `  Views  (Deluxe)  ` → `Views (Deluxe)`

### Special Characters Normalized
- `Ol' Burger Beats` → `Ol' Burger Beats` (proper apostrophe)
- `F*ck Love` → `F*ck Love` (preserved)

## Common Options

```bash
# Preview without creating files
python universal_parser.py input.csv --dry-run

# Custom output filename
python universal_parser.py input.csv -o my_albums.csv

# More aggressive deduplication
python universal_parser.py input.csv --fuzzy-threshold 90

# Disable fuzzy matching (exact only)
python universal_parser.py input.csv --fuzzy-threshold 100

# Keep original formatting (no cleaning)
python universal_parser.py input.csv --no-normalize

# Spotify: filter minimum tracks
python universal_parser.py spotify.csv --min-artist-songs 5 --min-album-songs 3
```

## Complete Workflow

```bash
# Step 1: Parse your data
python universal_parser.py my_music_list.txt

# Step 2: (Optional) Normalize album titles further
python normalize_album_titles.py albums.csv

# Step 3: Import to Lidarr
python add_albums_to_lidarr.py albums.csv
```

## Supported Input Formats

| Format | Example | Auto-Detected? |
|--------|---------|----------------|
| Spotify CSV | `Track Name,Artist Name(s),...` | ✅ Yes |
| CSV with headers | `artist,album` | ✅ Yes |
| CSV without headers | `Drake,Views` | ✅ Yes |
| Text: Artist - Album | `Drake - Views` | ✅ Yes |
| Text: Album by Artist | `Views by Drake` | ✅ Yes |
| Tab-separated | `Drake⇥Views` | ✅ Yes |

## Troubleshooting

### "No valid entries found"
- Check file encoding (should be UTF-8)
- Ensure you have 2 columns (artist & album)
- Try: `python universal_parser.py input.csv -v` for debug info

### Too many albums merged
- Increase fuzzy threshold: `--fuzzy-threshold 95`

### Not enough duplicates removed
- Lower fuzzy threshold: `--fuzzy-threshold 80`

### Wrong columns detected
- Add headers to your CSV: `artist,album`
- Or use explicit formatting: `Artist - Album` per line

## Output Statistics

Example output:
```
📊 PARSING STATISTICS
======================================================================
Format detected:       text_dash
Raw entries parsed:    100
Exact duplicates:      15
Fuzzy duplicates:      8

✨ Final unique pairs:  77
======================================================================
```

This means:
- Started with 100 entries
- Removed 15 exact duplicates
- Merged 8 fuzzy duplicates
- Final clean output: 77 unique albums

## Tips

💡 **Always do a dry run first**
```bash
python universal_parser.py input.csv --dry-run
```

💡 **Use verbose mode to understand what's happening**
```bash
python universal_parser.py input.csv -v
```

💡 **For Spotify exports, adjust filters to your preference**
```bash
# Only include artists with 5+ songs, albums with 3+ songs
python universal_parser.py spotify.csv --min-artist-songs 5 --min-album-songs 3
```

💡 **Test with a small sample first**
```bash
# Create a small test file with 10 entries
# Run the parser
# Verify the output looks good
# Then process your full dataset
```

## See Also

- Full documentation: `docs/UNIVERSAL_PARSER.md`
- Test suite: `python test_universal_parser.py`
- Text utilities: `lib/text_utils.py`

## Need Help?

Run with `--help` for all options:
```bash
python universal_parser.py --help
```

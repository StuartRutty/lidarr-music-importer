# CSV Input Cleaning Enhancement

## Summary

Enhanced the album import script to automatically clean and normalize artist names and album titles from CSV input **before** searching MusicBrainz or Lidarr APIs. This improves search accuracy and match rates by handling common CSV data quality issues.

## Changes Made

### 1. New Function: `clean_csv_input()` in `lib/text_utils.py`

A comprehensive cleaning function that normalizes CSV input data through multiple steps:

**For Both Artists and Albums:**
- Strips leading/trailing whitespace
- Normalizes Unicode characters (handles accents, ligatures)
- Removes zero-width and invisible characters
- Normalizes quotation marks to standard ASCII (curly quotes → straight quotes)
- Collapses multiple spaces to single space
- Normalizes censored profanity (F*ck → Fuck)

**For Albums Only:**
- Removes common suffixes that prevent matching:
  - EP/Single markers: "Winter - EP" → "Winter"
  - Deluxe editions: "(Deluxe Edition)" → ""
  - Featuring artists: "(& Artist)" or "(feat. Artist)" → ""
  - Explicit/Clean tags: "[Explicit]" → ""
  - Remastered editions: "(Remastered)" → ""
  - Collector's/Anniversary/Special editions: "(Collector's Edition)" → ""

### 2. Enhanced `normalize_profanity()` Function

Updated to preserve original capitalization:
- "F*ck" → "Fuck" (title case preserved)
- "f*ck" → "fuck" (lowercase preserved)
- "F*CK" → "FUCK" (uppercase preserved)

### 3. Enhanced `strip_album_suffixes()` Function

Added more edition patterns:
- Collector's Edition
- Anniversary Edition
- Special Edition
- Bonus Track Version

### 4. Integration in `add_albums_to_lidarr.py`

Modified the main processing loop to clean CSV data immediately upon reading:

```python
# Before (raw CSV data used directly):
artist = item["artist"]
album = item["album"]

# After (cleaned data used for API searches):
raw_artist = item["artist"]
raw_album = item["album"]

artist = clean_csv_input(raw_artist, is_artist=True)
album = clean_csv_input(raw_album, is_artist=False)
```

**Important:** Raw values are still used for CSV status updates to ensure proper row matching.

## Benefits

### Improved Search Accuracy
- Removes noise that prevents API matches
- Handles inconsistent spacing and Unicode variations
- Normalizes common album edition markers

### Better Match Rates
- "Lanterns - EP" now matches "Lanterns" in MusicBrainz
- "good kid, m.A.A.d city (Deluxe)" matches base album
- Handles curly apostrophes, special quotes, etc.

### Automatic Data Quality Fixes
- No manual CSV cleanup needed for common issues
- Consistent formatting across different data sources
- Handles copy-paste artifacts (zero-width spaces, etc.)

## Examples

### Real-World Cleaning Examples

| Raw CSV Input | Cleaned Output | What Changed |
|---------------|----------------|--------------|
| `  Son  Lux  ` | `Son Lux` | Whitespace normalized |
| `Lanterns - EP` | `Lanterns` | EP suffix removed |
| `F*ck Love (Deluxe)` | `Fuck Love` | Profanity + Deluxe removed |
| `good kid, m.A.A.d city (Deluxe)` | `good kid, m.A.A.d city` | Deluxe removed |
| `DAMN. (Collector's Edition)` | `DAMN.` | Edition removed |
| `Ol' Burger Beats` | `Ol' Burger Beats` | Curly apostrophe normalized |

## Testing

Comprehensive test suite added: `tests/test_csv_cleaning.py`

**Test Results:**
- ✅ 9/9 artist name cleaning tests passed
- ✅ 13/13 album title cleaning tests passed
- ✅ 6/6 edge case tests passed
- ✅ Real-world examples validated

Run tests: `python tests/test_csv_cleaning.py`

## Technical Details

### Unicode Normalization
Uses `unicodedata.normalize('NFKC')` for compatibility composition:
- Handles accented characters (é, ñ, etc.)
- Normalizes ligatures and special characters
- Ensures consistent representation across platforms

### Regex Patterns
Case-insensitive matching for edition markers:
- `\s*\([Dd]eluxe[^)]*\)\s*$` matches any Deluxe variant
- `\s*-?\s*EP\s*$` handles both "- EP" and "EP"
- `\s*\(feat\.?[^)]*\)\s*$` catches all featuring artist formats

### Profanity Normalization
Smart replacement preserving capitalization:
- First letter uppercase + rest lowercase → Title Case
- All uppercase → UPPERCASE  
- All lowercase → lowercase

## Usage

The cleaning is **automatic** and requires no code changes for normal use:

```bash
# Just run the script as usual - cleaning happens automatically
python add_albums_to_lidarr.py albums.csv
```

To see what was cleaned, enable debug logging:
```bash
python add_albums_to_lidarr.py albums.csv --log-file import.log
```

Check the log file for messages like:
```
CSV cleaning applied:
  Artist: 'Ol' Burger Beats' -> 'Ol' Burger Beats'
  Album: 'Lanterns - EP' -> 'Lanterns'
```

## Compatibility

- ✅ Backward compatible - existing scripts continue to work
- ✅ No breaking changes to CSV format
- ✅ Status updates use original CSV values for proper row matching
- ✅ Works with all existing command-line arguments

## Future Enhancements

Possible improvements:
- Add more profanity patterns as needed
- Handle more edition variants discovered in real usage
- Add optional strict mode that rejects uncleanable input
- Export cleaned CSV for review before processing

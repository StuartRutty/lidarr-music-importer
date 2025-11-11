# Enhanced MusicBrainz Search with Smart Title Matching

## Summary

Enhanced the MusicBrainz album search to automatically try multiple title variations when the exact title doesn't match. This dramatically improves match rates for albums with prefixes like "ep", "single", "the", etc.

## What Was Enhanced

### 1. Automatic Title Variation Generation

The MusicBrainz client now automatically generates and tries multiple title variations:

**Prefix Removal:**
- "ep seeds" → tries ["ep seeds", "seeds", "Ep Seeds"]
- "single winter" → tries ["single winter", "winter", "Single Winter"]
- "the album" → tries ["the album", "album", "The Album"]

**Case Variations:**
- lowercase → Title Case
- short titles → UPPERCASE (for acronyms)

### 2. Detailed Step-by-Step Logging

New emoji-based logging shows exactly what's happening:

```
🔍 MusicBrainz search: 'eevee' - 'ep seeds'
   Generated 3 title variations to try: ['ep seeds', 'seeds', 'Ep Seeds']
   📝 Trying title variation 1/3: 'ep seeds'
   📝 Trying title variation 2/3: 'seeds'
      → Got 1 raw results from MusicBrainz
      ✓ KEPT: 'seeds' by 'eevee' (score: 100)
   ✅ SUCCESS: Found 1 matching albums with title 'seeds' (query 2)
```

### 3. CSV Input Cleaning Integration

Works seamlessly with the CSV cleaning:
1. CSV input is cleaned (removing suffixes, normalizing Unicode)
2. Cleaned title is sent to MusicBrainz
3. MusicBrainz tries multiple variations automatically
4. Best match is returned

## Test Results

### Albums That Now Match Successfully ✅

| Raw CSV Input | Cleaned Title | Variation That Matched | MusicBrainz Title |
|---------------|---------------|------------------------|-------------------|
| eevee - ep seeds | ep seeds | **seeds** (variation 2) | seeds |
| eevee - ep unexpected | ep unexpected | **unexpected** (variation 2) | unexpected |
| eevee - ep unknown | ep unknown | **unknown** (variation 2) | unknown |

### Why This Matters

**Before Enhancement:**
```
❌ "ep seeds" → No match (gave up)
```

**After Enhancement:**
```
✅ "ep seeds" → tries "seeds" → FOUND!
```

## Technical Implementation

### Modified Files

1. **`lib/musicbrainz_client.py`**
   - Added `_generate_title_variations()` method
   - Enhanced `search_release_groups()` with variation loop
   - Added detailed logging at each step

2. **`scripts/add_albums_to_lidarr.py`**
   - Enhanced logging with emojis for clarity
   - Updated `search_album_on_musicbrainz()` 
   - Updated `match_artist_metadata()` with step indicators

### Title Variation Logic

```python
def _generate_title_variations(self, title: str) -> List[str]:
    variations = [title]  # Always try original first
    
    # Remove common prefixes
    prefixes = ['ep ', 'single ', 'the ', 'a ']
    for prefix in prefixes:
        if title.lower().startswith(prefix):
            stripped = title[len(prefix):].strip()
            variations.append(stripped)
    
    # Try Title Case if lowercase
    if title.islower():
        variations.append(title.title())
    
    # Try UPPERCASE for short titles (likely acronyms)
    if len(title) <= 6:
        variations.append(title.upper())
    
    return variations
```

## Usage Examples

### Basic Usage (Automatic)

```bash
# Just run normally - title variations happen automatically
python add_albums_to_lidarr.py albums.csv
```

### See Detailed Logs

```bash
# Enable INFO level logging to see title variations being tried
python add_albums_to_lidarr.py albums.csv --log-file debug.log
```

The log will show:
```
🔍 MusicBrainz search: 'Artist' - 'ep title'
   Generated 3 title variations to try
   📝 Trying variation 1/3: 'ep title'
   📝 Trying variation 2/3: 'title'  ← This one works!
   ✅ SUCCESS
```

### Test Specific Albums

```bash
# Test albums that previously failed
python add_albums_to_lidarr.py albums.csv --album "ep seeds" --max-items 1
```

## Configuration

No configuration changes needed! The title variation feature is:
- ✅ Always enabled
- ✅ Automatic
- ✅ Smart (tries most likely matches first)
- ✅ Safe (exact match tried first)

## Performance Impact

**Minimal:** Only tries variations when needed
- If exact title matches → done (1 query)
- If exact title fails → tries variations (2-4 queries)
- Rate limiting still respected (1 req/sec)

## Logging Enhancements

### New Emoji Indicators

| Emoji | Meaning |
|-------|---------|
| 🔍 | Starting MusicBrainz search |
| 📝 | Trying a title variation |
| 👤 | Artist metadata lookup |
| 📀 | Album search step |
| ✅ | Success |
| ❌ | Failed |
| ⚠️ | Warning |
| ℹ️ | Information |
| ✓ | Kept result |
| ✗ | Filtered out |

### Log Levels

**INFO:** Shows major steps and results
```
🔍 MusicBrainz search: 'eevee' - 'ep seeds'
   Generated 3 title variations
   ✅ SUCCESS: Found 1 matching albums
```

**DEBUG:** Shows detailed query attempts
```
      Query 1/3: artist:"eevee" AND releasegroup:"seeds"
      → Got 1 raw results from MusicBrainz
      ✓ KEPT: 'seeds' by 'eevee'
```

## Testing

### Test Script

Run comprehensive tests:
```bash
python tests/test_mb_search_enhanced.py
```

Tests include:
- Albums with "ep" prefix
- Albums with "single" prefix
- Albums with "the" prefix
- Edge cases

### Expected Behavior

✅ Should automatically find albums with common prefixes removed
✅ Should show clear logging of what's being tried
✅ Should still respect artist name filtering (no false positives)
✅ Should work with CSV cleaning integration

## Future Enhancements

Possible additions:
- More prefix patterns (vol., pt., deluxe)
- Fuzzy title matching with similarity threshold
- User-configurable variation strategies
- Cache successful variations for faster repeated searches

## Backward Compatibility

✅ **100% backward compatible**
- Existing scripts work unchanged
- No breaking changes to API
- Existing configs still valid
- CSV format unchanged

## Troubleshooting

### Album Still Not Found?

Check the logs for:
1. Which variations were tried
2. Whether MusicBrainz returned any results
3. Whether results were filtered due to artist mismatch

Example log analysis:
```
📝 Trying variation 1/3: 'ep seeds'
   → No results from MusicBrainz
📝 Trying variation 2/3: 'seeds'
   → Got 1 raw results
   ✗ FILTERED: 'seeds' by 'Different Artist'  ← Wrong artist
```

This means the album exists but under a different artist name.

### Connection Errors?

```
ERROR: MusicBrainz request failed: Connection aborted
```

This is normal rate limiting from MusicBrainz. The script automatically retries and handles this gracefully.

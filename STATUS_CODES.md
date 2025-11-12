# Album Import Status Code Reference

## Overview
The album import script uses clear, actionable status codes to track processing progress. Each status indicates the exact state of an artist/album pair and provides guidance on what to do next.

## Status Code Categories

### ✅ SUCCESS STATES (completed, no retry needed)
These statuses indicate successful completion. Items with these statuses will be skipped by `--skip-completed`.

| Status Code | Description | Next Action |
|-------------|-------------|-------------|
| `success` | Album successfully added and monitored | None - complete |
| `already_monitored` | Album was already being monitored when checked | None - complete |
| `artist_added` | New artist added to Lidarr and album monitored | None - complete |

### ⏳ PENDING STATES (temporary, retry recommended)
These statuses indicate partial completion. Items may succeed if retried after some time.

| Status Code | Description | Next Action |
|-------------|-------------|-------------|
| `pending_refresh` | Artist exists but album not found, metadata refresh triggered | Wait 5-10 minutes, then retry |
| `pending_import` | Album added to Lidarr, waiting for automatic import | Wait for Lidarr to process, then check status |

### 🚫 SKIP STATES (permanent, no retry needed)  
These statuses indicate permanent issues. Items with these statuses will be skipped by `--skip-completed`.

| Status Code | Description | Next Action |
|-------------|-------------|-------------|
| `skip_no_musicbrainz` | Album not found on MusicBrainz | Verify album title/artist, or skip |
| `skip_no_artist_match` | Artist not found in any metadata sources | Verify artist name spelling |
| `skip_api_error` | Lidarr API authentication/authorization failed | Check API key and permissions |

### ❌ ERROR STATES (temporary, retry possible)
These statuses indicate temporary issues that may resolve with retry. Use `--status failed` to retry these.

| Status Code | Description | Next Action |
|-------------|-------------|-------------|
| `error_connection` | Network/connection issues | Check network, retry later |
| `error_timeout` | Request timeout | Retry with slower network or increased timeouts |
| `error_invalid_data` | Invalid/malformed data from APIs | Check data quality, may need manual fix |
| `error_unknown` | Unexpected error occurred | Check logs for details, retry or report issue |

### 🧪 TESTING STATES
| Status Code | Description | Next Action |
|-------------|-------------|-------------|
| `dry_run` | Processed in test mode without making changes | Run without --dry-run to actually process |

## Command-Line Usage with Status Codes

### Initial Import
```bash
# Process all items (automatically skips completed on subsequent runs)
python add_albums_to_lidarr.py albums.csv

# Test first 5 items
python add_albums_to_lidarr.py albums.csv --dry-run --max-items 5
```

### Resume Interrupted Import
```bash
# Skip completed and permanent failures, process pending/errors only (default behavior)
python add_albums_to_lidarr.py albums.csv

# Process ALL items including completed ones
python add_albums_to_lidarr.py albums.csv --no-skip-completed
```

### Retry Failed Items
```bash
# Process only error states and pending states
# Use the new tokenized --status flag. Use the special token 'failed' to select retryable items.
python add_albums_to_lidarr.py albums.csv --status failed
```

### Status-Specific Processing
After running the script, check your CSV file. You can filter by status to understand what happened:

- **All successful**: `success`, `already_monitored`, `artist_added`
- **Need time**: `pending_refresh`, `pending_import` (wait 5-10 minutes, then retry)
- **Need attention**: `skip_no_musicbrainz`, `skip_no_artist_match` (verify data)
- **Temporary issues**: `error_connection`, `error_timeout`, etc. (retry later)

## Workflow Examples

### Handling Pending Items
If you see items with `pending_refresh` status:
1. Wait 5-10 minutes for Lidarr to refresh artist metadata
2. Run: `python add_albums_to_lidarr.py albums.csv` (completed items automatically skipped)

### Fixing Connection Issues  
If you see many `error_connection` items:
1. Check your network connection to Lidarr
2. Verify Lidarr is running and accessible
3. Run: `python add_albums_to_lidarr.py albums.csv --status failed`

## Filtering with --status / --not-status

The importer supports a flexible `--status` filter that accepts comma-separated
status names and a couple of special tokens for convenience:

- `new` — select rows with a blank/empty `status` column
- `failed` — select rows that should be retried (use `--status failed`, replaces the old `--only-failures`)

Examples:

```bash
# Select items that are pending or errored
python add_albums_to_lidarr.py albums.csv --status pending_refresh,error_connection

# Select only rows that have no status (new items)
python add_albums_to_lidarr.py albums.csv --status new

# Exclude already_monitored and skip_no_musicbrainz
python add_albums_to_lidarr.py albums.csv --not-status already_monitored,skip_no_musicbrainz
```

### MusicBrainz Issues
If you see `skip_no_musicbrainz` items:
1. Check if album titles have typos or extra characters
2. Verify artist names match MusicBrainz format (no extra punctuation)
3. Consider manual searches on musicbrainz.org to verify data exists

## CSV Status Column
The script automatically adds a `status` column to your CSV file. This enables:
- **Resumable imports**: Restart interrupted large imports
- **Progress tracking**: See exactly what succeeded/failed  
- **Targeted retries**: Process only specific status types
- **Status reporting**: Get detailed counts of each outcome

Example CSV after processing:
```csv
artist,album,status
Taylor Swift,1989,success
The Beatles,Abbey Road,already_monitored
Unknown Artist,Bad Album,skip_no_musicbrainz
Network Artist,Some Album,error_connection
```

## Troubleshooting by Status

### High `skip_no_musicbrainz` Count
- **Cause**: Album titles don't match MusicBrainz database
- **Solution**: Check for typos, extra punctuation, or format differences
- **Tool**: Use musicbrainz.org to verify correct album titles

### High `error_connection` Count  
- **Cause**: Network issues between script and Lidarr/MusicBrainz
- **Solution**: Check Lidarr accessibility, network stability
- **Tool**: Use `--request-delay` parameter to slow down requests

### High `pending_refresh` Count
- **Cause**: Normal for newly added artists - Lidarr needs time to fetch metadata
- **Solution**: Wait 5-10 minutes, then rerun (completed items automatically skipped)
- **Tool**: Check Lidarr's System → Events for refresh completion

### High `skip_api_error` Count
- **Cause**: Lidarr API key or permission issues
- **Solution**: Verify API key in script settings, check Lidarr logs
- **Tool**: Test with `--max-items 1` to isolate API issues
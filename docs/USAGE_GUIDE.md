# Usage Guide - Lidarr Music Importer

**Version 2.0** - Updated for new modular architecture

This guide covers common usage scenarios for the Lidarr Music Importer toolkit.

---

## 🚀 Getting Started

### 1. First-Time Setup (Updated for v2.0!)

```bash
# Navigate to the project directory
cd lidarr-music-importer

# Copy configuration template
cp config_template.py config.py

# Edit configuration with your settings
notepad config.py  # Windows
# or
nano config.py     # Linux/macOS
```

**Required Configuration (in config.py):**
```python
LIDARR_BASE_URL = "http://192.168.1.225:8686"  # Your Lidarr instance
LIDARR_API_KEY = "your-api-key-here"           # From Lidarr settings
ROOT_FOLDER_PATH = "/media/Music"              # Your music folder
```

**Alternative: Use Environment Variables**
```bash
export LIDARR_BASE_URL="http://192.168.1.225:8686"
export LIDARR_API_KEY="your-api-key"
export ROOT_FOLDER_PATH="/media/Music"
```

### 2. Verify Configuration

```bash
# Test configuration loads correctly
python -c "from lib.config import Config; c = Config(); print(c)"
```

### 3. Run Your First Import

```bash
# Test with example data (dry run)
python add_albums_to_lidarr.py ../examples/example_albums.csv --dry-run

# If test looks good, run for real
python add_albums_to_lidarr.py ../examples/example_albums.csv
```

## 📊 Working with Spotify Data

### Processing Spotify Export

If you have Spotify data, use the parsing script first:

```bash
# Process Spotify liked songs export
python parse_spotify_for_lidarr.py /path/to/liked.csv

# This creates: filtered_artist_album_pairs.csv

# Import the processed data
python add_albums_to_lidarr.py filtered_artist_album_pairs.csv
```

### Spotify Export Tips

1. **Request Your Data**: Go to Spotify Account Overview → Privacy Settings → Download your data
2. **Wait for Email**: Spotify will email you a download link (takes a few days)
3. **Extract liked.csv**: From the downloaded zip file
4. **Process**: Use our parsing script to filter and format

## 🔄 Managing Large Imports

### Batch Processing Strategy

For large datasets (500+ albums):

```bash
# Start with a small test
python add_albums_to_lidarr.py large_dataset.csv --dry-run --max-items 10

# Process in smaller batches
python add_albums_to_lidarr.py large_dataset.csv --batch-size 20

# Skip pauses for faster processing (use carefully)
python add_albums_to_lidarr.py large_dataset.csv --no-batch-pause --batch-size 50
```

### Handling Interruptions

```bash
# If import gets interrupted, resume from where you left off (default behavior)
python add_albums_to_lidarr.py your_data.csv

# Check progress by looking at status column in CSV
```

### Monitoring Progress

```bash
# Check how many items have each status
grep -c "completed" your_data.csv
grep -c "failed" your_data.csv
grep -c "refresh_triggered" your_data.csv

# Or view the CSV in Excel/Google Sheets for visual progress tracking
```

## 🎯 Targeting Specific Imports

### Processing Only Failed Items

```bash
# After fixing configuration issues, retry only failed items
python add_albums_to_lidarr.py your_data.csv --skip-completed
```

## MusicBrainz enrichment — parser-first workflow (Nov 2025)

Note: Recent refactoring moved all MusicBrainz lookups into the parsing step for better performance and reliability. The parser now enriches entries with MusicBrainz IDs by default and writes two new columns to its output CSV:

- `mb_artist_id` — MusicBrainz Artist UUID
- `mb_release_id` — MusicBrainz Release Group UUID (album-level)

Key points:

- The recommended workflow is:

   1. Run the universal parser (enrichment enabled by default):

       ```powershell
       cd lidarr-music-importer/scripts
       python universal_parser.py your_input.csv -o enriched_output.csv
       ```

   2. Run the import using the enriched CSV:

       ```powershell
       python add_albums_to_lidarr.py enriched_output.csv
       ```

- If you explicitly want to skip MusicBrainz enrichment (for troubleshooting or if you supply MB IDs by other means), pass `--no-enrich-musicbrainz` to `universal_parser.py`. Be aware: `add_albums_to_lidarr.py` will then require each row to include `mb_artist_id` (and `mb_release_id` when monitoring specific albums).

- Benefits of parser-first enrichment:
   - Eliminates redundant MusicBrainz API calls during import
   - Improves matching accuracy using pre-resolved MB IDs
   - Speeds up large imports (MB lookups batched and rate-limited in the parser)

Status code changes (user-facing):

- `already_monitored` — treated as a skip status (item was already monitored; the importer will not retry it)
- `skip_album_mb_noresults` — new skip status: artist exists in Lidarr but the specific release/album could not be found on MusicBrainz

These status codes appear in the CSV `status` column so you can filter and report on them. Use `--no-skip-completed` to include `already_monitored` items in a run for auditing purposes, but they won't be reprocessed by default.


### Testing Subsets

```bash
# Test with specific artists (create a smaller CSV)
head -20 large_dataset.csv > test_subset.csv
python add_albums_to_lidarr.py test_subset.csv --dry-run

# Test random sample
shuf -n 50 large_dataset.csv > random_sample.csv
python add_albums_to_lidarr.py random_sample.csv --dry-run
```

## 🛠️ Troubleshooting Workflows

### When Albums Don't Appear

Many albums need metadata refresh after adding the artist:

```bash
# Run import normally
python add_albums_to_lidarr.py your_data.csv

# Wait 10-15 minutes for Lidarr to refresh metadata
# Then run again to catch albums that are now available
python add_albums_to_lidarr.py your_data.csv --skip-completed
```

### Debugging API Issues

```bash
# Test Lidarr connection
python test_lidarr_connection.py

# Run with debug logging (edit script to set DEBUG level)
python add_albums_to_lidarr.py problem_albums.csv --max-items 5

# Check Lidarr logs for API errors
# Settings -> General -> Log Files
```

### Handling Rate Limits

If you get rate limit errors:

1. **Edit Configuration**: Increase delays in the script
   ```python
   LIDARR_REQUEST_DELAY = 5.0  # Increase from 2.0
   BATCH_PAUSE = 30.0          # Increase from 10.0
   ```

2. **Use Smaller Batches**:
   ```bash
   python add_albums_to_lidarr.py data.csv --batch-size 5
   ```

## 📁 Data Management

### CSV File Organization

Keep your data organized:

```
data/
├── raw_exports/
│   ├── spotify_liked_2024.csv
│   └── spotify_liked_2023.csv
├── processed/
│   ├── filtered_albums_2024.csv
│   └── high_priority_albums.csv
└── completed/
    └── imported_albums_2024.csv
```

### Backup Strategy

```bash
# Before large imports, backup your CSV
cp important_albums.csv important_albums_backup.csv

# Save processing logs
python add_albums_to_lidarr.py albums.csv > import_log.txt 2>&1
```

## 🔧 Advanced Customization

### Custom Filtering

Edit `parse_spotify_for_lidarr.py` to change filtering criteria:

```python
# Change minimum thresholds
MIN_SONGS_PER_ARTIST = 5    # Default: 3
MIN_SONGS_PER_ALBUM = 3     # Default: 2
```

### Performance Tuning

For very large imports:

```python
# In add_albums_to_lidarr.py configuration
BATCH_SIZE = 50             # Larger batches
LIDARR_REQUEST_DELAY = 1.0  # Faster requests (if API can handle it)
BATCH_PAUSE = 5.0           # Shorter pauses
```

## 📋 Common Command Patterns

### Daily Workflow Commands

```bash
# Quick test of new data
python add_albums_to_lidarr.py new_albums.csv --dry-run --max-items 10

# Import small dataset
python add_albums_to_lidarr.py new_albums.csv

# Resume large import
python add_albums_to_lidarr.py large_import.csv --skip-completed

# Fast import (no pauses)
python add_albums_to_lidarr.py urgent_albums.csv --no-batch-pause
```

### Quality Assurance

```bash
# Always test first
python add_albums_to_lidarr.py data.csv --dry-run

# Check data quality
wc -l data.csv                    # Count total lines
grep -c "^[^,]*,[^,]*$" data.csv  # Count valid artist,album pairs

# Validate after import
python test_lidarr_connection.py
```

## 💡 Tips and Best Practices

1. **Start Small**: Always test with `--dry-run` and `--max-items`
2. **Monitor Progress**: Use the status column to track completion
3. **Be Patient**: Large imports take time; use appropriate delays
4. **Check Logs**: Both script output and Lidarr logs help debug issues
5. **Backup Data**: Keep copies of your CSV files before processing
6. **Regular Updates**: Periodically update the scripts and requirements
7. **Respect APIs**: Don't overwhelm Lidarr or MusicBrainz with too many requests

---

## 📚 Additional Resources

- **Configuration Setup**: [QUICKSTART_REFACTORING.md](../QUICKSTART_REFACTORING.md)
- **Production Flags**: [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md)
- **Status Codes**: [STATUS_CODES.md](../STATUS_CODES.md)
- **Refactoring Details**: [REFACTORING.md](../REFACTORING.md)

## 🆕 What's New in v2.0?

- ✅ **New Configuration System**: Use `config.py` file or environment variables
- ✅ **Modular Code**: Core functionality in `lib/` modules (reusable!)
- ✅ **Better Security**: No more hardcoded API keys in source
- ✅ **Backward Compatible**: All existing commands still work

**Migrating from v1.x?** See [QUICKSTART_REFACTORING.md](../QUICKSTART_REFACTORING.md)

---

## 🆘 Getting Help

If you encounter issues:

1. **Check Configuration**: Verify all settings in the script
2. **Test Connection**: Use `test_lidarr_connection.py`
3. **Review Logs**: Look at both script output and Lidarr logs
4. **Start Simple**: Try with a small, known-good dataset
5. **Check Prerequisites**: Ensure all requirements are installed

---

For more detailed information, see the main README.md file.
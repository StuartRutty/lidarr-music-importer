<!-- Consolidated Usage + Production guide (merged from PRODUCTION_GUIDE.md and USAGE_GUIDE.md) -->
# Usage & Production Guide - Lidarr Music Importer

This consolidated document combines the previous `PRODUCTION_GUIDE.md` and `USAGE_GUIDE.md` into a single reference covering common usage, configuration, and production workflows.

---

<!-- Begin: content from PRODUCTION_GUIDE.md -->

# 🚀 Production Flags Guide - Lidarr Music Importer

**Version 2.0** - Updated for new configuration system

This guide covers the best command-line flags for different production scenarios with the Lidarr Music Importer.

---

## ⚙️ Initial Setup (New in v2.0!)

Before running production imports, set up your configuration:

### Method 1: Config File (Recommended)
```bash
# Copy template and edit with your settings (cross-platform)
# Unix / macOS:
cp config.template.py config.py
# Windows (cmd.exe):
:: copy config.template.py config.py
# Windows (PowerShell):
Copy-Item -Path .\config.template.py -Destination .\config.py

# Edit the file with your preferred editor (example):
# Windows: notepad config.py
# Unix: nano config.py

# Verify configuration loads
py -3 -c "from lib.config import Config; print(Config())"
```

### Method 2: Environment Variables
```bash
# Linux/Mac
export LIDARR_BASE_URL="http://192.168.1.225:8686"
export LIDARR_API_KEY="your-api-key"
export ROOT_FOLDER_PATH="/media/Music"

# Windows PowerShell
$env:LIDARR_BASE_URL="http://192.168.1.225:8686"
$env:LIDARR_API_KEY="your-api-key"
$env:ROOT_FOLDER_PATH="T:\\Music"
```

See `UNIVERSAL_PARSER.md` or the project `README.md` for detailed setup/quickstart instructions.

---

## 📏 **Controlling Volume**

### `--max-items N`
Limit processing to first N items - essential for production runs!

```bash
# Test with small batch first
py -3 add_albums_to_lidarr.py albums.csv --max-items 50

# Process in chunks of 500
py -3 add_albums_to_lidarr.py albums.csv --max-items 500

# Daily processing quota
py -3 add_albums_to_lidarr.py albums.csv --max-items 200 --skip-completed
```

**💡 Tip**: Start with 50-100 items for new datasets to catch issues early.

## 🎯 **Smart Filtering**

### `--no-skip-completed`
Process ALL items including completed ones (default behavior skips completed)

```bash
# Process everything including previously completed items
py -3 add_albums_to_lidarr.py albums.csv --no-skip-completed

# Daily processing quota (skips completed by default)
py -3 add_albums_to_lidarr.py albums.csv --max-items 200
```

### `--skip-existing` 
Skip artists already in Lidarr (faster processing)

```bash
# Quick run - only new artists
py -3 add_albums_to_lidarr.py albums.csv --skip-existing --max-items 200

# Fast weekend processing
py -3 add_albums_to_lidarr.py albums.csv --skip-existing --no-batch-pause
```

### `--status failed`
Use `--status failed` to process only items that are retryable (replaces the older `--only-failures` flag).

```bash
# Retry after fixing connection issues
py -3 add_albums_to_lidarr.py albums.csv --status failed

# Focus on temporary failures only
py -3 add_albums_to_lidarr.py albums.csv --status failed --max-items 50
```

## ⚡ **Performance Tuning**

### Batch Processing
Control API load and processing speed

```bash
# Conservative (default): 10 items, 10s pause
py -3 add_albums_to_lidarr.py albums.csv --max-items 100

# Faster: larger batches, shorter pauses  
py -3 add_albums_to_lidarr.py albums.csv --batch-size 25 --max-items 200

# Maximum speed (use carefully!)
py -3 add_albums_to_lidarr.py albums.csv --no-batch-pause --skip-existing
```

### Progress Monitoring

```bash
# More frequent progress updates for large runs
py -3 add_albums_to_lidarr.py albums.csv --progress-interval 25 --max-items 1000

# Less frequent for smaller runs
py -3 add_albums_to_lidarr.py albums.csv --progress-interval 100
```

## 📝 **Logging & Debugging**

### `--log-file filename`
Save detailed logs for troubleshooting

```bash
# Production run with logging
py -3 add_albums_to_lidarr.py albums.csv --max-items 500 --log-file "$(date +%Y%m%d)_import.log"

# Retry run with separate log
py -3 add_albums_to_lidarr.py albums.csv --status failed --log-file retry_$(date +%Y%m%d).log

# Weekly import with timestamped log
py -3 add_albums_to_lidarr.py albums.csv --skip-completed --max-items 300 --log-file "weekly_$(date +%Y%m%d_%H%M).log"
```

## 🎯 **Recommended Production Workflows**

### 🥇 **First-Time Import** (Large Dataset)
```bash
# 1. Test small batch
py -3 add_albums_to_lidarr.py albums.csv --dry-run --max-items 10

# 2. Start with conservative run
py -3 add_albums_to_lidarr.py albums.csv --max-items 100 --log-file initial.log

# 3. Continue in larger batches (completed items automatically skipped)
py -3 add_albums_to_lidarr.py albums.csv --max-items 500 --log-file batch1.log
py -3 add_albums_to_lidarr.py albums.csv --max-items 500 --log-file batch2.log
```

### 🔄 **Daily Maintenance**
```bash
# Quick daily run - only new/failed items (default behavior)
py -3 add_albums_to_lidarr.py albums.csv --max-items 200 --log-file daily_$(date +%Y%m%d).log
```

### ⚡ **Fast Weekend Processing**
```bash
# High-speed run for large backlogs
py -3 add_albums_to_lidarr.py albums.csv --skip-existing --no-batch-pause --max-items 1000 --log-file weekend.log
```

### 🔧 **Retry Failed Items**
```bash
# Focus on failures after fixing issues
py -3 add_albums_to_lidarr.py albums.csv --status failed --max-items 100 --log-file retry.log
```

### 📊 **Testing New Data**
```bash
# Safe testing with new CSV files
py -3 add_albums_to_lidarr.py new_albums.csv --dry-run --max-items 20
py -3 add_albums_to_lidarr.py new_albums.csv --max-items 50 --log-file test_new.log
```

## ⚠️ **Production Safety Tips**

1. **Always start small**: Use `--max-items 50` for new datasets
2. **Use logging**: Always use `--log-file` for production runs
3. **Monitor your API**: Watch Lidarr logs during runs
4. **Resume safely**: Default behavior skips completed items automatically
5. **Test first**: Use `--dry-run` when unsure

## 📈 **Performance Guidelines**

| Dataset Size | Recommended Flags | Expected Time |
|--------------|-------------------|---------------|
| < 100 items | `--max-items 100` | 5-10 minutes |
| 100-500 items | `--batch-size 20 --max-items 500` | 30-60 minutes |
| 500+ items | `--max-items 500` | Process in chunks |
| Retry run | `--status failed --max-items 100` | 10-30 minutes |
| Maintenance | `--skip-existing --max-items 200` | 5-15 minutes |

## 🚀 **Example Production Commands**

```bash
# Monday: Process weekend discoveries (conservative)
py -3 add_albums_to_lidarr.py weekend_finds.csv --max-items 100 --log-file monday.log

# Wednesday: Continue large import (completed items automatically skipped)  
py -3 add_albums_to_lidarr.py large_import.csv --max-items 300 --log-file wed.log

# Friday: Fast processing of curated list (aggressive)
py -3 add_albums_to_lidarr.py priority.csv --skip-existing --no-batch-pause --max-items 200

# Sunday: Retry anything that failed during the week
py -3 add_albums_to_lidarr.py weekly.csv --status failed --log-file sunday_retry.log
```

---

<!-- End: content from PRODUCTION_GUIDE.md -->


---

<!-- Begin: content from USAGE_GUIDE.md -->

# Usage Guide - Lidarr Music Importer

**Version 2.0** - Updated for new modular architecture

This guide covers common usage scenarios for the Lidarr Music Importer toolkit.

## 🚀 Getting Started

### 1. First-Time Setup (Updated for v2.0!)

```bash
# Navigate to the project directory
cd lidarr-music-importer

# Copy configuration template
cp config.template.py config.py

# Edit configuration with your settings
# Windows: notepad config.py
# Unix: nano config.py
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
py -3 -c "from lib.config import Config; c = Config(); print(c)"
```

### 3. Run Your First Import
```bash
# Test with example data (dry run)
py -3 add_albums_to_lidarr.py ../examples/example_albums.csv --dry-run

# If test looks good, run for real
py -3 add_albums_to_lidarr.py ../examples/example_albums.csv
```

## 📊 Working with Spotify Data
### Processing Spotify Export

If you have Spotify data, use the parsing script first:

```bash
# Process Spotify liked songs export
py -3 parse_spotify_for_lidarr.py /path/to/liked.csv

# This creates: filtered_artist_album_pairs.csv

# Import the processed data
py -3 add_albums_to_lidarr.py filtered_artist_album_pairs.csv
```

## 🔄 Managing Large Imports

### Batch Processing Strategy
For large datasets (500+ albums):

```bash
# Start with a small test
py -3 add_albums_to_lidarr.py large_dataset.csv --dry-run --max-items 10

# Process in smaller batches
py -3 add_albums_to_lidarr.py large_dataset.csv --batch-size 20

# Skip pauses for faster processing (use carefully)
py -3 add_albums_to_lidarr.py large_dataset.csv --no-batch-pause --batch-size 50
```

### Handling Interruptions

```bash
# If import gets interrupted, resume from where you left off (default behavior)
py -3 add_albums_to_lidarr.py your_data.csv

# Check progress by looking at status column in CSV
```

### Monitoring Progress

```bash
# Check how many items have each status
grep -c "completed" your_data.csv
grep -c "failed" your_data.csv
grep -c "refresh_triggered" your_data.csv
```

## 🛠️ Troubleshooting Workflows

### When Albums Don't Appear

Many albums need metadata refresh after adding the artist:

```bash
# Run import normally
py -3 add_albums_to_lidarr.py your_data.csv

# Wait 10-15 minutes for Lidarr to refresh metadata
# Then run again to catch albums that are now available
py -3 add_albums_to_lidarr.py your_data.csv --skip-completed
```

### Debugging API Issues

```bash
# Test Lidarr connection
py -3 test_lidarr_connection.py

# Run with debug logging (edit script to set DEBUG level)
py -3 add_albums_to_lidarr.py problem_albums.csv --max-items 5

# Check Lidarr logs for API errors
# Settings -> General -> Log Files
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

---

<!-- End: content from USAGE_GUIDE.md -->

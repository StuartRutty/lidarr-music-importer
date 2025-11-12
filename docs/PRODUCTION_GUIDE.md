# 🚀 Production Flags Guide - Lidarr Music Importer

**Version 2.0** - Updated for new configuration system

This guide covers the best command-line flags for different production scenarios with the Lidarr Music Importer.

---

## ⚙️ Initial Setup (New in v2.0!)

Before running production imports, set up your configuration:

### Method 1: Config File (Recommended)
```bash
# Copy template and edit with your settings
cp config_template.py config.py
nano config.py  # or use your editor

# Verify configuration loads
python -c "from lib.config import Config; print(Config())"
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
$env:ROOT_FOLDER_PATH="T:\Music"
```

**See [QUICKSTART_REFACTORING.md](../QUICKSTART_REFACTORING.md) for detailed setup instructions.**

---

## 📏 **Controlling Volume**

### `--max-items N`
Limit processing to first N items - essential for production runs!

```bash
# Test with small batch first
python add_albums_to_lidarr.py albums.csv --max-items 50

# Process in chunks of 500
python add_albums_to_lidarr.py albums.csv --max-items 500

# Daily processing quota
python add_albums_to_lidarr.py albums.csv --max-items 200 --skip-completed
```

**💡 Tip**: Start with 50-100 items for new datasets to catch issues early.

## 🎯 **Smart Filtering**

### `--no-skip-completed`
Process ALL items including completed ones (default behavior skips completed)

```bash
# Process everything including previously completed items
python add_albums_to_lidarr.py albums.csv --no-skip-completed

# Daily processing quota (skips completed by default)
python add_albums_to_lidarr.py albums.csv --max-items 200
```

**💡 Tip**: Default behavior skips completed items. Use `--no-skip-completed` only when you need to reprocess everything.

### `--skip-existing` 
Skip artists already in Lidarr (faster processing)

```bash
# Quick run - only new artists
python add_albums_to_lidarr.py albums.csv --skip-existing --max-items 200

# Fast weekend processing
python add_albums_to_lidarr.py albums.csv --skip-existing --no-batch-pause
```

### `--status failed`
Use `--status failed` to process only items that are retryable (replaces the older `--only-failures` flag).

```bash
# Retry after fixing connection issues
python add_albums_to_lidarr.py albums.csv --status failed

# Focus on temporary failures only
python add_albums_to_lidarr.py albums.csv --status failed --max-items 50
```

## ⚡ **Performance Tuning**

### Batch Processing
Control API load and processing speed

```bash
# Conservative (default): 10 items, 10s pause
python add_albums_to_lidarr.py albums.csv --max-items 100

# Faster: larger batches, shorter pauses  
python add_albums_to_lidarr.py albums.csv --batch-size 25 --max-items 200

# Maximum speed (use carefully!)
python add_albums_to_lidarr.py albums.csv --no-batch-pause --skip-existing
```

### Progress Monitoring

```bash
# More frequent progress updates for large runs
python add_albums_to_lidarr.py albums.csv --progress-interval 25 --max-items 1000

# Less frequent for smaller runs
python add_albums_to_lidarr.py albums.csv --progress-interval 100
```

## 📝 **Logging & Debugging**

### `--log-file filename`
Save detailed logs for troubleshooting

```bash
# Production run with logging
python add_albums_to_lidarr.py albums.csv --max-items 500 --log-file "$(date +%Y%m%d)_import.log"

# Retry run with separate log
python add_albums_to_lidarr.py albums.csv --status failed --log-file retry_$(date +%Y%m%d).log

# Weekly import with timestamped log
python add_albums_to_lidarr.py albums.csv --skip-completed --max-items 300 --log-file "weekly_$(date +%Y%m%d_%H%M).log"
```

## 🎯 **Recommended Production Workflows**

### 🥇 **First-Time Import** (Large Dataset)
```bash
# 1. Test small batch
python add_albums_to_lidarr.py albums.csv --dry-run --max-items 10

# 2. Start with conservative run
python add_albums_to_lidarr.py albums.csv --max-items 100 --log-file initial.log

# 3. Continue in larger batches (completed items automatically skipped)
python add_albums_to_lidarr.py albums.csv --max-items 500 --log-file batch1.log
python add_albums_to_lidarr.py albums.csv --max-items 500 --log-file batch2.log
```

### 🔄 **Daily Maintenance**
```bash
# Quick daily run - only new/failed items (default behavior)
python add_albums_to_lidarr.py albums.csv --max-items 200 --log-file daily_$(date +%Y%m%d).log
```

### ⚡ **Fast Weekend Processing**
```bash
# High-speed run for large backlogs
python add_albums_to_lidarr.py albums.csv --skip-existing --no-batch-pause --max-items 1000 --log-file weekend.log
```

### 🔧 **Retry Failed Items**
```bash
# Focus on failures after fixing issues
python add_albums_to_lidarr.py albums.csv --status failed --max-items 100 --log-file retry.log
```

### 📊 **Testing New Data**
```bash
# Safe testing with new CSV files
python add_albums_to_lidarr.py new_albums.csv --dry-run --max-items 20
python add_albums_to_lidarr.py new_albums.csv --max-items 50 --log-file test_new.log
```

## ⚠️ **Production Safety Tips**

1. **Always start small**: Use `--max-items 50` for new datasets
2. **Use logging**: Always use `--log-file` for production runs
3. **Monitor your API**: Watch Lidarr logs during runs
5. **Resume safely**: Default behavior skips completed items automatically
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
python add_albums_to_lidarr.py weekend_finds.csv --max-items 100 --log-file monday.log

# Wednesday: Continue large import (completed items automatically skipped)  
python add_albums_to_lidarr.py large_import.csv --max-items 300 --log-file wed.log

# Friday: Fast processing of curated list (aggressive)
python add_albums_to_lidarr.py priority.csv --skip-existing --no-batch-pause --max-items 200

# Sunday: Retry anything that failed during the week
python add_albums_to_lidarr.py weekly.csv --status failed --log-file sunday_retry.log
```

---

**💡 Pro Tip**: Create shell aliases for common patterns:

```bash
# Add to your .bashrc / PowerShell profile
# Testing & Development
alias lidarr-test-code="pytest -v"
alias lidarr-test-code-cov="pytest --cov=lib --cov-report=html --cov-report=term"
alias lidarr-test-code-fast="pytest -x"

# Script Testing & Production
alias lidarr-test="python add_albums_to_lidarr.py --dry-run --max-items 10"
alias lidarr-daily="python add_albums_to_lidarr.py --max-items 200"
alias lidarr-retry="python add_albums_to_lidarr.py --status failed --max-items 100"
alias lidarr-batch="python add_albums_to_lidarr.py --max-items 200 --batch-size 25 --log-file lidarr_$(date +%H%M_%Y%m%d).log"
```

```powershell
# For PowerShell users, add to your $PROFILE:
# Testing & Development (pytest)
function lidarr-test-code { 
    pytest -v 
}
function lidarr-test-code-cov { 
    pytest --cov=lib --cov-report=html --cov-report=term 
}
function lidarr-test-code-fast { 
    pytest -x  # Stop at first failure
}
function lidarr-test-code-unit { 
    pytest tests/test_text_utils.py -v  # Run specific test file
}

# Script Testing & Production
function lidarr-test { 
    python add_albums_to_lidarr.py $args --dry-run --max-items 10 
}
function lidarr-daily { 
    python add_albums_to_lidarr.py $args --max-items 200 
}
    function lidarr-retry { 
    python add_albums_to_lidarr.py $args --status failed --max-items 100 
}
function lidarr-batch { 
    $timestamp = Get-Date -Format "HHmm_yyyyMMdd"
    python add_albums_to_lidarr.py $args --max-items 200 --batch-size 25 --log-file "lidarr_$timestamp.log"
}
```

**🔧 PowerShell Setup Instructions:**
1. **Enable Scripts**: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
2. **Edit Profile**: `notepad $PROFILE` and add the functions above
3. **Reload Profile**: `. $PROFILE` 
4. **Functions Available**: Every PowerShell session will now have these commands

**Usage Examples:**
```bash
# Linux/macOS - Testing & Development
lidarr-test-code           # Run all unit tests
lidarr-test-code-cov       # Run tests with coverage
lidarr-batch albums.csv    # Production script run

# PowerShell - Testing & Development
lidarr-test-code           # Run all 89 unit tests
lidarr-test-code-cov       # Run tests with coverage report
lidarr-test-code-fast      # Stop at first failure
lidarr-test-code-unit      # Run specific test module

# PowerShell - Script Testing & Production
lidarr-test albums.csv     # Test 10 items (dry-run)
lidarr-daily albums.csv    # Process 200 items  
lidarr-retry albums.csv    # Retry failures only
lidarr-batch albums.csv    # 200 items + timestamped log
```

**💡 PowerShell Setup & MusicBrainz Troubleshooting**: 

**🔧 Making Functions Permanent:**
1. **Create/Edit Profile**: Run `notepad $PROFILE` to open your PowerShell profile
2. **Add Functions**: Copy the functions above and save the file
3. **Reload Profile**: Run `. $PROFILE` or restart PowerShell
4. **Test**: Functions will now be available in every PowerShell session

**🚫 MusicBrainz Connection Issues:**
If you see "⚠️ No MusicBrainz data" messages:

1. **VPN Issues**: MusicBrainz blocks some VPN IPs
   ```powershell
   # Test MusicBrainz connectivity
   Invoke-WebRequest "https://musicbrainz.org/ws/2/artist/?query=kanye+west&fmt=json" -UseBasicParsing
   ```

2. **Disable MusicBrainz Temporarily**: Edit the script configuration
   ```python
   USE_MUSICBRAINZ = False  # Set to False to skip MusicBrainz lookups
   ```

3. **Check Rate Limiting**: Increase delays in configuration
   ```python
   MUSICBRAINZ_DELAY = 3.0  # Increase from 2.0 to 3.0 seconds
   ```

**Correct PowerShell function:**
```powershell
function lidarr-batch {
    $timestamp = Get-Date -Format "HHmm_yyyyMMdd"
    python add_albums_to_lidarr.py $args --max-items 200 --batch-size 25 --log-file "lidarr_$timestamp.log"
}
```

```

This creates log files like: `lidarr_1430_20251109.log` (2:30 PM on Nov 9, 2025)

---

## 📚 Additional Resources

- **Configuration Guide**: [QUICKSTART_REFACTORING.md](../QUICKSTART_REFACTORING.md)
- **Refactoring Details**: [REFACTORING.md](../REFACTORING.md)
- **Status Codes**: [STATUS_CODES.md](../STATUS_CODES.md)
- **General Usage**: [USAGE_GUIDE.md](USAGE_GUIDE.md)

## 🆕 What's New in v2.0?

- ✅ **Configuration Management**: Use `config.py` or environment variables
- ✅ **Modular Architecture**: Core functionality in reusable `lib/` modules  
- ✅ **Better Security**: API keys no longer in source code
- ✅ **Same CLI**: All existing commands work as before

**Migrating from v1.x?** See [QUICKSTART_REFACTORING.md](../QUICKSTART_REFACTORING.md)

# Lidarr Music Importer

**MusicBrainz-powered album import tool for targeted Lidarr music library building**

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Lidarr](https://img.shields.io/badge/lidarr-compatible-orange.svg)](https://lidarr.audio/)

Import specific albums into Lidarr using MusicBrainz metadata for precise matching. Perfect for converting Spotify playlists or curated album lists into monitored Lidarr collections.

---

## 🔥 Recent Updates

**Version 2.1 - Universal Parser (November 2025)** 🆕
- ✨ **Universal Parser**: Auto-detects and parses multiple input formats (Spotify CSV, manual lists, etc.)
- 🔍 **Fuzzy Deduplication**: Uses rapidfuzz to intelligently merge near-duplicate entries
- 🧹 **Smart Normalization**: Cleans artist/album names with configurable options
- 📊 **Multiple Format Support**: Handles CSV, TSV, text files with various formats

**Version 2.0 Refactoring (November 2025)**
- ✅ **Modular Architecture**: Core functionality extracted to reusable `lib/` modules
- ✅ **Configuration Management**: Support for `config.py` and environment variables
- ✅ **Security**: No more hardcoded API keys in source code
- ✅ **Improved MusicBrainz Client**: Better rate limiting and error handling

**See [QUICKSTART_REFACTORING.md](QUICKSTART_REFACTORING.md) for migration guide.**

---

## 🚀 Quick Start

### Option 1: Using Universal Parser (Recommended for new users)

```bash
# 1. Parse your data (auto-detects format)
cd scripts
python universal_parser.py your_music_list.txt

# 2. Import to Lidarr
python add_albums_to_lidarr.py albums.csv
```

Note: The universal parser performs MusicBrainz enrichment by default and writes `mb_artist_id` and `mb_release_id` to the output CSV. The import script now expects an enriched CSV (or explicit MB IDs per row) and does not call MusicBrainz itself. To skip enrichment (not recommended unless you provide MB IDs manually), use:

```bash
python universal_parser.py your_music_list.txt --no-enrich-musicbrainz
```

Supported input formats:
- **Spotify CSV exports** (filtered automatically)
- **Simple CSV** (artist,album or album,artist)
- **Text files** (Artist - Album or Album by Artist)
- **Tab-separated** values

📖 See [UNIVERSAL_PARSER_QUICKSTART.md](scripts/UNIVERSAL_PARSER_QUICKSTART.md) for detailed examples.

### Option 2: Direct CSV Import

```bash
# 1. Navigate to scripts directory
cd scripts

# 2. Test with sample items
python add_albums_to_lidarr.py albums.csv --dry-run --max-items 3

# 3. Run full import (automatically skips completed items)
python add_albums_to_lidarr.py albums.csv

# 4. Process ALL items including completed ones
python add_albums_to_lidarr.py albums.csv --no-skip-completed

# 5. Retry only failed items
python add_albums_to_lidarr.py albums.csv --only-failures
```

### 🎯 PowerShell Quick Functions
For frequent users, set up these convenient shortcuts:
```powershell
# Testing & Development
lidarr-test-code          # Run pytest unit tests (89 tests)
lidarr-test-code-cov      # Run tests with coverage report

# Script Testing & Production
lidarr-test albums.csv    # Test 10 items (dry-run)
lidarr-quick albums.      # Process 25 items
lidarr-batch albums.csv   # Process 200 items with timestamped logs
lidarr-retry albums.csv   # Retry only failures
lidarr-daily albums.csv   # Daily maintenance run
```
*See [PRODUCTION_GUIDE.md](docs/PRODUCTION_GUIDE.md) for setup instructions.*
# Lidarr Music Importer — concise overview

Small, testable tools to convert album lists into Lidarr imports using MusicBrainz metadata.

Goals:
- Parse common input formats (Spotify CSV, simple CSV, text) into an enriched CSV.
- Normalize and fuzzy-match artist/album titles.
- Add albums to Lidarr via its API with resumable status tracking.

Requirements
- Python 3.7+
- Install dependencies: `pip install -r requirements.txt`

Quick setup (Windows cmd)
1. Create a venv and activate it:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

2. Install requirements:

```cmd
pip install -r requirements.txt
```

3. Create local configuration from the template and edit values:

```cmd
copy config.template.py config.py
rem (edit config.py and set LIDARR_BASE_URL and LIDARR_API_KEY)
```

Usage (simple)
- Parse input to CSV (auto-detect):

```cmd
python scripts\universal_parser.py my_list.txt
```

- Dry-run import of the produced CSV:

```cmd
python scripts\add_albums_to_lidarr.py albums.csv --dry-run --max-items 10
```

- Full import:

```cmd
python scripts\add_albums_to_lidarr.py albums.csv
```

Testing
- Run the test suite:

```cmd
pytest -q
```

Notes
- `config.py` is ignored by `.gitignore`. Do not commit secrets.
- An interactive MusicBrainz demo was moved to `scripts/mb_search_enhanced_demo.py` (not collected by tests).
- Use `--dry-run` and `--max-items` while testing with a live Lidarr instance.

Contributing & CI
- Add tests for new functionality. A basic CI workflow that runs `pytest` is recommended before pushing.



## 📝 Requirements

- Python 3.7+
- Lidarr v2+ with API access
- Required packages: `requests`, `tqdm` (install with `pip install -r requirements.txt`)
- Network access to Lidarr instance
- CSV data with artist/album pairs
- **MusicBrainz**: For comprehensive music metadata
- **Spotify**: For music discovery and export capabilities

---

**Note**: This tool is designed to work with legally obtained music metadata and requires proper Lidarr setup. Ensure you comply with all applicable terms of service and copyright laws.

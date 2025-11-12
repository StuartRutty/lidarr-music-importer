# Lidarr Music Importer

Small, testable tools to convert album lists into Lidarr imports using MusicBrainz metadata.

What this repo provides
- `scripts/` — user-facing Python scripts (parsers and importer).
- `lib/` — reusable modules (clients, CSV helpers, utilities).
- `examples/` — small sample input files (`sample_albums_simple.csv`, `sample_spotify.csv`, `sample_text_list.txt`).
- `tests/` — unit tests run by CI.

Quick requirements
- Python 3.7+
- Install dependencies:

```cmd
py -3 -m pip install -r requirements.txt
```

Setup (local)
1. Create and activate a virtual environment (Windows):

```cmd
py -3 -m venv .venv
.venv\Scripts\activate
```

2. Create `config.py` from the template and add your Lidarr settings:

```cmd
copy config.template.py config.py
rem Edit config.py: set LIDARR_BASE_URL and LIDARR_API_KEY
```

Usage (examples)
- Parse an input file (auto-detect format) and write an enriched CSV:

```cmd
py -3 scripts\universal_parser.py examples\sample_spotify.csv
```

- Dry-run import (test without changing Lidarr):

```cmd
py -3 scripts\add_albums_to_lidarr.py albums.csv --dry-run --max-items 10
```

- Full import:

```cmd
py -3 scripts\add_albums_to_lidarr.py albums.csv
```

Testing
- Run unit tests locally:

```cmd
py -3 -m pytest -q
```

CI
- A GitHub Actions workflow is included at `.github/workflows/ci.yml` to run tests on push/PR.

Notes
- `config.py` is intentionally gitignored — do not commit secrets. Use environment variables or repository secrets for CI.
- The interactive MusicBrainz demo was moved to `scripts/mb_search_enhanced_demo.py` and is not collected by tests.
- Examples live in `examples/`; avoid committing large data files in `scripts/`.

Note about Spotify CSVs
- The Spotify-style CSVs used during development (and recommended for users) were generated with Exportify: the project repo is https://github.com/watsonbox/exportify and the browser-based web UI is available at https://exportify.app/.

Contributing
- Add tests for new features and keep changes small. Run `pytest` locally before opening a PR.

License & legal
- This project uses music metadata from third parties (MusicBrainz, Spotify). Ensure you follow each service's terms of use when using this tool.

Configuration and environment variables
-------------------------------------

Where configuration is read from:

- `config.py` (recommended): copy `config.template.py` to `config.py` and edit values. This file is gitignored and is the primary place to store local settings such as `LIDARR_BASE_URL` and `LIDARR_API_KEY`.
- Environment variables (fallback): if `config.py` is not present, the code will read configuration from environment variables.

Key variables you may want to set (either in `config.py` or as env vars):

- Lidarr credentials:
	- `LIDARR_BASE_URL` (e.g. `http://localhost:8686`)
	- `LIDARR_API_KEY` (your Lidarr API key)

- MusicBrainz / client identity (required by MusicBrainz TOS):
	- In `config.py` set `MUSICBRAINZ_USER_AGENT = {"app_name": "...", "version": "...", "contact": "your.email@example.com"}`.
	- As environment variables you can set `MB_APP_NAME`, `MB_VERSION` and `MB_CONTACT` (the code will use these when `config.py` is absent).

Notes and recommendations:

- The MusicBrainz contact email is used in the HTTP User-Agent header and should point to an address where you can be contacted if the MusicBrainz team needs to reach you about API usage. Please update the placeholder `your.email@example.com` in `config.template.py` / `config.py` or set `MB_CONTACT` in your environment.
- The repository's `.gitignore` includes `.env` and `config.py`; if you keep secrets in a `.env` file, make sure it remains untracked. CI should use repository secrets instead of committing credentials.
- Example (Windows cmd) to create a `config.py` from the template and edit the MusicBrainz contact:

```cmd
copy config.template.py config.py
rem open config.py in an editor and update MUSICBRAINZ_USER_AGENT['contact'] and LIDARR_API_KEY
```

If you'd like, I can also add a short checklist and sample `.env` example (gitignored) to the repo to make onboarding easier.

Parser behavior note
--------------------

The parser applies `--artist`, `--album`, `--max-items`, `--min-artist-songs` and `--min-album-songs` filters during parsing (before MusicBrainz lookups) to avoid unnecessary API requests. Use these flags to limit which rows get enriched.


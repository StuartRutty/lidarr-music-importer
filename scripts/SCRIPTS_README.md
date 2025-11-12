# scripts/ — purpose and how to use

This folder contains the user-facing Python scripts for parsing input lists and importing albums into Lidarr. It intentionally does NOT include generated executable files (those are ignored).

Tracked scripts

- `add_albums_to_lidarr.py` — main importer that reads an enriched CSV and adds albums to a Lidarr instance.
- `universal_parser.py` — auto-detects input formats (Spotify CSV, simple CSV, text) and writes an enriched CSV with MusicBrainz IDs by default.
-- `parse_spotify_for_lidarr.py` — helper to convert a Spotify export to a simple CSV (legacy/kept for backward compatibility).
- `clean_albums.py` — CSV cleaning utilities used during preprocessing.
- `normalize_album_titles.py` — album title normalizer utilities (helper script).
- `fix_musicbrainz.py` — utilities to patch or correct MusicBrainz IDs in CSVs.
- `restore_album_titles.py` — helper to roll back title normalization when needed.
- `mb_search_enhanced_demo.py` — interactive demo for MusicBrainz enhanced search (kept as a demo; not run by tests).

Samples and examples

- See `examples/sample_albums_simple.csv` (artist,album)
- See `examples/sample_spotify.csv` (mock Spotify export columns)
- See `examples/sample_text_list.txt` (lines in the format `Artist - Album`)

Note: For exporting Spotify playlists to CSV we recommend Exportify — the web UI is at https://exportify.app/ and the project repo is https://github.com/watsonbox/exportify.

Quick usage (examples)

1. Parse an input file (auto-detect format):

```cmd
py -3 scripts\universal_parser.py examples\sample_spotify.csv
```

2. Dry-run an import (safe test against your Lidarr instance):

```cmd
py -3 scripts\add_albums_to_lidarr.py albums.csv --dry-run --max-items 5
```

Notes

- `config.py` must exist and contain valid `LIDARR_BASE_URL` and `LIDARR_API_KEY` for actual imports. Use `config.template.py` to create `config.py`.
- The repo `.gitignore` excludes `scripts/*.exe` and `scripts/albums.csv` so generated files are not tracked.

If you'd like, I can add small command examples for each script or a checklist for testing against a local Lidarr instance.

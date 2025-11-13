# Web UI Quickstart (Flask prototype)

This quickstart describes the simple Flask-based web UI scaffold added to the repository.

Files created:
- `webui/app.py` — Minimal Flask app with upload, preview, process, and download endpoints.
- `webui/requirements-webui.txt` — Python dependencies for the web UI (`Flask`, `python-dotenv`).
- `webui/templates/index.html` — Upload / sample selection UI.
- `webui/templates/preview.html` — Preview cleaned rows and process to a downloadable CSV.

Run locally (Windows cmd.exe):

```cmd
py -3 -m pip install -r webui\requirements-webui.txt
py -3 webui\app.py
```

Open http://127.0.0.1:5000/ in your browser.

Data flow (UI):
- Input: user uploads a CSV or selects a sample from `examples/`.
- Server: uses `lib/csv_handler.CSVHandler` to parse rows, `lib/text_utils.clean_csv_input` to clean artist/album values.
- Preview: shows the first N cleaned rows and MB ID columns if present.
- Process: writes a cleaned CSV to `webui/processed/` and provides a download link.

Notes and next steps:
- The prototype intentionally avoids calling external APIs (Lidarr, MusicBrainz) directly from UI actions. That wiring is the next task.
- The UI can be extended with controls to:
  - toggle MusicBrainz enrichment (calls into `scripts/universal_parser.py`/`lib/musicbrainz_client.py`),
  - configure Lidarr host/API key for direct imports, and
  - run the `add_albums_to_lidarr.py` logic (dry-run and real modes).

MusicBrainz enrichment: the UI now includes an "Enrich with MusicBrainz" action on the preview page. It calls `scripts.universal_parser.UniversalParser` to parse the uploaded file, perform MusicBrainz lookup (respecting a user-provided delay, minimum 1.0s), and write an enriched CSV to `webui/processed/` for download.

Async enrichment: the enrichment runs in a background thread and the preview page will poll `/enrich_status` to show live progress and provide a download link when finished. For large inputs, consider running the server in a terminal so you can monitor output.

If you want, I can now wire direct Lidarr import (dry-run first) from the UI, add an asynchronous progress indicator for enrichment, or improve the UI for selecting specific rows to import. Which would you like me to implement next?

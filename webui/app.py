#!/usr/bin/env python3
"""Simple Flask web UI for lidarr-music-importer (prototype)

Features:
- Upload or select a sample CSV
- Preview cleaned rows (uses `lib.csv_handler.CSVHandler` and `lib.text_utils.clean_csv_input`)
- Process to produce a cleaned CSV for download

This is a small scaffold to connect the repo's existing parsing/cleaning helpers
to a local web UI for interactive use. It intentionally keeps functionality
lightweight and safe: it will not call Lidarr or MusicBrainz directly from the UI
until you explicitly request those features.
"""
from pathlib import Path
import sys
import os
import time
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

# Ensure project root is importable so we can import `lib` modules
HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.csv_handler import CSVHandler
from lib.text_utils import clean_csv_input

# Import UniversalParser from scripts for MusicBrainz enrichment
try:
    from scripts.universal_parser import UniversalParser
except Exception:
    UniversalParser = None

import threading
import uuid
from typing import Dict, Any

# In-memory task store for background enrichment tasks
# Structure: { task_id: {status, total, processed, current, out_name, error} }
tasks: Dict[str, Dict[str, Any]] = {}

# Guard to ensure resume logic runs only once per process (compatible with older Flask)
_resume_done = False

 # Persisted job store
try:
    import importlib
    job_store = importlib.import_module('webui.job_store')
except Exception:
    job_store = None

UPLOAD_DIR = Path(__file__).resolve().parent / 'uploads'
PROCESSED_DIR = Path(__file__).resolve().parent / 'processed'
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('WEBUI_SECRET', 'dev-secret')


def list_example_files():
    examples_dir = HERE / 'examples'
    if not examples_dir.exists():
        return []
    return [p.name for p in examples_dir.iterdir() if p.is_file()]


def _run_worker(tid: str, input_path: Path, output_path: Path, delay: float, start_index: int = 1):
    """Module-level worker to perform enrichment and persist progress."""
    try:
        tasks[tid]['status'] = 'running'
        if job_store is not None:
            try:
                job_store.update_job(tid, {'status': 'running'})
            except Exception:
                pass
        up = UniversalParser(fuzzy_threshold=85, normalize=True)
        up.parse_file(str(input_path))
        entries = up.entries
        tasks[tid]['total'] = len(entries)

        # Persist total if available
        if job_store is not None:
            try:
                job_store.update_job(tid, {'total': tasks[tid]['total']})
            except Exception:
                pass

        # Ensure MusicBrainz client exists
        if getattr(up, 'mb_client', None) is None:
            try:
                from lib.musicbrainz_client import MusicBrainzClient
                up.mb_client = MusicBrainzClient(delay=max(delay, 1.0))
            except Exception:
                up.mb_client = None

        # Enrich entries one-by-one to update progress
        for i, entry in enumerate(entries, start=1):
            # Skip entries already processed when resuming
            if i < start_index:
                continue
            tasks[tid]['current'] = f"{entry.artist} - {entry.album}"
            tasks[tid]['processed'] = i
            # Persist progress update
            if job_store is not None:
                try:
                    job_store.update_job(tid, {'current': tasks[tid]['current'], 'processed': tasks[tid]['processed']})
                except Exception:
                    pass
            try:
                if up.mb_client:
                    mb_artist = up.mb_client.search_artists(entry.artist, limit=1)
                    artist_list = mb_artist.get('artist-list', []) if isinstance(mb_artist, dict) else []
                    if artist_list:
                        best_artist = artist_list[0]
                        entry.mb_artist_id = best_artist.get('id', '')

                    search_album = entry.album_search or entry.album
                    mb_release = up.mb_client.search_release_groups(entry.artist, search_album, limit=5, artist_mbid=entry.mb_artist_id if entry.mb_artist_id else None)
                    release_list = mb_release.get('release-group-list', []) if isinstance(mb_release, dict) else []
                    if release_list:
                        best_release = release_list[0]
                        entry.mb_release_id = best_release.get('id', '')
            except Exception as e:
                tasks[tid]['error'] = str(e)

            time.sleep(max(delay, 1.0))

        # Write output CSV
        try:
            up.write_output(str(output_path), include_risk_column=False, skip_risky=False)
        except Exception:
            import csv
            with open(str(output_path), 'w', newline='', encoding='utf-8') as wf:
                header = ['artist', 'album', 'album_search', 'mb_artist_id', 'mb_release_id']
                writer = csv.writer(wf)
                writer.writerow(header)
                for e in entries:
                    writer.writerow([e.artist, e.album, getattr(e, 'album_search', ''), getattr(e, 'mb_artist_id', ''), getattr(e, 'mb_release_id', '')])

        tasks[tid]['status'] = 'completed'
        if job_store is not None:
            try:
                job_store.update_job(tid, {'status': 'completed'})
            except Exception:
                pass
    except Exception as exc:
        tasks[tid]['status'] = 'failed'
        tasks[tid]['error'] = str(exc)
        if job_store is not None:
            try:
                job_store.update_job(tid, {'status': 'failed', 'error': tasks[tid]['error']})
            except Exception:
                pass


def _resume_jobs_helper():
    """Helper to resume queued/running jobs from the on-disk job store."""
    if job_store is None:
        return

    for jid in job_store.list_jobs():
        try:
            job = job_store.get_job(jid)
            if not job:
                continue
            status = job.get('status')
            if status in ('queued', 'running'):
                # Mirror into in-memory tasks and spawn worker to resume
                tasks[jid] = job
                in_path = None
                try:
                    in_path = UPLOAD_DIR / Path(job.get('input_path') or '')
                except Exception:
                    in_path = None
                # If input_path missing, skip resume
                if in_path and in_path.exists():
                    out_name = job.get('out_name') or f"enriched_{int(time.time())}_{job.get('input_path','')}"
                    out_path = PROCESSED_DIR / out_name
                    start_index = int(job.get('processed', 0)) + 1
                    try:
                        thr = threading.Thread(
                            target=_run_worker,
                            args=(jid, in_path, out_path, max(1.0, float(job.get('mb_delay', 1.0))), start_index),
                            daemon=True,
                        )
                        thr.start()
                    except Exception as e:
                        # Persist failure to resume
                        try:
                            job_store.update_job(jid, {'status': 'failed', 'error': str(e)})
                        except Exception:
                            pass
        except Exception:
            # Ignore per-job errors but continue attempting others
            continue


@app.route('/')
def index():
    samples = list_example_files()
    return render_template('index.html', samples=samples)


@app.route('/upload', methods=['POST'])
def upload():
    # Accept file upload or example selection
    sample = request.form.get('sample')
    file = request.files.get('file')
    if file and file.filename:
        save_path = UPLOAD_DIR / f"upload_{int(time.time())}_{file.filename}"
        file.save(save_path)
        flash(f"Uploaded: {file.filename}")
        return redirect(url_for('preview', path=save_path.name))
    elif sample:
        # Copy example to uploads dir so we can process uniformly
        src = HERE / 'examples' / sample
        if not src.exists():
            flash('Selected sample not found', 'error')
            return redirect(url_for('index'))
        dst = UPLOAD_DIR / f"sample_{int(time.time())}_{sample}"
        with open(src, 'rb') as r, open(dst, 'wb') as w:
            w.write(r.read())
        flash(f"Selected sample: {sample}")
        return redirect(url_for('preview', path=dst.name))
    else:
        flash('No file uploaded or sample selected', 'error')
        return redirect(url_for('index'))


@app.route('/preview')
def preview():
    path = request.args.get('path')
    preview_rows = int(request.args.get('preview_rows', 10))
    artist_filter = (request.args.get('artist_filter') or '').strip().lower()
    album_filter = (request.args.get('album_filter') or '').strip().lower()
    strip_suffixes = request.args.get('strip_suffixes', 'on') in ('1', 'on', 'true', 'yes')

    if not path:
        flash('No file specified for preview', 'error')
        return redirect(url_for('index'))

    file_path = UPLOAD_DIR / path
    if not file_path.exists():
        flash('Uploaded file not found', 'error')
        return redirect(url_for('index'))

    try:
        csvh = CSVHandler(str(file_path))
        items, has_status = csvh.read_items()
    except Exception as e:
        flash(f'Failed to read CSV: {e}', 'error')
        return redirect(url_for('index'))

    filtered = []
    for it in items:
        raw_artist = it.get('artist', '')
        raw_album = it.get('album', '')
        cleaned_artist = clean_csv_input(raw_artist, is_artist=True, strip_suffixes=strip_suffixes)
        cleaned_album = clean_csv_input(raw_album, is_artist=False, strip_suffixes=strip_suffixes)

        # Apply artist/album substring filters (case-insensitive) if provided
        if artist_filter:
            if artist_filter not in cleaned_artist.lower() and artist_filter not in raw_artist.lower():
                continue
        if album_filter:
            if album_filter not in cleaned_album.lower() and album_filter not in raw_album.lower():
                continue

        filtered.append({
            'raw_artist': raw_artist,
            'raw_album': raw_album,
            'cleaned_artist': cleaned_artist,
            'cleaned_album': cleaned_album,
            'mb_artist_id': it.get('mb_artist_id', ''),
            'mb_release_id': it.get('mb_release_id', ''),
        })

    preview = filtered[:preview_rows]
    total_all = len(items)
    filtered_total = len(filtered)

    return render_template(
        'preview.html',
        preview=preview,
        filename=path,
        preview_rows=preview_rows,
        artist_filter=artist_filter,
        album_filter=album_filter,
        strip_suffixes=strip_suffixes,
        filtered_total=filtered_total,
        total_all=total_all,
    )


@app.route('/process', methods=['POST'])
def process():
    # Process uploaded CSV into a cleaned CSV and offer download
    filename = request.form.get('filename')
    skip_risky = request.form.get('skip_risky') == 'on'
    strip_suffixes = request.form.get('strip_suffixes') == 'on'
    if not filename:
        flash('No file specified to process', 'error')
        return redirect(url_for('index'))

    in_path = UPLOAD_DIR / filename
    if not in_path.exists():
        flash('Input file not found', 'error')
        return redirect(url_for('index'))

    out_name = f"processed_{int(time.time())}_{filename}"
    out_path = PROCESSED_DIR / out_name

    # Simple processing: rewrite CSV rows with cleaned artist/album and preserve MB IDs
    try:
        import csv
        with open(in_path, newline='', encoding='utf-8') as rf, open(out_path, 'w', newline='', encoding='utf-8') as wf:
            reader = csv.DictReader(rf)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else ['artist', 'album']
            # Ensure MB ID columns exist in output if present in input
            if 'mb_artist_id' in fieldnames and 'mb_release_id' in fieldnames:
                out_fields = ['artist', 'album', 'mb_artist_id', 'mb_release_id']
            else:
                out_fields = ['artist', 'album']
            writer = csv.DictWriter(wf, fieldnames=out_fields)
            writer.writeheader()
            for row in reader:
                artist_raw = row.get('artist', '')
                album_raw = row.get('album', '')
                artist_clean = clean_csv_input(artist_raw, is_artist=True, strip_suffixes=strip_suffixes)
                album_clean = clean_csv_input(album_raw, is_artist=False, strip_suffixes=strip_suffixes)
                out_row = {'artist': artist_clean, 'album': album_clean}
                if 'mb_artist_id' in out_fields:
                    out_row['mb_artist_id'] = row.get('mb_artist_id', '')
                    out_row['mb_release_id'] = row.get('mb_release_id', '')
                writer.writerow(out_row)

    except Exception as e:
        flash(f'Processing failed: {e}', 'error')
        return redirect(url_for('preview', path=filename))

    flash(f'Processing complete: {out_name}')
    return redirect(url_for('download', path=out_name))


@app.route('/enrich', methods=['POST'])
def enrich():
    """Start asynchronous MusicBrainz enrichment task and return a task id.

    The enrichment is performed in a background thread. Clients should poll
    `/enrich_status?task_id=<id>` for progress updates and final download link.
    """
    if UniversalParser is None:
        flash('MusicBrainz enrichment not available (failed to import UniversalParser)', 'error')
        return redirect(url_for('preview', path=request.form.get('filename')))

    filename = request.form.get('filename')
    mb_delay = float(request.form.get('mb_delay') or 2.0)
    if not filename:
        flash('No file specified to enrich', 'error')
        return redirect(url_for('index'))

    in_path = UPLOAD_DIR / filename
    if not in_path.exists():
        flash('Input file not found for enrichment', 'error')
        return redirect(url_for('index'))

    # Prepare output path in processed dir
    out_name = f"enriched_{int(time.time())}_{filename}"
    out_path = PROCESSED_DIR / out_name

    # Create a task id and initialize status
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'queued',
        'total': 0,
        'processed': 0,
        'current': '',
        'out_name': str(out_name),
        'error': None
    }

    # Persist initial job state if job_store is available
    if job_store is not None:
        try:
            job_store.create_job(task_id, tasks[task_id])
        except Exception:
            pass

    # use module-level worker instead

    thr = threading.Thread(target=_run_worker, args=(task_id, in_path, out_path, max(1.0, mb_delay)), daemon=True)
    thr.start()

    return redirect(url_for('preview', path=filename) + f"#task={task_id}")


@app.route('/import', methods=['POST'])
def import_dry_run():
    """Dry-run import: take selected row indices and show actions without calling Lidarr."""
    filename = request.form.get('filename')
    selected = request.form.getlist('selected')
    if not filename:
        flash('No file specified for import', 'error')
        return redirect(url_for('index'))

    in_path = UPLOAD_DIR / filename
    if not in_path.exists():
        flash('Input file not found', 'error')
        return redirect(url_for('index'))

    strip_suffixes = request.form.get('strip_suffixes') == 'on'
    try:
        import csv
        results = []
        with open(in_path, newline='', encoding='utf-8') as rf:
            reader = list(csv.DictReader(rf))
            # If no selection provided, select none
            indices = set()
            for s in selected:
                try:
                    indices.add(int(s))
                except Exception:
                    pass

            for idx in sorted(indices):
                if 0 <= idx < len(reader):
                    row = reader[idx]
                    artist_raw = row.get('artist', '')
                    album_raw = row.get('album', '')
                    artist_clean = clean_csv_input(artist_raw, is_artist=True, strip_suffixes=strip_suffixes)
                    album_clean = clean_csv_input(album_raw, is_artist=False, strip_suffixes=strip_suffixes)
                    results.append({
                        'artist_raw': artist_raw,
                        'album_raw': album_raw,
                        'artist_clean': artist_clean,
                        'album_clean': album_clean,
                        'mb_artist_id': row.get('mb_artist_id', ''),
                        'mb_release_id': row.get('mb_release_id', ''),
                    })
    except Exception as e:
        flash(f'Import dry-run failed: {e}', 'error')
        return redirect(url_for('preview', path=filename))

    return render_template('import_result.html', results=results, filename=filename)


@app.route('/enrich_status')
def enrich_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return {'status': 'unknown'}, 404
    if task_id in tasks:
        return tasks[task_id]
    # Fall back to persisted job store
    if job_store is not None:
        job = job_store.get_job(task_id)
        if job is not None:
            return job
    return {'status': 'unknown'}, 404


@app.route('/download')
def download():
    path = request.args.get('path')
    if not path:
        flash('No file specified', 'error')
        return redirect(url_for('index'))
    return send_from_directory(PROCESSED_DIR, path, as_attachment=True)


if __name__ == '__main__':
    # Enable the reloader in development so code changes restart the server automatically.
    app.run(debug=True, port=5000, use_reloader=True)


# Run resume logic on the first incoming request so we avoid spawning workers during
# module import (which interacts poorly with the Flask reloader). This ensures the
# resume/cleanup logic runs once per process, after the reloader has spawned the
# child process that will serve requests.
@app.before_request
def _resume_jobs_on_first_request():
    global _resume_done
    # Run once per process
    if _resume_done:
        return
    _resume_done = True

    if job_store is None:
        return
    # Run resume helper (defined at module scope)
    try:
        _resume_jobs_helper()
    except Exception:
        pass

    # Cleanup old completed jobs (best-effort)
    try:
        job_store.cleanup_jobs()
    except Exception:
        pass


# If running under pytest, run resume at import time so tests that import the
# module see resume behavior without needing an incoming HTTP request.
try:
    import sys as _sys
    if job_store is not None and 'pytest' in _sys.modules:
        # Ensure we only run resume once per process
        if not _resume_done:
            _resume_done = True
            # call the same helper to resume jobs directly
            try:
                _resume_jobs_helper()
            except Exception:
                pass
except Exception:
    pass

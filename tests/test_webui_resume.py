import sys
import time
import os
import json
import importlib
from pathlib import Path


def test_resume_enrichment_job(tmp_path):
    # Prepare paths
    repo_root = Path(__file__).resolve().parent.parent
    uploads_dir = repo_root / 'webui' / 'uploads'
    processed_dir = repo_root / 'webui' / 'processed'
    jobs_dir = repo_root / 'webui' / 'jobs'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    # Create a small CSV input
    input_name = f'resume_test_{int(time.time())}.csv'
    input_path = uploads_dir / input_name
    input_path.write_text('artist,album\nResume Artist,Resume Album\n', encoding='utf-8')

    # Prepare a fake UniversalParser module before importing webui.app so
    # the resume-on-import logic uses the fake parser (no network).
    module_name = 'scripts.universal_parser'
    fake_mod = type(sys)(module_name)

    class FakeEntry:
        def __init__(self, artist, album):
            self.artist = artist
            self.album = album
            self.album_search = album
            self.mb_artist_id = ''
            self.mb_release_id = ''

    class FakeUniversalParser:
        def __init__(self, fuzzy_threshold=85, normalize=True):
            self.entries = []

        def parse_file(self, path):
            # Read the file to ensure path is valid and create one entry
            self.entries = [FakeEntry('Resume Artist', 'Resume Album')]

        def write_output(self, output_path, include_risk_column=False, skip_risky=False):
            # Write output CSV with the enriched row using csv.writer
            import csv
            with open(output_path, 'w', encoding='utf-8', newline='') as wf:
                writer = csv.writer(wf)
                writer.writerow(['artist', 'album', 'album_search', 'mb_artist_id', 'mb_release_id'])
                for e in self.entries:
                    writer.writerow([e.artist, e.album, getattr(e, 'album_search', ''), getattr(e, 'mb_artist_id', ''), getattr(e, 'mb_release_id', '')])

    fake_mod.UniversalParser = FakeUniversalParser
    sys.modules[module_name] = fake_mod

    # Create a job file directly using the on-disk job store
    # Import job_store
    import webui.job_store as job_store

    task_id = f'test-resume-{int(time.time())}'
    out_name = f'enriched_{int(time.time())}_{input_name}'
    job_data = {
        'status': 'queued',
        'total': 1,
        'processed': 0,
        'current': '',
        'out_name': out_name,
        'error': None,
        'input_path': input_name,
        'mb_delay': 1.0,
    }
    job_store.create_job(task_id, job_data)

    # Ensure webui.app is re-imported so the startup resume logic runs.
    if 'webui.app' in sys.modules:
        del sys.modules['webui.app']
    appmod = importlib.import_module('webui.app')

    # Poll the job file until completed
    start = time.time()
    timeout = 15
    last = None
    while time.time() - start < timeout:
        job = job_store.get_job(task_id)
        if job and job.get('status') == 'completed':
            break
        last = job
        time.sleep(0.5)

    assert job is not None, f'Job file missing, last: {last}'
    assert job.get('status') == 'completed', f'Job did not complete in time, last: {last}'

    # Confirm the processed file was written
    out_path = processed_dir / job.get('out_name')
    assert out_path.exists(), f'Expected output file {out_path} not found'
    txt = out_path.read_text(encoding='utf-8')
    assert 'Resume Artist' in txt

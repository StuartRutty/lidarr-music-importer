import os
import time
import csv
from urllib.parse import urlparse, parse_qs

import pytest


def setup_fake_parser(app_module):
    """Replace UniversalParser in the app module with a fake that doesn't network."""

    class DummyMBClient:
        def search_artists(self, artist, limit=1):
            return {}

        def search_release_groups(self, artist, release, limit=5, artist_mbid=None):
            return {}

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
            self.mb_client = DummyMBClient()

        def parse_file(self, path):
            # Create one fake entry
            self.entries = [FakeEntry('Test Artist', 'Test Album')]

        def write_output(self, output_path, include_risk_column=False, skip_risky=False):
            # Write a small CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as wf:
                writer = csv.writer(wf)
                writer.writerow(['artist', 'album', 'album_search', 'mb_artist_id', 'mb_release_id'])
                for e in self.entries:
                    writer.writerow([e.artist, e.album, e.album_search, e.mb_artist_id, e.mb_release_id])

    app_module.UniversalParser = FakeUniversalParser


@pytest.fixture
def client():
    # Import the Flask app and use its test client
    import webui.app as appmod

    setup_fake_parser(appmod)

    app = appmod.app
    app.testing = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'Upload CSV file' in rv.data


def test_upload_sample_and_preview(client):
    # Use an example sample that exists in the repo
    sample_name = 'example_albums.csv'
    rv = client.post('/upload', data={'sample': sample_name}, follow_redirects=False)
    assert rv.status_code in (302, 303)
    loc = rv.headers['Location']
    assert '/preview' in loc
    qs = urlparse(loc).query
    params = parse_qs(qs)
    assert 'path' in params
    path = params['path'][0]

    # Now GET the preview page
    rv2 = client.get(f'/preview?path={path}')
    assert rv2.status_code == 200
    assert b'Preview' in rv2.data


def test_enrich_background_task(client, tmp_path):
    # Upload sample
    sample_name = 'example_albums.csv'
    rv = client.post('/upload', data={'sample': sample_name}, follow_redirects=False)
    loc = rv.headers['Location']
    qs = urlparse(loc).query
    params = parse_qs(qs)
    path = params['path'][0]

    # Start enrichment (this should spawn a background thread)
    rv2 = client.post('/enrich', data={'filename': path, 'mb_delay': '1.0'}, follow_redirects=False)
    assert rv2.status_code in (302, 303)
    loc2 = rv2.headers['Location']
    # The redirect includes a fragment with task id: /preview?path=...#task=<id>
    assert '#task=' in loc2
    task_id = loc2.split('#task=')[-1]

    # Poll the status endpoint until completed (with timeout)
    start = time.time()
    status = None
    while time.time() - start < 10:
        rv3 = client.get(f'/enrich_status?task_id={task_id}')
        if rv3.status_code == 200:
            data = rv3.get_json()
            status = data.get('status')
            if status == 'completed':
                out_name = data.get('out_name')
                # Confirm the file exists in processed dir
                proc = os.path.join(os.path.dirname(__file__), '..', 'webui', 'processed')
                proc = os.path.abspath(proc)
                out_path = os.path.join(proc, out_name)
                assert os.path.exists(out_path)
                # Basic check of CSV contents
                with open(out_path, 'r', encoding='utf-8') as rf:
                    txt = rf.read()
                    assert 'Test Artist' in txt
                return
        time.sleep(0.5)

    pytest.fail(f'Enrichment task did not complete in time, last status: {status}')

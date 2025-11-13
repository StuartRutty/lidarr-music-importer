import io
import os
import csv
from urllib.parse import urlparse, parse_qs

import pytest


@pytest.fixture
def client():
    import webui.app as appmod
    app = appmod.app
    app.testing = True
    with app.test_client() as client:
        yield client


def test_file_upload_saves_to_uploads(client, tmp_path):
    # Create a simple CSV in memory
    csv_bytes = b"artist,album\nFoo Artist,Bar Album\n"
    data = {
        'file': (io.BytesIO(csv_bytes), 'upload_test.csv')
    }

    rv = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=False)
    assert rv.status_code in (302, 303)
    loc = rv.headers['Location']
    # Location should include /preview?path=<filename>
    assert '/preview' in loc
    qs = urlparse(loc).query
    params = parse_qs(qs)
    assert 'path' in params
    path = params['path'][0]

    uploads_dir = os.path.join(os.path.dirname(__file__), '..', 'webui', 'uploads')
    uploads_dir = os.path.abspath(uploads_dir)
    saved_path = os.path.join(uploads_dir, path)
    assert os.path.exists(saved_path)

    # Verify content matches
    with open(saved_path, 'rb') as f:
        saved = f.read()
        assert saved == csv_bytes


def test_process_writes_processed_csv(client):
    # Upload a CSV sample first
    csv_bytes = b"artist,album\nAlpha, Bravo\n"
    data = {'file': (io.BytesIO(csv_bytes), 'process_test.csv')}
    rv = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=False)
    assert rv.status_code in (302, 303)
    loc = rv.headers['Location']
    qs = urlparse(loc).query
    params = parse_qs(qs)
    path = params['path'][0]

    # Call process to create processed CSV
    rv2 = client.post('/process', data={'filename': path}, follow_redirects=False)
    assert rv2.status_code in (302, 303)
    loc2 = rv2.headers['Location']
    # Should redirect to /download?path=<processed_name>
    assert '/download' in loc2
    qs2 = urlparse(loc2).query
    params2 = parse_qs(qs2)
    assert 'path' in params2
    out_name = params2['path'][0]

    processed_dir = os.path.join(os.path.dirname(__file__), '..', 'webui', 'processed')
    processed_dir = os.path.abspath(processed_dir)
    out_path = os.path.join(processed_dir, out_name)
    assert os.path.exists(out_path)

    # Check CSV contents include cleaned artist/album
    with open(out_path, 'r', encoding='utf-8') as rf:
        txt = rf.read()
        assert 'Alpha' in txt
        assert 'Bravo' in txt

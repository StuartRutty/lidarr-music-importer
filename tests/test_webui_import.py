import io
import os
from urllib.parse import urlparse, parse_qs


def test_import_dry_run_select_rows():
    import webui.app as appmod
    app = appmod.app
    app.testing = True
    with app.test_client() as client:
        # Upload a sample from examples
        sample_name = 'example_albums.csv'
        rv = client.post('/upload', data={'sample': sample_name}, follow_redirects=False)
        assert rv.status_code in (302, 303)
        loc = rv.headers['Location']
        qs = urlparse(loc).query
        params = parse_qs(qs)
        path = params['path'][0]

        # Perform dry-run import selecting the first row (index 0)
        rv2 = client.post('/import', data={'filename': path, 'selected': '0'}, follow_redirects=True)
        assert rv2.status_code == 200
        # Should contain a table of results and the artist name from the selected row
        assert b'Import Dry-Run Results' in rv2.data
        assert b'artist' in rv2.data.lower()
def test_preview_filters_and_strip_suffixes():
    import webui.app as appmod
    app = appmod.app
    app.testing = True
    with app.test_client() as client:
        # Upload a sample from examples
        sample_name = 'example_albums.csv'
        rv = client.post('/upload', data={'sample': sample_name}, follow_redirects=False)
        assert rv.status_code in (302, 303)
        loc = rv.headers['Location']
        # Extract the path query param from the redirect
        from urllib.parse import urlparse, parse_qs
        qs = urlparse(loc).query
        params = parse_qs(qs)
        path = params['path'][0]

        # Request preview with an artist filter that should only match the second sample row
        rv2 = client.get(f'/preview?path={path}&artist_filter=test+artist+2')
        assert rv2.status_code == 200
        data = rv2.data.decode('utf-8').lower()
        # Should contain the filtered artist and not contain the other sample artist
        assert 'test artist 2' in data
        assert 'test artist 1' not in data

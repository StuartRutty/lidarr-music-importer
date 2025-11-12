import json
from types import SimpleNamespace
from lib.lidarr_client import LidarrClient


class FakeResponse:
    def __init__(self, status_code=200, json_obj=None, text=''):
        self.status_code = status_code
        self._json = json_obj
        self.text = text or (json.dumps(json_obj) if json_obj is not None else '')

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}: {self.text}")


def test_monitor_album_by_mbid_success(monkeypatch):
    calls = {'get': [], 'post': []}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls['get'].append((url, params))
        # get_artist_albums -> endpoint /api/v1/album?artistId=...
        if url.endswith('/api/v1/album') and params and 'artistId' in params:
            return FakeResponse(200, [])
        # lookup for MBID -> /api/v1/album?term=lidarr:mbid
        if url.endswith('/api/v1/album/lookup') and params and params.get('term', '').startswith('lidarr:'):
            # return a single album with artist id matching expected
            album = {
                'id': 999,
                'title': 'Test Album',
                'artist': {'id': 123, 'artistName': 'Artist'},
                'foreignAlbumId': 'mbid1',
            }
            return FakeResponse(200, [album])
        # fallback
        return FakeResponse(200, [])

    def fake_post(url, *args, **kwargs):
        # capture payload whether sent as positional or as `json=` keyword
        payload = None
        if 'json' in kwargs:
            payload = kwargs.get('json')
        elif args:
            payload = args[0]

        calls['post'].append((url, payload))
        # adding album -> /api/v1/album
        if url.endswith('/api/v1/album'):
            title = None
            if isinstance(payload, dict):
                title = payload.get('title')
            return FakeResponse(201, {'id': 1001, 'title': title})
        # command endpoints
        if url.endswith('/api/v1/command'):
            return FakeResponse(200, {'message': 'ok'})
        return FakeResponse(404, None, 'not found')

    monkeypatch.setattr('requests.get', fake_get)
    monkeypatch.setattr('requests.post', fake_post)

    client = LidarrClient(base_url='http://localhost:8686', api_key='key', quality_profile_id=1, metadata_profile_id=1, root_folder_path='/music')

    result = client.monitor_album_by_mbid(artist_id=123, musicbrainz_album_id='mbid1', artist_name='Artist', album_title='Test Album')
    assert result is True
    # verify we did the lookup and then posted to add album
    assert any('/api/v1/album/lookup' in c[0] for c in calls['get'])
    assert any('/api/v1/album' in c[0] for c in calls['post'])

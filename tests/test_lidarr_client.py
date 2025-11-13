import requests
import pytest
import responses
import time
from unittest.mock import Mock, patch
from datetime import datetime

from lib.lidarr_client import LidarrClient


class _DummyResp400:
    def __init__(self, text='Already exists'):
        self.status_code = 400
        self.text = text

    def raise_for_status(self):
        err = requests.exceptions.HTTPError()
        err.response = self
        raise err

    def json(self):
        return {"artistName": "Dummy"}


class _DummyResp201:
    def __init__(self, payload=None):
        self.status_code = 201
        self._payload = payload or {"title": "Album1"}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_get_headers_and_repr():
    c = LidarrClient("http://localhost:8686/", "APIKEY", 1, 1, "/music")
    assert c._get_headers() == {"X-Api-Key": "APIKEY"}
    assert "LidarrClient" in repr(c)


def test_add_artist_already_exists(monkeypatch):
    c = LidarrClient("http://localhost:8686/", "K", 1, 1, "/root")

    def fake_post(url, json=None, headers=None, timeout=None):
        return _DummyResp400("Artist already exists")

    monkeypatch.setattr("requests.post", fake_post)

    artist_data = {"artistName": "Test Artist"}
    result = c.add_artist(artist_data, monitor=False, search=False)
    assert result == artist_data


def test_add_album_returns_json_on_201(monkeypatch):
    c = LidarrClient("http://localhost:8686/", "K", 1, 1, "/root")

    def fake_post(url, json=None, headers=None, timeout=None):
        return _DummyResp201({"title": "AlbumX"})

    monkeypatch.setattr("requests.post", fake_post)

    album = {"title": "AlbumX"}
    res = c.add_album(album, monitored=True, search=True)
    assert isinstance(res, dict)
    assert res.get("title") == "AlbumX"


def test_is_album_already_monitored_matches_by_title(monkeypatch):
    c = LidarrClient("http://localhost:8686/", "K", 1, 1, "/root")

    sample_album = {"title": "Some Album", "artist": {"artistName": "The Band"}, "monitored": True}

    monkeypatch.setattr(c, "get_all_albums", lambda: [sample_album])

    matched, album = c.is_album_already_monitored("The Band", "Some Album")
    assert matched is True
    assert album == sample_album


def test_monitor_album_by_mbid_existing_monitored(monkeypatch):
    c = LidarrClient("http://host", "key", 1, 1, "/root")

    # existing album returned by get_artist_albums with matching foreignAlbumId
    existing = {"foreignAlbumId": "mbid1", "monitored": True}
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [existing])

    res = c.monitor_album_by_mbid(123, "mbid1", "Artist", "Title")
    assert res is True


def test_monitor_album_by_mbid_existing_unmonitored_updates(monkeypatch):
    c = LidarrClient("http://host", "key", 1, 1, "/root")

    existing = {"foreignAlbumId": "mbid2", "monitored": False}
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [existing])
    # simulate update_album succeeds
    monkeypatch.setattr(c, "update_album", lambda a: True)

    res = c.monitor_album_by_mbid(5, "mbid2", "Artist", "Title")
    assert res is True


def test_monitor_album_by_mbid_no_lookup_results(monkeypatch):
    c = LidarrClient("http://host", "key", 1, 1, "/root")

    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [])

    # monkeypatch requests.get for lookup to return an object with json() -> []
    class R:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return []

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: R())

    res = c.monitor_album_by_mbid(1, "missing-mbid", "A", "T")
    assert res is False


def test_monitor_album_by_mbid_lookup_name_match_fix(monkeypatch):
    c = LidarrClient("http://host", "key", 1, 1, "/root")

    # no existing albums
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [])

    # simulate lookup returning album with artist id None but name matching
    album_data = {
        "title": "X",
        "artist": {"id": None, "artistName": "The Band", "foreignArtistId": None},
        "foreignAlbumId": "mbid3"
    }

    class R:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return [album_data]

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: R())

    # get_artist_by_id should return the complete artist data used to patch album
    monkeypatch.setattr(c, "get_artist_by_id", lambda a: {"id": 99, "artistName": "The Band"})
    # add_album should return a truthy result
    monkeypatch.setattr(c, "add_album", lambda album, monitored=True, search=True: {"title": "X"})

    res = c.monitor_album_by_mbid(99, "mbid3", "The Band", "X")
    assert res is True


def test_monitor_album_exact_match_and_monitoring(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")

    album = {"title": "Target Album", "monitored": True, "id": 7}
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [album])

    res = c.monitor_album(12, "Target Album", "Artist")
    assert res is True


def test_monitor_album_exact_match_not_monitored_updates_and_search(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")

    album = {"title": "Target Album", "monitored": False, "id": 8}
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [album])
    monkeypatch.setattr(c, "update_album", lambda a: True)
    called = {"search": False}

    def fake_search(aid):
        called["search"] = True

    monkeypatch.setattr(c, "search_for_album", fake_search)

    res = c.monitor_album(12, "Target Album", "Artist")
    assert res is True
    assert called["search"] is True


def test_monitor_album_no_matches_triggers_refresh(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")
    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: [])

    called = {"refreshed": False}
    monkeypatch.setattr(c, "refresh_artist", lambda aid: called.__setitem__("refreshed", True))

    res = c.monitor_album(5, "Nonexistent", "Artist")
    assert res is False
    assert called["refreshed"] is True


def test_unmonitor_all_albums_for_artist(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")

    albums = [
        {"id": 1, "title": "A", "monitored": True},
        {"id": 2, "title": "B", "monitored": False},
        {"id": 3, "title": "C", "monitored": True},
    ]

    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: albums)
    updated = []

    def fake_update(album):
        updated.append(album.get("title"))
        return True

    monkeypatch.setattr(c, "update_album", fake_update)

    res = c.unmonitor_all_albums_for_artist(10, "Artist")
    assert res is True
    # Only monitored albums were updated
    assert "A" in updated and "C" in updated


def test_unmonitor_all_except_specific_album_keep_target_by_mbid(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")

    albums = [
        {"id": 1, "title": "Target", "monitored": True, "foreignAlbumId": "MBIDT"},
        {"id": 2, "title": "Other", "monitored": True, "foreignAlbumId": "MBIDX"},
    ]

    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: albums)
    unmonitored = []

    def fake_update(album):
        if not album.get('monitored'):
            unmonitored.append(album.get('title'))
        return True

    monkeypatch.setattr(c, "update_album", fake_update)

    res = c.unmonitor_all_except_specific_album(1, "MBIDT", "Artist", "Target")
    assert res is True
    # Other album should have been unmonitored
    assert "Other" in unmonitored


def test_unmonitor_all_except_specific_album_keep_target_by_title(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")

    albums = [
        {"id": 1, "title": "Target Album", "monitored": True, "foreignAlbumId": None},
        {"id": 2, "title": "Target Album (Deluxe)", "monitored": True, "foreignAlbumId": None},
        {"id": 3, "title": "Other", "monitored": True, "foreignAlbumId": None},
    ]

    monkeypatch.setattr(c, "get_artist_albums", lambda artist_id: albums)
    unmonitored = []

    def fake_update(album):
        if not album.get('monitored'):
            unmonitored.append(album.get('title'))
        return True

    monkeypatch.setattr(c, "update_album", fake_update)

    res = c.unmonitor_all_except_specific_album(1, "", "Artist", "Target Album")
    assert res is True
    # Other album should have been unmonitored
    assert "Other" in unmonitored


def test_retry_request_retries_on_503_and_succeeds():
    c = LidarrClient("http://host", "k", 1, 1, "/root")
    c.max_retries = 4
    counter = {"n": 0}

    def flaky():
        if counter["n"] < 2:
            counter["n"] += 1
            raise requests.exceptions.RequestException("503 Service Unavailable")
        return "ok"

    res = c._retry_request(flaky)
    assert res == "ok"


def test_retry_request_raises_after_max(monkeypatch):
    c = LidarrClient("http://host", "k", 1, 1, "/root")
    c.max_retries = 2

    def always_fail():
        raise requests.exceptions.RequestException("503 Service Unavailable")

    try:
        c._retry_request(always_fail)
        raised = False
    except Exception:
        raised = True

    assert raised is True


class TestLidarrClientGetExistingArtists:
    """Test retrieving existing artists from Lidarr."""
    
    @responses.activate
    def test_get_existing_artists_success(self):
        """Test successful retrieval of existing artists."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        # Mock response
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist",
            json=[
                {"id": 1, "artistName": "Taylor Swift", "foreignArtistId": "abc123"},
                {"id": 2, "artistName": "The Beatles", "foreignArtistId": "xyz789"}
            ],
            status=200
        )
        
        result = client.get_existing_artists()
        
        assert len(result) == 2
        assert "taylor swift" in result
        assert "the beatles" in result
        assert result["taylor swift"]["id"] == 1
        assert result["the beatles"]["id"] == 2
    
    @responses.activate
    def test_get_existing_artists_empty(self):
        """Test when no artists exist."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist",
            json=[],
            status=200
        )
        
        result = client.get_existing_artists()
        assert result == {}
    
    @responses.activate
    def test_get_existing_artists_api_error(self):
        """Test handling API errors."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist",
            json={"error": "Unauthorized"},
            status=401
        )
        
        result = client.get_existing_artists()
        # Should return empty dict on error
        assert result == {}


class TestLidarrClientArtistLookup:
    """Test artist lookup functionality."""
    
    @responses.activate
    def test_artist_lookup_with_musicbrainz_id(self):
        """Test artist lookup using MusicBrainz ID."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist/lookup",
            json=[{
                "artistName": "Taylor Swift",
                "foreignArtistId": "abc123",
                "overview": "American singer-songwriter"
            }],
            status=200
        )
        
        result = client.artist_lookup("Taylor Swift", musicbrainz_id="abc123")
        
        assert result is not None
        assert result["artistName"] == "Taylor Swift"
        assert result["foreignArtistId"] == "abc123"
    
    @responses.activate
    def test_artist_lookup_by_name_only(self):
        """Test artist lookup by name only."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist/lookup",
            json=[{
                "artistName": "The Beatles",
                "foreignArtistId": "xyz789"
            }],
            status=200
        )
        
        result = client.artist_lookup("The Beatles")
        
        assert result is not None
        assert result["artistName"] == "The Beatles"
    
    @responses.activate
    def test_artist_lookup_not_found(self):
        """Test artist lookup when not found."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist/lookup",
            json=[],
            status=200
        )
        
        result = client.artist_lookup("Unknown Artist")
        assert result is None


class TestLidarrClientAddArtist:
    """Test adding artists to Lidarr."""
    
    @responses.activate
    def test_add_artist_success(self):
        """Test successfully adding an artist."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        artist_data = {
            "artistName": "Taylor Swift",
            "foreignArtistId": "abc123",
            "qualityProfileId": 1,
            "metadataProfileId": 1,
            "rootFolderPath": "/music",
            "monitored": False,
            "addOptions": {"searchForMissingAlbums": False}
        }
        
        responses.add(
            responses.POST,
            "http://localhost:8686/api/v1/artist",
            json={"id": 1, **artist_data},
            status=201
        )
        
        result = client.add_artist(artist_data)
        
        assert result is not None
        assert result["id"] == 1
        assert result["artistName"] == "Taylor Swift"
    
    @responses.activate
    def test_add_artist_already_exists(self):
        """Test adding an artist that already exists."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        artist_data = {
            "artistName": "Taylor Swift",
            "foreignArtistId": "abc123"
        }
        
        responses.add(
            responses.POST,
            "http://localhost:8686/api/v1/artist",
            body="Artist already exists",
            status=400
        )
        
        result = client.add_artist(artist_data)
        # Returns original data when artist already exists
        assert result is not None
        assert result["artistName"] == "Taylor Swift"


class TestLidarrClientGetArtistAlbums:
    """Test retrieving albums for an artist."""
    
    @responses.activate
    def test_get_artist_albums_success(self):
        """Test retrieving albums for an artist."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/album",
            json=[
                {"id": 1, "title": "1989", "monitored": True, "artist": {"id": 1, "artistName": "Taylor Swift"}},
                {"id": 2, "title": "Lover", "monitored": False, "artist": {"id": 1, "artistName": "Taylor Swift"}}
            ],
            status=200
        )
        
        result = client.get_artist_albums(artist_id=1)
        
        assert len(result) == 2
        assert result[0]["title"] == "1989"
        assert result[1]["title"] == "Lover"
    
    @responses.activate
    def test_get_artist_albums_empty(self):
        """Test when artist has no albums."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/album",
            json=[],
            status=200
        )
        
        result = client.get_artist_albums(artist_id=99)
        assert result == []


class TestLidarrClientMonitorAlbum:
    """Test monitoring specific albums."""
    
    @responses.activate
    def test_monitor_album_success(self):
        """Test successfully monitoring an album."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        album_data = {
            "id": 1,
            "title": "1989",
            "monitored": False
        }
        
        responses.add(
            responses.PUT,
            "http://localhost:8686/api/v1/album/1",
            json={**album_data, "monitored": True},
            status=200
        )
        
        album_data["monitored"] = True
        result = client.update_album(album_data)
        
        assert result is True
    
    @responses.activate
    def test_monitor_album_not_found(self):
        """Test monitoring album that doesn't exist."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        album_data = {
            "id": 999,
            "title": "Unknown Album",
            "monitored": True
        }
        
        responses.add(
            responses.PUT,
            "http://localhost:8686/api/v1/album/999",
            json={"error": "Album not found"},
            status=404
        )
        
        result = client.update_album(album_data)
        assert result is False


class TestLidarrClientSearchAlbum:
    """Test triggering album searches."""
    
    @responses.activate
    def test_search_album_success(self):
        """Test triggering album search."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.POST,
            "http://localhost:8686/api/v1/command",
            json={"id": 1, "name": "AlbumSearch", "status": "queued"},
            status=201
        )
        
        result = client.search_for_album(album_id=1)
        
        assert result is True


class TestLidarrClientRefreshArtist:
    """Test artist metadata refresh."""
    
    @responses.activate
    def test_refresh_artist_success(self):
        """Test triggering artist refresh."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        responses.add(
            responses.POST,
            "http://localhost:8686/api/v1/command",
            json={"id": 1, "name": "RefreshArtist", "status": "queued"},
            status=201
        )
        
        result = client.refresh_artist(artist_id=1)
        
        assert result is True


class TestLidarrClientIntegration:
    """Integration tests for common workflows."""
    
    @responses.activate
    def test_full_artist_workflow(self):
        """Test complete workflow: lookup → add → get albums."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        # Mock artist lookup
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/artist/lookup",
            json=[{"artistName": "Test Artist", "foreignArtistId": "test123"}],
            status=200
        )
        
        # Mock add artist
        responses.add(
            responses.POST,
            "http://localhost:8686/api/v1/artist",
            json={"id": 1, "artistName": "Test Artist"},
            status=201
        )
        
        # Mock get albums
        responses.add(
            responses.GET,
            "http://localhost:8686/api/v1/album",
            json=[{"id": 1, "title": "Test Album"}],
            status=200
        )
        
        # Execute workflow
        lookup = client.artist_lookup("Test Artist")
        assert lookup is not None
        
        added = client.add_artist(lookup)
        assert added is not None
        assert added["id"] == 1
        
        albums = client.get_artist_albums(1)
        assert len(albums) == 1
        assert albums[0]["title"] == "Test Album"
    
    def test_client_string_representation(self):
        """Test string representation of client."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="secret-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music"
        )
        
        repr_str = repr(client)
        assert "LidarrClient" in repr_str
        assert "localhost:8686" in repr_str
        # API key should be redacted
        assert "secret-key" not in repr_str or "***" in repr_str


class TestLidarrClientErrorHandling:
    """Test error handling and retry logic."""
    
    @responses.activate
    def test_handles_timeout_errors(self):
        """Test handling of timeout errors."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0,
            timeout=1
        )
        
        def timeout_callback(request):
            raise requests.exceptions.Timeout("Request timed out")
        
        responses.add_callback(
            responses.GET,
            "http://localhost:8686/api/v1/artist",
            callback=timeout_callback
        )
        
        result = client.get_existing_artists()
        # Should handle gracefully and return empty dict
        assert result == {}
    
    @responses.activate
    def test_handles_connection_errors(self):
        """Test handling of connection errors."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        def connection_error_callback(request):
            raise requests.exceptions.ConnectionError("Connection refused")
        
        responses.add_callback(
            responses.GET,
            "http://localhost:8686/api/v1/artist",
            callback=connection_error_callback
        )
        
        result = client.get_existing_artists()
        # Should handle gracefully
        assert result == {}

"""
Tests for Lidarr API Client

Tests the LidarrClient class for interacting with Lidarr's Web Service API.
Uses HTTP mocking to test API calls without a real Lidarr instance.
"""

import pytest
import responses
import requests
import time
from unittest.mock import Mock, patch
from lib.lidarr_client import LidarrClient


class TestLidarrClientInit:
    """Test LidarrClient initialization."""
    
    def test_init_with_required_parameters(self):
        """Test initialization with required parameters."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-api-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music"
        )
        
        assert client.base_url == "http://localhost:8686"
        assert client.api_key == "test-api-key"
        assert client.quality_profile_id == 1
        assert client.metadata_profile_id == 1
        assert client.root_folder_path == "/music"
    
    def test_init_strips_trailing_slash_from_url(self):
        """Test that trailing slash is removed from base URL."""
        client = LidarrClient(
            base_url="http://localhost:8686/",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music"
        )
        
        assert client.base_url == "http://localhost:8686"
        assert not client.base_url.endswith('/')
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        client = LidarrClient(
            base_url="http://example.com:8080",
            api_key="custom-key",
            quality_profile_id=5,
            metadata_profile_id=3,
            root_folder_path="/custom/path",
            request_delay=1.0,
            max_retries=5,
            retry_delay=3.0,
            timeout=60
        )
        
        assert client.request_delay == 1.0
        assert client.max_retries == 5
        assert client.retry_delay == 3.0
        assert client.timeout == 60
    
    def test_init_sets_default_values(self):
        """Test that default values are set correctly."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music"
        )
        
        assert client.request_delay == 0.5
        assert client.max_retries == 3
        assert client.retry_delay == 2.0
        assert client.timeout == 30
        assert client.last_request_time == 0


class TestLidarrClientHeaders:
    """Test header generation."""
    
    def test_get_headers_includes_api_key(self):
        """Test that headers include API key."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-api-key-123",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music"
        )
        
        headers = client._get_headers()
        assert "X-Api-Key" in headers
        assert headers["X-Api-Key"] == "test-api-key-123"


class TestLidarrClientRateLimiting:
    """Test rate limiting functionality."""
    
    def test_wait_for_rate_limit_delays_requests(self):
        """Test that rate limiting adds delay between requests."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0.1
        )
        
        # Simulate first request
        client.last_request_time = time.time()
        
        # Wait should delay
        start = time.time()
        client._wait_for_rate_limit()
        elapsed = time.time() - start
        
        # Should have waited approximately request_delay seconds
        assert elapsed >= 0.09  # Allow small tolerance
    
    def test_wait_for_rate_limit_with_zero_delay(self):
        """Test that zero delay doesn't wait."""
        client = LidarrClient(
            base_url="http://localhost:8686",
            api_key="test-key",
            quality_profile_id=1,
            metadata_profile_id=1,
            root_folder_path="/music",
            request_delay=0
        )
        
        client.last_request_time = time.time()
        start = time.time()
        client._wait_for_rate_limit()
        elapsed = time.time() - start
        
        # Should be nearly instant
        assert elapsed < 0.01


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

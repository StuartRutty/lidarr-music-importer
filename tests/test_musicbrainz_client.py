"""
Unit tests for lib/musicbrainz_client.py

Tests MusicBrainz API client including request handling, rate limiting,
XML parsing, and error handling.
"""

import pytest
import time
import responses
import sys
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET

# Add parent directory to path to import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.musicbrainz_client import MusicBrainzClient


class TestMusicBrainzClientInit:
    """Tests for MusicBrainzClient initialization."""

    @pytest.mark.unit
    def test_init_default_settings(self):
        """Test client initialization with default settings."""
        client = MusicBrainzClient()
        
        assert client.base_url == "https://musicbrainz.org/ws/2"
        assert client.min_delay >= 1.0  # Respects MB TOS minimum
        assert client.timeout == 30
        assert client.last_request_time == 0.0

    @pytest.mark.unit
    def test_init_custom_delay(self):
        """Test client initialization with custom delay."""
        client = MusicBrainzClient(delay=2.5)
        
        assert client.min_delay == 2.5

    @pytest.mark.unit
    def test_init_enforces_minimum_delay(self):
        """Test that delay below 1.0 is enforced to minimum."""
        client = MusicBrainzClient(delay=0.5)
        
        # Should be enforced to 1.0 per MB TOS
        assert client.min_delay == 1.0

    @pytest.mark.unit
    def test_init_custom_user_agent(self):
        """Test client initialization with custom user agent."""
        user_agent = {
            'app_name': 'test-app',
            'version': '1.0',
            'contact': 'test@example.com'
        }
        
        client = MusicBrainzClient(user_agent=user_agent)
        
        # Check that user agent is set in session headers
        assert 'User-Agent' in client.session.headers
        assert 'test-app' in client.session.headers['User-Agent']
        assert '1.0' in client.session.headers['User-Agent']
        assert 'test@example.com' in client.session.headers['User-Agent']

    @pytest.mark.unit
    def test_init_sets_accept_header(self):
        """Test that Accept header is set to XML."""
        client = MusicBrainzClient()
        
        assert client.session.headers['Accept'] == 'application/xml'

    @pytest.mark.unit
    def test_init_custom_timeout(self):
        """Test client initialization with custom timeout."""
        client = MusicBrainzClient(timeout=60)
        
        assert client.timeout == 60


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    @pytest.mark.unit
    def test_rate_limit_waits_between_requests(self):
        """Test that client waits for rate limit between requests."""
        client = MusicBrainzClient(delay=1.0)
        
        # First request (no wait needed)
        start = time.time()
        client._wait_for_rate_limit()
        first_duration = time.time() - start
        
        # Second request (should wait)
        start = time.time()
        client._wait_for_rate_limit()
        second_duration = time.time() - start
        
        # First request should be instant, second should wait ~1sec
        assert first_duration < 0.1
        assert second_duration >= 0.9  # Allow small margin

    @pytest.mark.unit
    def test_rate_limit_respects_custom_delay(self):
        """Test that custom delay is respected."""
        client = MusicBrainzClient(delay=0.5)  # Will be enforced to 1.0
        
        client._wait_for_rate_limit()
        
        start = time.time()
        client._wait_for_rate_limit()
        duration = time.time() - start
        
        # Should wait at least 1.0 second (enforced minimum)
        assert duration >= 0.9

    @pytest.mark.unit
    def test_rate_limit_updates_last_request_time(self):
        """Test that last_request_time is updated."""
        client = MusicBrainzClient()
        
        initial_time = client.last_request_time
        assert initial_time == 0.0
        
        client._wait_for_rate_limit()
        
        assert client.last_request_time > initial_time
        assert client.last_request_time > 0


class TestMakeRequest:
    """Tests for _make_request method."""

    @pytest.mark.unit
    @responses.activate
    def test_make_request_success(self):
        """Test successful API request."""
        client = MusicBrainzClient(delay=0.1)
        
        # Mock successful response
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <artist-list count="1" offset="0">
        <artist id="test-id" type="Group">
            <name>Test Artist</name>
        </artist>
    </artist-list>
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body=xml_response,
            status=200,
            content_type='application/xml'
        )
        
        result = client._make_request('artist', {'query': 'test'})
        
        assert result is not None
        assert isinstance(result, ET.Element)

    @pytest.mark.unit
    @responses.activate
    def test_make_request_503_rate_limited(self):
        """Test handling of 503 rate limit response."""
        client = MusicBrainzClient(delay=0.1)
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body='Rate limit exceeded',
            status=503
        )
        
        result = client._make_request('artist', {'query': 'test'})
        
        assert result is None

    @pytest.mark.unit
    @responses.activate
    def test_make_request_404_not_found(self):
        """Test handling of 404 response."""
        client = MusicBrainzClient(delay=0.1)
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body='Not found',
            status=404
        )
        
        result = client._make_request('artist', {'query': 'test'})
        
        assert result is None

    @pytest.mark.unit
    @responses.activate
    def test_make_request_timeout(self):
        """Test handling of request timeout."""
        import requests
        client = MusicBrainzClient(delay=0.1, timeout=1)
        
        # Simulate timeout using responses callback
        def timeout_callback(request):
            raise requests.exceptions.Timeout('Connection timeout')
        
        responses.add_callback(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            callback=timeout_callback
        )
        
        result = client._make_request('artist', {'query': 'test'})
        assert result is None

    @pytest.mark.unit
    @responses.activate
    def test_make_request_invalid_xml(self):
        """Test handling of invalid XML response."""
        client = MusicBrainzClient(delay=0.1)
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body='<invalid xml',
            status=200
        )
        
        result = client._make_request('artist', {'query': 'test'})
        
        assert result is None


class TestSearchArtists:
    """Tests for search_artists method."""

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_artists_success(self):
        """Test successful artist search."""
        client = MusicBrainzClient(delay=0.1)
        
        xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#" xmlns:ext="http://musicbrainz.org/ns/ext#-2.0">
    <artist-list count="2">
        <artist id="artist-1" ext:score="100">
            <name>Son Lux</name>
        </artist>
        <artist id="artist-2" ext:score="90">
            <name>Son Lux Trio</name>
        </artist>
    </artist-list>
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body=xml_response,
            status=200
        )
        
        result = client.search_artists('Son Lux', limit=5)
        
        assert 'artist-list' in result
        assert len(result['artist-list']) == 2
        assert result['artist-list'][0]['name'] == 'Son Lux'
        assert result['artist-list'][0]['id'] == 'artist-1'

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_artists_no_results(self):
        """Test artist search with no results."""
        client = MusicBrainzClient(delay=0.1)
        
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <artist-list count="0" />
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body=xml_response,
            status=200
        )
        
        result = client.search_artists('NonexistentArtist')
        
        assert result == {"artist-list": []}

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_artists_api_failure(self):
        """Test artist search when API fails."""
        client = MusicBrainzClient(delay=0.1)
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body='Server error',
            status=500
        )
        
        result = client.search_artists('Test Artist')
        
        assert result == {"artist-list": []}

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_artists_custom_limit(self):
        """Test artist search with custom limit parameter."""
        client = MusicBrainzClient(delay=0.1)
        
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <artist-list count="1">
        <artist id="test-id" ext:score="100">
            <name>Test</name>
        </artist>
    </artist-list>
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/artist',
            body=xml_response,
            status=200
        )
        
        result = client.search_artists('Test', limit=10)
        
        # Check that request was made with correct limit
        assert len(responses.calls) == 1
        assert 'limit=10' in responses.calls[0].request.url


class TestBuildReleaseGroupQueries:
    """Tests for _build_release_group_queries method."""

    @pytest.mark.unit
    def test_build_queries_normal_artist(self):
        """Test query building for normal artist name."""
        client = MusicBrainzClient()
        
        queries = client._build_release_group_queries('Radiohead', 'OK Computer')
        
        assert len(queries) > 0
        assert any('Radiohead' in q for q in queries)
        assert any('OK Computer' in q for q in queries)

    @pytest.mark.unit
    def test_build_queries_artist_with_special_chars(self):
        """Test query building for artist with special characters."""
        client = MusicBrainzClient()
        
        queries = client._build_release_group_queries('A$AP Rocky', 'Testing')
        
        # Should include both original and cleaned version
        assert any('A$AP Rocky' in q for q in queries)
        assert any('ASAP Rocky' in q for q in queries)

    @pytest.mark.unit
    def test_build_queries_bracketed_artist(self):
        """Test query building for artist with brackets."""
        client = MusicBrainzClient()
        
        queries = client._build_release_group_queries('[bsd.u]', 'Album')
        
        # Should try both with and without brackets
        assert any('[bsd.u]' in q for q in queries)
        assert any('bsd.u' in q for q in queries)

    @pytest.mark.unit
    def test_build_queries_progressive_loosening(self):
        """Test that queries get progressively looser."""
        client = MusicBrainzClient()
        
        queries = client._build_release_group_queries('Artist', 'Album')
        
        # First queries should be more strict (with quotes)
        assert queries[0].count('"') >= queries[-1].count('"')


class TestSearchReleaseGroups:
    """Tests for search_release_groups method."""

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_release_groups_success(self):
        """Test successful release group search."""
        client = MusicBrainzClient(delay=0.1)
        
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#" xmlns:ext="http://musicbrainz.org/ns/ext#-2.0">
    <release-group-list count="1">
        <release-group id="rg-1" type="Album" ext:score="100">
            <title>Tomorrows I</title>
            <artist-credit>
                <name-credit>
                    <artist id="artist-1">
                        <name>Son Lux</name>
                    </artist>
                </name-credit>
            </artist-credit>
        </release-group>
    </release-group-list>
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/release-group',
            body=xml_response,
            status=200
        )
        
        result = client.search_release_groups('Son Lux', 'Tomorrows I')
        
        assert 'release-group-list' in result
        assert len(result['release-group-list']) >= 1

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_search_release_groups_no_results(self):
        """Test release group search with no results."""
        client = MusicBrainzClient(delay=0.1)
        
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <release-group-list count="0" />
</metadata>'''
        
        responses.add(
            responses.GET,
            'https://musicbrainz.org/ws/2/release-group',
            body=xml_response,
            status=200
        )
        
        result = client.search_release_groups('Unknown', 'Album')
        
        assert result == {"release-group-list": []}

    @pytest.mark.unit
    @pytest.mark.api
    def test_search_release_groups_with_aliases(self):
        """Test release group search with artist aliases."""
        client = MusicBrainzClient(delay=0.1)
        
        aliases = {
            'kanye west': ['ye', 'kanye']
        }
        
        # Just test that method accepts aliases parameter
        with patch.object(client, '_make_request', return_value=None):
            result = client.search_release_groups(
                'Kanye West',
                'Donda',
                artist_aliases=aliases
            )
            assert 'release-group-list' in result


class TestIntegration:
    """Integration tests for MusicBrainzClient."""

    @pytest.mark.unit
    def test_client_lifecycle(self):
        """Test complete client lifecycle."""
        # Create client
        client = MusicBrainzClient(
            delay=1.0,
            user_agent={
                'app_name': 'test',
                'version': '1.0',
                'contact': 'test@example.com'
            }
        )
        
        # Verify initialization
        assert client.base_url is not None
        assert client.session is not None
        assert client.min_delay >= 1.0

    @pytest.mark.unit
    @pytest.mark.api
    @responses.activate
    def test_multiple_searches_respect_rate_limit(self):
        """Test that multiple searches respect rate limiting."""
        client = MusicBrainzClient(delay=1.0)
        
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <artist-list count="0" />
</metadata>'''
        
        # Add multiple responses
        for _ in range(3):
            responses.add(
                responses.GET,
                'https://musicbrainz.org/ws/2/artist',
                body=xml_response,
                status=200
            )
        
        start = time.time()
        
        # Make multiple requests
        client.search_artists('Artist1')
        client.search_artists('Artist2')
        client.search_artists('Artist3')
        
        duration = time.time() - start
        
        # Should take at least 2 seconds (2 waits between 3 requests)
        assert duration >= 1.8  # Allow small margin

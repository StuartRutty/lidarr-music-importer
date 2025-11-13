"""
Combined MusicBrainz client tests.

This file merges several MusicBrainz-related test modules into a single
canonical test file for easier maintenance.
"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import time
import re

import pytest
import responses
from unittest.mock import patch, Mock

# allow importing from repo
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.musicbrainz_client import MusicBrainzClient


class TestMusicBrainzClientInit:
    """Tests for MusicBrainzClient initialization."""

    @pytest.mark.unit
    def test_init_default_settings(self):
        client = MusicBrainzClient()
        assert client.base_url == "https://musicbrainz.org/ws/2"
        assert client.min_delay >= 1.0

    @pytest.mark.unit
    def test_init_custom_delay(self):
        client = MusicBrainzClient(delay=2.5)
        assert client.min_delay == 2.5

    @pytest.mark.unit
    def test_init_enforces_minimum_delay(self):
        client = MusicBrainzClient(delay=0.5)
        assert client.min_delay == 1.0

    @pytest.mark.unit
    def test_init_custom_user_agent(self):
        user_agent = {'app_name': 'test-app', 'version': '1.0', 'contact': 'test@example.com'}
        client = MusicBrainzClient(user_agent=user_agent)
        assert 'User-Agent' in client.session.headers


class TestRateLimiting:
    @pytest.mark.unit
    def test_rate_limit_waits_between_requests(self):
        client = MusicBrainzClient(delay=1.0)
        client._wait_for_rate_limit()
        start = time.time()
        client._wait_for_rate_limit()
        assert time.time() - start >= 0.9


class TestMakeRequest:
    @pytest.mark.unit
    @responses.activate
    def test_make_request_success(self):
        client = MusicBrainzClient(delay=0.1)
        xml_response = '''<?xml version="1.0"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
    <artist-list count="1" offset="0">
        <artist id="test-id" type="Group">
            <name>Test Artist</name>
        </artist>
    </artist-list>
</metadata>'''
        responses.add(responses.GET, 'https://musicbrainz.org/ws/2/artist', body=xml_response, status=200, content_type='application/xml')
        result = client._make_request('artist', {'query': 'test'})
        assert result is not None


    @pytest.mark.unit
    @responses.activate
    def test_make_request_503_rate_limited(self):
        client = MusicBrainzClient(delay=0.1)
        responses.add(responses.GET, 'https://musicbrainz.org/ws/2/artist', body='Rate limit exceeded', status=503)
        result = client._make_request('artist', {'query': 'test'})
        assert result is None


class TestSearchArtists:
    @pytest.mark.unit
    @responses.activate
    def test_search_artists_success(self):
        client = MusicBrainzClient(delay=0.1)
        xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#" xmlns:ext="http://musicbrainz.org/ns/ext#-2.0">
    <artist-list count="2">
        <artist id="artist-1" ext:score="100"><name>Son Lux</name></artist>
        <artist id="artist-2" ext:score="90"><name>Son Lux Trio</name></artist>
    </artist-list>
</metadata>'''
        responses.add(responses.GET, 'https://musicbrainz.org/ws/2/artist', body=xml_response, status=200)
        result = client.search_artists('Son Lux', limit=5)
        assert 'artist-list' in result


@responses.activate
def test_search_release_groups_json_prefers_spotify_relation():
    client = MusicBrainzClient()
    body = {
        'release-groups': [
            {'id': 'rg-spotify-match', 'title': 'Album Two', 'artist-credit-phrase': 'Test Artist', 'first-release-date': '2021-02-02', 'relations': [{ 'url': { 'resource': 'https://open.spotify.com/album/ALBID2' } }]},
            {'id': 'rg-other', 'title': 'Album Two', 'artist-credit-phrase': 'Test Artist', 'first-release-date': '2021-02-02', 'relations': []}
        ]
    }
    url_re = re.compile(r'https://musicbrainz.org/ws/2/release-group.*')
    responses.add(responses.GET, url_re, json=body, status=200, content_type='application/json')
    result = client.search_release_groups('Test Artist', 'Album Two', spotify_album_id='ALBID2')
    if isinstance(result, dict):
        if 'release-group-list' in result:
            candidate = result['release-group-list'][0]
            assert candidate.get('id') == 'rg-spotify-match'
        else:
            assert result.get('id') == 'rg-spotify-match'
    else:
        assert result[0].get('id') == 'rg-spotify-match'


def test_generate_title_variations_basic():
    client = MusicBrainzClient()
    variations = client._generate_title_variations('ep seeds')
    assert variations[0] == 'ep seeds'
    assert 'seeds' in variations


def test_is_artist_match_simple():
    client = MusicBrainzClient()
    assert client._is_artist_match('Son Lux', 'Son Lux', {}) is True
    assert client._is_artist_match('The Beatles', 'beatles', {}) is True
    assert client._is_artist_match('Different Artist', 'Target Artist', {}) is False


@responses.activate
def test_search_release_groups_prefers_stripped_title():
    client = MusicBrainzClient()
    body = {'release-groups': [{'id': 'rg-seeds', 'title': 'seeds', 'artist-credit-phrase': 'eevee', 'first-release-date': '2020-01-01', 'relations': []}]}
    with patch.object(client, '_make_request', return_value=body):
        result = client.search_release_groups('eevee', 'ep seeds')
    assert isinstance(result, dict)
    assert 'release-group-list' in result
    assert result['release-group-list'][0]['id'] == 'rg-seeds'


# Additional tests: XML parsing, _make_request error paths, and extra artist-match edge cases
def test_extract_artists_from_root_with_json_and_xml():
        client = MusicBrainzClient()

        # JSON-style input
        json_root = {'artists': [{'id': 'a1', 'name': 'Test Artist', 'ext:score': 100}]}
        artists = client._extract_artists_from_root(json_root, 'Test Artist')
        assert isinstance(artists, list)
        assert artists and artists[0].get('id') == 'a1'

        # XML-style input: craft a minimal MB-like XML
        xml_text = '''<?xml version="1.0"?>
        <metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
            <artist-list>
                <artist id="xml-1"><name>XML Artist</name></artist>
            </artist-list>
        </metadata>'''
        root = ET.fromstring(xml_text)
        artists_xml = client._extract_artists_from_root(root, 'XML Artist')
        assert isinstance(artists_xml, list)
        assert artists_xml and artists_xml[0].get('id') == 'xml-1'


def test_parse_release_groups_xml_filters_and_parses():
        client = MusicBrainzClient()

        xml_text = '''<?xml version="1.0"?>
        <metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">
            <release-group-list>
                <release-group id="rg-parse-1">
                    <title>Parsed Album</title>
                    <artist-credit>
                        <name-credit>
                            <artist><name>Parse Artist</name></artist>
                        </name-credit>
                    </artist-credit>
                    <first-release-date>2020-01-01</first-release-date>
                </release-group>
            </release-group-list>
        </metadata>'''

        root = ET.fromstring(xml_text)
        ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
        rgs = root.findall('.//mb:release-group', ns)

        parsed = client._parse_release_groups(rgs, ns, 'Parse Artist', {})
        assert isinstance(parsed, list)
        assert parsed and parsed[0].get('id') == 'rg-parse-1'

        # Ensure artist mismatch filters out results
        parsed_none = client._parse_release_groups(rgs, ns, 'Other Artist', {})
        assert parsed_none == []


def test_make_request_handles_timeout_and_503(monkeypatch):
        client = MusicBrainzClient(delay=0.0)

        class DummyResp:
                def __init__(self, status_code=503, text='err'):
                        self.status_code = status_code
                        self.text = text

                def raise_for_status(self):
                        from requests import HTTPError
                        err = HTTPError(self.text)
                        err.response = self
                        raise err

        # Simulate timeout
        def fake_get_timeout(url, params=None, timeout=None):
                from requests import exceptions
                raise exceptions.Timeout()

        monkeypatch.setattr(client.session, 'get', fake_get_timeout)
        res = client._make_request('artist', {'query': 'x'})
        assert res is None

        # Simulate 503 response
        def fake_get_503(url, params=None, timeout=None):
                return DummyResp(503, 'Service Unavailable')

        monkeypatch.setattr(client.session, 'get', fake_get_503)
        res2 = client._make_request('artist', {'query': 'x'})
        assert res2 is None


def test_is_artist_match_edge_cases():
        client = MusicBrainzClient()

        # empty credit or artist returns False
        assert client._is_artist_match('', 'Artist', {}) is False
        assert client._is_artist_match('Credit', '', {}) is False

        # aliases matching
        aliases = {'foo': ['the foo', 'foo']}
        assert client._is_artist_match('The Foo', 'foo', aliases) is True


# --- moved from tests/test_musicbrainz_client_extra.py ---
def test_generate_title_variations_titlecase_ampersand_and_no_punct():
    client = MusicBrainzClient()
    title = "ep & seeds"
    variations = client._generate_title_variations(title)

    # Original should be first
    assert variations[0] == title

    # Ampersand replaced by 'and'
    assert any('and' in v for v in variations)

    # No punctuation version should be present
    assert any(re.match(r'^ep seeds$|^seeds$', v) for v in variations)


def test_generate_title_variations_all_caps_short_title():
    client = MusicBrainzClient()
    title = "NIN"
    variations = client._generate_title_variations(title)

    # For short titles, uppercase variant may be added
    assert 'NIN' in variations


def test_build_release_group_queries_for_bracketed_artist():
    client = MusicBrainzClient()
    artist = "[single] Artist Name"
    release = "Some Album"
    queries = client._build_release_group_queries(artist, release)

    # Should produce at least one query and include artist in some form
    assert isinstance(queries, list)
    assert any('Artist Name' in q or 'single' in q for q in queries)


def test_extract_release_groups_from_json_normalizes_fields():
    client = MusicBrainzClient()
    body = {
        'release-groups': [
            {
                'id': 'rg-1',
                'title': 'Test Album',
                'artist-credit-phrase': 'The Band',
                'first-release-date': '2020-01-01',
                'relations': []
            }
        ]
    }

    # call the (internal) JSON extractor
    rgs = client._extract_release_groups_from_json(body)
    assert isinstance(rgs, list)
    assert rgs and rgs[0].get('id') == 'rg-1'
    assert rgs[0].get('title') == 'Test Album'


def test_is_artist_match_with_alias_and_similarity():
    client = MusicBrainzClient()
    # artist_credit_phrase from MB and user-supplied artist
    credit = 'The Weeknd'
    artist = 'weeknd'
    aliases = {'weeknd': ['the weeknd', 'weeknd']}

    assert client._is_artist_match(credit, artist, aliases) is True


def test_extract_release_groups_from_json_artist_credit_trackcount_and_relations():
    client = MusicBrainzClient()

    body = {
        'release-groups': [
            {
                'id': 'rg-json-1',
                'title': 'JSON Album',
                # artist-credit as list of dicts (artist and name parts)
                'artist-credit': [
                    {'artist': {'name': 'Primary Artist'}},
                    {'name': 'Feat Artist'}
                ],
                'first-release-date': '2022-05-05',
                'relations': [
                    {'url': {'resource': 'https://example.com/rg1'}},
                    {'target': 'https://other.example/rg1'}
                ],
                'releases': [
                    {'media': [{'track-count': 11}]}
                ],
                'ext:score': 95
            }
        ]
    }

    rgs = client._extract_release_groups_from_json(body)
    assert isinstance(rgs, list)
    assert rgs and rgs[0]['id'] == 'rg-json-1'
    # current implementation prefers the nested 'artist' name; second part is ignored
    assert rgs[0]['artist-credit-phrase'] == 'Primary Artist'
    assert rgs[0]['track_count'] == 11
    assert 'https://example.com/rg1' in rgs[0]['urls']
    assert 'https://other.example/rg1' in rgs[0]['urls'] or any('other.example' in u for u in rgs[0]['urls'])


def test_search_release_groups_fallback_releasegroup_only_json(monkeypatch):
    client = MusicBrainzClient()

    # _make_request: return None for main queries, return JSON for fallback releasegroup-only queries
    def fake_make_request(endpoint, params):
        q = params.get('query', '')
        if q.startswith('releasegroup:"'):
            return {
                'release-groups': [
                    {'id': 'rg-fallback', 'title': 'Fallback Album', 'artist-credit-phrase': 'Fallback Artist', 'first-release-date': '2019-01-01', 'relations': []}
                ]
            }
        return None

    monkeypatch.setattr(client, '_make_request', fake_make_request)

    res = client.search_release_groups('Fallback Artist', 'Fallback Album')
    assert isinstance(res, dict)
    assert res.get('release-group-list') and res['release-group-list'][0]['id'] == 'rg-fallback'


def test_search_release_groups_volume_handling_and_no_match(monkeypatch):
    client = MusicBrainzClient()

    # Case A: a matching volume present
    def make_req_with_vol(endpoint, params):
        return {
            'release-groups': [
                {'id': 'rg-vol5', 'title': 'Hits Vol. 5', 'artist-credit-phrase': 'Vol Artist', 'ext:score': '80', 'relations': [], 'first-release-date': '2018-01-01'},
                {'id': 'rg-vol3', 'title': 'Hits Vol. 3', 'artist-credit-phrase': 'Vol Artist', 'ext:score': '70', 'relations': [], 'first-release-date': '2018-01-01'}
            ]
        }

    monkeypatch.setattr(client, '_make_request', make_req_with_vol)
    res = client.search_release_groups('Vol Artist', 'Hits Vol. 5')
    assert isinstance(res, dict)
    assert res.get('release-group-list') and res['release-group-list'][0]['id'] == 'rg-vol5'

    # Case B: requested volume but no candidates matching that volume -> expect empty result list
    def make_req_no_matching_vol(endpoint, params):
        # returns only Vol. 2/3 results
        return {
            'release-groups': [
                {'id': 'rg-vol2', 'title': 'Hits Vol. 2', 'artist-credit-phrase': 'Vol Artist', 'ext:score': '60', 'relations': [], 'first-release-date': '2018-01-01'}
            ]
        }

    monkeypatch.setattr(client, '_make_request', make_req_no_matching_vol)
    res2 = client.search_release_groups('Vol Artist', 'Hits Vol. 5')
    assert isinstance(res2, dict)
    assert res2.get('release-group-list') == []


def test_parse_release_groups_exact_title_preference():
    client = MusicBrainzClient()

    # Build two release-group XML elements with same artist credit but different titles/scores
    ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
    rg1 = ET.Element('{http://musicbrainz.org/ns/mmd-2.0#}release-group', {'id': 'rg-a', '{http://musicbrainz.org/ns/ext#-2.0}score': '50'})
    t1 = ET.SubElement(rg1, '{http://musicbrainz.org/ns/mmd-2.0#}title')
    t1.text = 'Exact Album'
    ac1 = ET.SubElement(rg1, '{http://musicbrainz.org/ns/mmd-2.0#}artist-credit')
    nc1 = ET.SubElement(ac1, '{http://musicbrainz.org/ns/mmd-2.0#}name-credit')
    art1 = ET.SubElement(nc1, '{http://musicbrainz.org/ns/mmd-2.0#}artist')
    name1 = ET.SubElement(art1, '{http://musicbrainz.org/ns/mmd-2.0#}name')
    name1.text = 'Exact Artist'

    rg2 = ET.Element('{http://musicbrainz.org/ns/mmd-2.0#}release-group', {'id': 'rg-b', '{http://musicbrainz.org/ns/ext#-2.0}score': '90'})
    t2 = ET.SubElement(rg2, '{http://musicbrainz.org/ns/mmd-2.0#}title')
    t2.text = 'Similar Album'
    ac2 = ET.SubElement(rg2, '{http://musicbrainz.org/ns/mmd-2.0#}artist-credit')
    nc2 = ET.SubElement(ac2, '{http://musicbrainz.org/ns/mmd-2.0#}name-credit')
    art2 = ET.SubElement(nc2, '{http://musicbrainz.org/ns/mmd-2.0#}artist')
    name2 = ET.SubElement(art2, '{http://musicbrainz.org/ns/mmd-2.0#}name')
    name2.text = 'Exact Artist'

    parsed = client._parse_release_groups([rg1, rg2], {'mb': ns['mb'], 'ns2': 'http://musicbrainz.org/ns/ext#-2.0'}, 'Exact Artist', {}, title_searched='Exact Album')
    assert isinstance(parsed, list)
    assert parsed and parsed[0]['title'].lower() == 'exact album'


"""
Tests for MusicBrainzClient JSON handling.

Verifies that release-group search prefers Spotify relation matching when the JSON response
contains an external URL referencing the Spotify album id.
"""
import sys
from pathlib import Path
import json
import re

import pytest
import responses

# allow importing from repo
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.musicbrainz_client import MusicBrainzClient


@responses.activate
def test_search_release_groups_json_prefers_spotify_relation():
    client = MusicBrainzClient()

    # Prepare a JSON body with a release-group that contains a Spotify relation
    body = {
        'release-groups': [
            {
                'id': 'rg-spotify-match',
                'title': 'Album Two',
                'artist-credit-phrase': 'Test Artist',
                'first-release-date': '2021-02-02',
                'relations': [
                    { 'url': { 'resource': 'https://open.spotify.com/album/ALBID2' } }
                ]
            },
            {
                'id': 'rg-other',
                'title': 'Album Two',
                'artist-credit-phrase': 'Test Artist',
                'first-release-date': '2021-02-02',
                'relations': []
            }
        ]
    }

    # Mock the release-group endpoint (allow any query params)
    url_re = re.compile(r'https://musicbrainz.org/ws/2/release-group.*')
    responses.add(responses.GET, url_re, json=body, status=200,
                  content_type='application/json')

    # Now call search_release_groups asking to prefer spotify album id
    result = client.search_release_groups('Test Artist', 'Album Two', spotify_album_id='ALBID2')

    # Depending on implementation the function may return a dict or a tuple/list.
    # We assert that the returned candidate has the id for the Spotify-matching release-group.
    if isinstance(result, dict):
        # older implementations may wrap results under a top-level key
        if 'release-group-list' in result:
            candidate = result['release-group-list'][0]
            assert candidate.get('id') == 'rg-spotify-match'
        else:
            assert result.get('id') == 'rg-spotify-match'
    else:
        # assume a tuple/list with first element the candidate dict
        assert result[0].get('id') == 'rg-spotify-match'

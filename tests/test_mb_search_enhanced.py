"""Unit tests for the enhanced MusicBrainz search behaviors.

These tests cover the title-variation generation and a simple
search_release_groups flow that prefers stripped/variation titles
such as removing an "ep" prefix.
"""

import re
from unittest.mock import patch

import responses

from lib.musicbrainz_client import MusicBrainzClient


def test_generate_title_variations_basic():
	client = MusicBrainzClient()

	variations = client._generate_title_variations('ep seeds')

	# original should be first
	assert variations[0] == 'ep seeds'

	# a stripped form should be present
	assert 'seeds' in variations

	# title-case variation should be present when original is lowercase
	assert 'Ep Seeds' in variations


def test_is_artist_match_simple():
	client = MusicBrainzClient()

	# Direct containment should succeed
	assert client._is_artist_match('Son Lux', 'Son Lux', {}) is True

	# Case-insensitive containment
	assert client._is_artist_match('The Beatles', 'beatles', {}) is True

	# Non-matching credit should fail
	assert client._is_artist_match('Different Artist', 'Target Artist', {}) is False


@responses.activate
def test_search_release_groups_prefers_stripped_title():
	"""When the releasegroup title is provided as 'ep seeds', the client
	should try variations and successfully pick the 'seeds' entry returned
	by the mocked _make_request JSON response."""

	client = MusicBrainzClient()

	# Prepare a JSON body with a release-group that has title 'seeds' and matches artist 'eevee'
	body = {
		'release-groups': [
			{
				'id': 'rg-seeds',
				'title': 'seeds',
				'artist-credit-phrase': 'eevee',
				'first-release-date': '2020-01-01',
				'relations': []
			},
		]
	}

	# Instead of mocking the network URL, monkeypatch the client's _make_request
	with patch.object(client, '_make_request', return_value=body):
		result = client.search_release_groups('eevee', 'ep seeds')

	assert isinstance(result, dict)
	assert 'release-group-list' in result
	assert result['release-group-list'][0]['id'] == 'rg-seeds'



import pytest

from lib import parser_utils


def test_normalize_spotify_id_empty():
    assert parser_utils.normalize_spotify_id('') == ''
    assert parser_utils.normalize_spotify_id(None) == ''


def test_normalize_spotify_id_variants():
    assert parser_utils.normalize_spotify_id('spotify:album:ALBID123') == 'ALBID123'
    assert parser_utils.normalize_spotify_id('https://open.spotify.com/album/ALBID456?si=xyz') == 'ALBID456'
    assert parser_utils.normalize_spotify_id('ALBID789') == 'ALBID789'


def test_aggregate_spotify_rows_basic():
    rows = [
        {'Artist Name': 'A', 'Album Name': 'B', 'Album ID': 'spotify:album:ALB1', 'Track Name': 't1', 'ISRC': 'isrc1'},
        {'Artist Name': 'A', 'Album Name': 'B', 'Album URL': 'https://open.spotify.com/album/ALB1', 'Track Name': 't2', 'ISRC': 'isrc2'},
        {'Artist Name': 'C', 'Album Name': 'D', 'Album ID': 'ALB2', 'Track Name': 'x', 'ISRC': ''},
    ]
    meta = parser_utils.aggregate_spotify_rows(rows)
    assert ('A', 'B') in meta
    ab = meta[('A', 'B')]
    assert ab['spotify_album_id'] == 'ALB1'
    assert ab['track_titles'] == ['t1', 't2']
    assert ab['track_isrcs'] == ['isrc1', 'isrc2']

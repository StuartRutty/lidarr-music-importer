import pytest

from scripts.universal_parser import apply_item_filters
from lib.csv_handler import ItemStatus


def make_item(artist, album, status=''):
    return {'artist': artist, 'album': album, 'status': status}


def test_status_new_token():
    items = [make_item('A', 'X', ''), make_item('B', 'Y', 'pending_refresh'), make_item('C', 'Z', 'error_connection')]
    filtered = apply_item_filters(items, status='new')
    assert len(filtered) == 1
    assert filtered[0]['artist'] == 'A'


def test_status_failed_token():
    items = [make_item('A', 'X', ''), make_item('B', 'Y', 'error_connection'), make_item('C', 'Z', 'already_monitored')]
    filtered = apply_item_filters(items, status='failed')
    # should include items with should_retry == True ('' and error_connection)
    artists = {i['artist'] for i in filtered}
    assert 'A' in artists
    assert 'B' in artists
    assert 'C' not in artists


def test_status_comma_list_and_exclude():
    items = [make_item('A', 'X', 'pending_refresh'), make_item('B', 'Y', 'error_connection'), make_item('C', 'Z', 'skip_no_musicbrainz')]
    filtered = apply_item_filters(items, status='pending_refresh,error_connection')
    assert len(filtered) == 2
    filtered2 = apply_item_filters(items, exclude_status='skip_no_musicbrainz')
    assert len(filtered2) == 2


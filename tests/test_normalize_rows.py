import csv
from pathlib import Path

from lib import parser_utils


def make_rows():
    return [
        {'artist': 'A', 'album': 'Foo (Deluxe)', 'status': 'pending'},
        {'artist': 'B', 'album': 'Bar', 'status': 'done'},
        {'artist': 'C', 'album': 'Baz (2015 Remaster)', 'status': 'pending'},
    ]


def test_normalize_rows_apply_changes():
    rows = make_rows()
    fieldnames = ['artist', 'album', 'status']
    new_rows, new_fieldnames, stats = parser_utils.normalize_rows(rows, fieldnames, status_filter=None, apply_changes=True)
    assert stats['total_rows'] == 3
    assert stats['changed_rows'] == 2
    # Ensure original_album column present
    assert 'original_album' in new_fieldnames
    assert new_rows[0]['album'] == 'Foo'
    assert new_rows[2]['album'] == 'Baz'


def test_normalize_rows_no_apply():
    rows = make_rows()
    fieldnames = ['artist', 'album', 'status']
    new_rows, new_fieldnames, stats = parser_utils.normalize_rows(rows, fieldnames, status_filter=None, apply_changes=False)
    assert stats['changed_rows'] == 2
    # original rows unchanged
    assert new_rows[0]['album'] == 'Foo (Deluxe)'

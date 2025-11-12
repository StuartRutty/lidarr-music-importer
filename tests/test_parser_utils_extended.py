import csv
import json
from pathlib import Path

import pytest

from lib import parser_utils


def test_parse_spotify_export_and_filter(tmp_path: Path):
    p = tmp_path / 'sample.csv'
    # Create a header and rows with indices used by the parser (artist at 3, album at 5, album artist at 7)
    rows = [
        ['c0', 'c1', 'c2', 'Artist Name', 'c4', 'Album Name', 'c6', 'Album Artist'],
        ['a0', 'a1', 'a2', 'Artist A', 'a4', 'Album X', 'a6', ''],
        ['b0', 'b1', 'b2', 'Artist A', 'b4', 'Album X', 'b6', ''],
        ['c0', 'c1', 'c2', 'Artist A', 'c4', 'Album Y', 'c6', 'Artist A'],
        ['d0', 'd1', 'd2', 'Artist B', 'd4', 'Album Z', 'd6', 'Artist B'],
    ]

    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow(r)

    artist_albums, artist_totals = parser_utils.parse_spotify_export(str(p))
    # Artist A should have Album X (2 tracks) and Album Y (1)
    assert 'Artist A' in artist_albums
    assert artist_albums['Artist A']['Album X'] == 2
    assert artist_totals['Artist A'] == 3

    # Filtering should remove Artist A's Album Y if min_album_songs=2
    filtered = parser_utils.filter_artist_albums(artist_albums, artist_totals, min_artist_songs=1, min_album_songs=2)
    assert 'Album X' in filtered['Artist A']
    assert 'Album Y' not in filtered['Artist A']


def test_generate_artist_album_output_and_json(tmp_path: Path):
    filtered = {
        'Artist A': {'Album X': 2},
        'Artist B': {'Album Z': 1}
    }
    out_csv = tmp_path / 'out.csv'
    out_json = tmp_path / 'out.json'
    parser_utils.generate_artist_album_output(filtered, str(out_csv), str(out_json))

    assert out_csv.exists()
    with out_csv.open('r', encoding='utf-8') as f:
        lines = [r.strip() for r in f.readlines()]
    assert lines[0].lower().startswith('artist')
    # Two data lines plus header
    assert len(lines) == 3

    assert out_json.exists()
    j = json.loads(out_json.read_text(encoding='utf-8'))
    assert j['metadata']['total_artists'] == 2


@pytest.mark.parametrize(
    'input_title,expected',
    [
        ('Drip Season 3 (Deluxe)', 'Drip Season 3'),
        ('Good Kid M.A.A.D City (Vol. 2)', 'Good Kid M.A.A.D City (Vol. 2)'),
        ('The Life Of Pablo [Explicit]', 'The Life Of Pablo'),
        ('Album (2015 Remaster)', 'Album'),
    ],
)
def test_normalize_album_title(input_title, expected):
    out = parser_utils.normalize_album_title(input_title)
    assert out == expected


def test_needs_normalization_and_clean_text():
    assert parser_utils.needs_normalization('Some Album (Deluxe)')
    assert not parser_utils.needs_normalization('Some Album')
    assert parser_utils.clean_text('[Artist]') == 'Artist'
    assert parser_utils.clean_text('A  B') == 'A B'

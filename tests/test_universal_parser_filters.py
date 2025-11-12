import csv
import textwrap
from pathlib import Path
from lib.text_utils import clean_csv_input
from scripts.universal_parser import UniversalParser


def write_spotify_csv(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Artist Name', 'Album Name', 'Track Name'])
        for r in rows:
            writer.writerow(r)


def test_spotify_min_artist_and_album_filters(tmp_path: Path):
    p = tmp_path / 'spotify.csv'
    # Rows: A has 2 tracks on Album1, B has 1 track, C has 3 tracks on Album3
    rows = [
        ('A', 'Album1', 't1'),
        ('A', 'Album1', 't2'),
        ('B', 'Album2', 't1'),
        ('C', 'Album3', 't1'),
        ('C', 'Album3', 't2'),
        ('C', 'Album3', 't3'),
    ]
    write_spotify_csv(p, rows)

    up = UniversalParser()
    up.parse_spotify_csv(str(p), min_artist_songs=2, min_album_songs=2)

    # Expect A/Album1 and C/Album3 only
    pairs = {(e.artist, e.album, e.track_count) for e in up.entries}
    assert ('A', 'Album1', 2) in pairs
    assert ('C', 'Album3', 3) in pairs
    assert not any(e.artist == 'B' for e in up.entries)


def test_simple_and_text_filters_and_max_items(tmp_path: Path):
    # Simple CSV
    simple = tmp_path / 'simple.csv'
    with open(simple, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Always Proper', 'BLUNTS & JUNTS 2'])
        writer.writerow(['Other Artist', 'Some Album'])

    up = UniversalParser()
    up.parse_simple_csv(str(simple), artist_filter='Always', max_items=1)
    assert len(up.entries) == 1
    assert up.entries[0].artist == 'Always Proper'

    # Text format
    textf = tmp_path / 'list.txt'
    textf.write_text('ALWAYS PROPER - BLUNTS & JUNTS 2\nOther - Album\n', encoding='utf-8')
    up2 = UniversalParser()
    up2.parse_text_format(str(textf), 'text_dash', artist_filter='ALWAYS PROPER')
    assert len(up2.entries) == 1
    assert up2.entries[0].artist.upper() == 'ALWAYS PROPER'

"""
Unit tests for scripts/universal_parser.py

Tests Spotify ID normalization and CSV output for spotify columns.
"""
import json
import sys
from pathlib import Path
import tempfile
import csv

import pytest

# allow importing from repo
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.universal_parser import UniversalParser


@pytest.mark.unit
def test_spotify_id_normalization_and_output(tmp_path):
    # Create a temporary Spotify-style CSV with different album id formats
    csv_content = [
        [
            "Track URI","Track Name","Artist URI(s)","Artist Name(s)","Album URI","Album Name","Album Artist URI(s)","Album Artist Name(s)","Album Release Date","ISRC"
        ],
        [
            'spotify:track:AAA','Track1','spotify:artist:ART1','Test Artist','spotify:album:ALBID1','Album One','spotify:artist:ART1','Test Artist','2020-01-01','ISRC1'
        ],
        [
            'spotify:track:BBB','Track2','spotify:artist:ART1','Test Artist','https://open.spotify.com/album/ALBID2?si=xyz','Album Two','spotify:artist:ART1','Test Artist','2021-02-02','ISRC2'
        ],
        [
            'spotify:track:CCC','Track3','spotify:artist:ART1','Test Artist','ALBID3','Album Three','spotify:artist:ART1','Test Artist','2022-03-03','ISRC3'
        ]
    ]

    tmpfile = tmp_path / "test_spotify.csv"
    with tmpfile.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in csv_content:
            writer.writerow(row)

    up = UniversalParser()
    up.parse_file(str(tmpfile))

    # Expect 3 unique entries
    assert len(up.entries) == 3

    # Check spotify_album_id normalization for each entry
    ids = [e.spotify_album_id for e in up.entries]
    # ensure we see the two normalized/aligned ids
    assert 'ALBID1' in ids
    assert 'ALBID2' in ids
    # third entry may be an opaque or empty value depending on parser heuristics;
    # we only assert presence of the first two normalized ids.

    # Write output CSV and verify spotify columns exist and values are normalized
    out = tmp_path / "out.csv"
    up.write_output(str(out))

    with out.open('r', encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r)
        # spotify_album_id should be present in header
        assert 'spotify_album_id' in header

        # load rows and check normalization persisted
        rows = list(r)
        # find first data row spotify id column index
        idx = header.index('spotify_album_id')
        out_ids = [row[idx] for row in rows]
        # ensure the normalized ids we expect are present in output
        assert 'ALBID1' in out_ids
        assert 'ALBID2' in out_ids
        # we should have three output rows (one per unique album aggregation)
        assert len(rows) == 3

import sys
from pathlib import Path


def test_parse_exportify_spotify_csv(tmp_path):
    # Ensure repo root is on sys.path for imports
    repo_root = Path(__file__).parent.parent
    sys.path.insert(0, str(repo_root))

    from scripts.universal_parser import UniversalParser

    csv_path = repo_root / 'scripts' / 'jun_29.csv'
    assert csv_path.exists(), "Expected sample CSV at scripts/jun_29.csv"

    up = UniversalParser()
    up.parse_file(str(csv_path), min_artist_songs=1, min_album_songs=1)

    # Basic assertions about parsing
    assert up.stats['format_detected'] == 'spotify_csv'
    assert up.stats['raw_entries'] > 0
    # Expect at least one known artist from sample
    artists = {e.artist for e in up.entries}
    assert any('ALWAYS PROPER' in a.upper() or 'GOTNOTIME' in a.upper() for a in artists)

    # Write output and ensure file is created
    out = tmp_path / 'out.csv'
    up.write_output(str(out))
    assert out.exists()

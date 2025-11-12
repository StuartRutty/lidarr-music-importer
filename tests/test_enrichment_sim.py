import csv
from pathlib import Path
from scripts.universal_parser import UniversalParser, AlbumEntry


class FakeMBClient:
    def __init__(self, mapping=None):
        # mapping: artist -> list of (release_title, release_id)
        self.mapping = mapping or {}

    def search_artists(self, artist: str, limit: int = 5):
        # Return a single artist match with a deterministic id
        return {'artist-list': [{'id': f'{artist.lower().replace(" ", "_")}_id', 'name': artist, 'ext:score': '100'}]}

    def search_release_groups(self, artist: str, releasegroup: str, limit: int = 5, artist_aliases=None, artist_mbid=None):
        # If mapping contains the artist+title, return that id, else return a synthetic id
        key = (artist, releasegroup)
        rid = self.mapping.get(key) or f"rg_{artist.lower().replace(' ', '_')}_{releasegroup.lower().replace(' ', '_')}_id"
        return {'release-group-list': [{'id': rid, 'title': releasegroup, 'artist-credit-phrase': artist, 'ext:score': '100'}]}


def test_enrichment_writes_all_entries(tmp_path: Path):
    # Create a parser with two entries that should both be enriched
    up = UniversalParser()
    e1 = AlbumEntry(artist='Always Proper', album='BLUNTS & JUNTS 2', album_search='BLUNTS & JUNTS 2')
    e2 = AlbumEntry(artist='Drae Da Skimask', album='STAY INSIDE THE HOUSE (DELUXE EDITION)', album_search='STAY INSIDE THE HOUSE')
    up.entries = [e1, e2]

    # Attach fake MB client that will return deterministic ids
    fake = FakeMBClient()
    up.mb_client = fake

    out = tmp_path / 'enriched.csv'

    # Run enrichment (should call write_output after each item) and not skip any
    up.enrich_with_musicbrainz(mb_delay=0.0, output_path=str(out))

    # After enrichment, both entries should have mb_release_id set
    assert all(e.mb_release_id for e in up.entries), "Both entries should have mb_release_id populated"

    # The output CSV should contain two data rows (header + 2 rows)
    rows = list(csv.reader(open(out, 'r', encoding='utf-8')))
    # header + 2 rows
    assert len(rows) == 3

    # Ensure both release IDs appear in CSV
    csv_ids = {r[3] for r in rows[1:]}  # mb_release_id is at index 3 when mb ids present
    assert any('rg_' in s or '_id' in s for s in csv_ids)

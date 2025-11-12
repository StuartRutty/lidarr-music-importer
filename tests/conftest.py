"""
Pytest fixtures for lidarr-music-importer tests

Provides common test data and mock objects for use across all test modules.
"""
import pytest
from pathlib import Path


@pytest.fixture
def sample_artists():
    """Sample artist names for testing normalization."""
    return [
        "Beyoncé",
        "Björk",
        "Sigur Rós",
        "!!!",
        "deadmau5",
        "WALK THE MOON",
        "The Beatles",
        "A Tribe Called Quest",
    ]


@pytest.fixture
def sample_albums():
    """Sample album titles with various formats."""
    return [
        "To Pimp a Butterfly",
        "OK Computer (Remastered)",
        "Abbey Road [Deluxe Edition]",
        "Rumours (Super Deluxe Edition)",
        "The Dark Side of the Moon",
        "Kind of Blue (Legacy Edition)",
        "Thriller (25th Anniversary Edition)",
        "A Love Supreme [Deluxe Edition]",
    ]


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing CSV handler."""
    return [
        {"artist": "Son Lux", "album": "Tomorrows I", "status": "pending"},
        {"artist": "Radiohead", "album": "OK Computer", "status": "completed"},
        {"artist": "Kendrick Lamar", "album": "DAMN.", "status": "failed"},
    ]


@pytest.fixture
def mock_musicbrainz_artist_response():
    """Mock MusicBrainz artist search API response."""
    return {
        "artists": [
            {
                "id": "test-mbid-123",
                "name": "Son Lux",
                "score": 100,
                "type": "Group",
                "disambiguation": "",
            }
        ]
    }


@pytest.fixture
def mock_musicbrainz_album_response():
    """Mock MusicBrainz release group search API response."""
    return {
        "release-groups": [
            {
                "id": "album-mbid-456",
                "title": "Tomorrows I",
                "primary-type": "Album",
                "first-release-date": "2021-07-09",
                "score": 100,
            }
        ]
    }


@pytest.fixture
def mock_lidarr_artist_response():
    """Mock Lidarr artist lookup API response."""
    return [
        {
            "artistName": "Son Lux",
            "foreignArtistId": "test-mbid-123",
            "id": 1,
            "monitored": True,
            "qualityProfileId": 1,
            "rootFolderPath": "/music",
        }
    ]


@pytest.fixture
def mock_lidarr_album_response():
    """Mock Lidarr album API response."""
    return [
        {
            "id": 1,
            "title": "Tomorrows I",
            "foreignAlbumId": "album-mbid-456",
            "monitored": True,
            "artistId": 1,
            "releaseDate": "2021-07-09",
        }
    ]


@pytest.fixture
def test_data_dir(tmp_path):
    """Create a temporary directory for test data."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_csv_file(test_data_dir):
    """Create a sample CSV file for testing."""
    csv_path = test_data_dir / "test_albums.csv"
    csv_content = """artist,album,status,mb_artist_id,mb_album_id,error_message
Son Lux,Tomorrows I,pending,,,
Radiohead,OK Computer,completed,test-artist-1,test-album-1,
Kendrick Lamar,DAMN.,failed,,,Artist not found in MusicBrainz
"""
    csv_path.write_text(csv_content, encoding="utf-8")
    return csv_path


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a concise, one-line summary at the end of the test run.

    This avoids creating any files and keeps CI/pr output easy to scan.
    """
    stats = getattr(terminalreporter, "stats", {})

    def _count(key):
        return len(stats.get(key, [])) if stats.get(key) is not None else 0

    passed = _count('passed')
    failed = _count('failed')
    skipped = _count('skipped')
    xfailed = _count('xfailed')
    xpassed = _count('xpassed')
    errors = _count('error')

    total = passed + failed + skipped + xfailed + xpassed + errors

    # Write a compact summary line to the terminal (no files written)
    terminalreporter.write_sep("=", "pytest summary")
    terminalreporter.write_line(
        f"Total: {total}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}  "
        f"Errors: {errors}  xfailed: {xfailed}  xpassed: {xpassed}"
    )

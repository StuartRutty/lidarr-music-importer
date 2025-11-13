"""
Pytest fixtures for lidarr-music-importer tests

Provides common test data and mock objects for use across all test modules.
"""
import pytest
from pathlib import Path
import os
import shutil
import webbrowser


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


def pytest_ignore_collect(collection_path, config):
    """Ignore duplicate/variant test files that were left in the tests/ dir.

    Newer pytest versions pass a pathlib.Path as `collection_path`.
    We accept that and convert to string for matching. This hook returns True
    for filenames matching duplicate patterns so pytest won't collect them.
    """
    try:
        p = str(collection_path)
    except Exception:
        p = repr(collection_path)

    import re
    if re.search(r"(_combined|_extra|_more|_json)\.py$", p):
        return True
    return False


@pytest.fixture(scope="session", autouse=True)
def cleanup_webui_dirs():
    """Ensure `webui/uploads` and `webui/processed` are clean before and after tests.

    This fixture runs automatically for the test session. It creates the directories
    if missing and removes any files created during tests to avoid leaving artifacts
    in the repository working tree.
    """
    repo_root = Path(__file__).resolve().parent.parent
    uploads_dir = repo_root / "webui" / "uploads"
    processed_dir = repo_root / "webui" / "processed"
    jobs_dir = repo_root / "webui" / "jobs"

    def _ensure_and_clear(dirpath: Path):
        if dirpath.exists():
            for child in dirpath.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                except Exception:
                    # Best-effort cleanup; tests should not fail due to cleanup errors
                    pass
        else:
            dirpath.mkdir(parents=True, exist_ok=True)

    # Clean before tests
    _ensure_and_clear(uploads_dir)
    _ensure_and_clear(processed_dir)
    _ensure_and_clear(jobs_dir)

    yield

    # Clean after tests
    _ensure_and_clear(uploads_dir)
    _ensure_and_clear(processed_dir)
    _ensure_and_clear(jobs_dir)


@pytest.fixture(autouse=True)
def no_external_opens(monkeypatch):
    """Prevent tests from opening external applications or URLs.

    Some environments (especially on Windows with certain editor integrations)
    may react to attempts to open files/URLs by focusing the editor or starting
    external programs. During tests we replace those calls with no-op functions.
    """
    # Patch webbrowser.open to a harmless no-op
    monkeypatch.setattr(webbrowser, 'open', lambda *a, **k: None)

    # Patch os.startfile on Windows if present
    if hasattr(os, 'startfile'):
        monkeypatch.setattr(os, 'startfile', lambda *a, **k: None)

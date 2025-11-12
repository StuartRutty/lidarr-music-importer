"""Top-level convenience exports for the `lib` package.

Importing from `lib` directly is a small convenience for scripts and tests.
Keep this module small: it should only expose stable, well-tested helpers.
"""
from .models import AlbumEntry
from .parser_utils import (
    normalize_spotify_id,
    aggregate_spotify_rows,
    parse_spotify_export,
    filter_artist_albums,
    generate_artist_album_output,
    normalize_album_title,
    needs_normalization,
    clean_text,
    normalize_rows,
    process_csv,
    read_csv_to_rows,
    write_rows_to_csv,
)
from .io_utils import create_backup
from .musicbrainz_client import MusicBrainzClient

__all__ = [
    'AlbumEntry',
    'normalize_spotify_id',
    'aggregate_spotify_rows',
    'parse_spotify_export',
    'filter_artist_albums',
    'generate_artist_album_output',
    'normalize_album_title',
    'needs_normalization',
    'clean_text',
    'normalize_rows',
    'process_csv',
    'read_csv_to_rows',
    'write_rows_to_csv',
    'create_backup',
    'MusicBrainzClient',
]
"""
Lidarr Music Importer Library

Core modules for interacting with Lidarr and MusicBrainz APIs.
"""

__version__ = "2.0.0"
__author__ = "Lidarr Music Importer Contributors"

from .config_manager import Config

__all__ = ['Config']

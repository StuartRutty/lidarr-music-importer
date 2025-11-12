"""
Custom exception hierarchy for Lidarr music importer.

This module defines domain-specific exceptions to provide better
error handling and more informative error messages throughout the application.
"""


class LidarrImporterError(Exception):
    """Base exception for all Lidarr importer errors."""
    pass


class APIError(LidarrImporterError):
    """Base class for all API-related errors."""
    pass


class LidarrAPIError(APIError):
    """Error communicating with Lidarr API."""
    pass


class MusicBrainzAPIError(APIError):
    """Error communicating with MusicBrainz API."""
    pass


class RateLimitError(APIError):
    """API rate limit exceeded."""
    pass


class DataError(LidarrImporterError):
    """Base class for data-related errors."""
    pass


class ArtistNotFoundError(DataError):
    """Artist not found in MusicBrainz or Lidarr."""
    pass


class AlbumNotFoundError(DataError):
    """Album not found in MusicBrainz or Lidarr."""
    pass


class ValidationError(DataError):
    """Data validation failed."""
    pass


class ConfigurationError(LidarrImporterError):
    """Configuration error (missing or invalid settings)."""
    pass

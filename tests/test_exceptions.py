"""
Tests for Custom Exception Classes

Tests the exception hierarchy and ensures proper inheritance and behavior.
"""

import pytest
from lib.exceptions import (
    LidarrImporterError,
    APIError,
    LidarrAPIError,
    MusicBrainzAPIError,
    RateLimitError,
    DataError,
    ArtistNotFoundError,
    AlbumNotFoundError,
    ValidationError,
    ConfigurationError
)


class TestExceptionHierarchy:
    """Test the exception inheritance hierarchy."""
    
    def test_base_exception_inherits_from_exception(self):
        """Test that base error inherits from Exception."""
        assert issubclass(LidarrImporterError, Exception)
    
    def test_api_error_inherits_from_base(self):
        """Test that APIError inherits from base."""
        assert issubclass(APIError, LidarrImporterError)
        assert issubclass(APIError, Exception)
    
    def test_lidarr_api_error_inherits_from_api_error(self):
        """Test that LidarrAPIError inherits from APIError."""
        assert issubclass(LidarrAPIError, APIError)
        assert issubclass(LidarrAPIError, LidarrImporterError)
        assert issubclass(LidarrAPIError, Exception)
    
    def test_musicbrainz_api_error_inherits_from_api_error(self):
        """Test that MusicBrainzAPIError inherits from APIError."""
        assert issubclass(MusicBrainzAPIError, APIError)
        assert issubclass(MusicBrainzAPIError, LidarrImporterError)
        assert issubclass(MusicBrainzAPIError, Exception)
    
    def test_rate_limit_error_inherits_from_api_error(self):
        """Test that RateLimitError inherits from APIError."""
        assert issubclass(RateLimitError, APIError)
        assert issubclass(RateLimitError, LidarrImporterError)
        assert issubclass(RateLimitError, Exception)
    
    def test_data_error_inherits_from_base(self):
        """Test that DataError inherits from base."""
        assert issubclass(DataError, LidarrImporterError)
        assert issubclass(DataError, Exception)
    
    def test_artist_not_found_error_inherits_from_data_error(self):
        """Test that ArtistNotFoundError inherits from DataError."""
        assert issubclass(ArtistNotFoundError, DataError)
        assert issubclass(ArtistNotFoundError, LidarrImporterError)
        assert issubclass(ArtistNotFoundError, Exception)
    
    def test_album_not_found_error_inherits_from_data_error(self):
        """Test that AlbumNotFoundError inherits from DataError."""
        assert issubclass(AlbumNotFoundError, DataError)
        assert issubclass(AlbumNotFoundError, LidarrImporterError)
        assert issubclass(AlbumNotFoundError, Exception)
    
    def test_validation_error_inherits_from_data_error(self):
        """Test that ValidationError inherits from DataError."""
        assert issubclass(ValidationError, DataError)
        assert issubclass(ValidationError, LidarrImporterError)
        assert issubclass(ValidationError, Exception)
    
    def test_configuration_error_inherits_from_base(self):
        """Test that ConfigurationError inherits from base."""
        assert issubclass(ConfigurationError, LidarrImporterError)
        assert issubclass(ConfigurationError, Exception)


class TestExceptionRaising:
    """Test raising and catching exceptions."""
    
    def test_raise_base_exception(self):
        """Test raising base exception."""
        with pytest.raises(LidarrImporterError, match="test error"):
            raise LidarrImporterError("test error")
    
    def test_raise_api_error(self):
        """Test raising APIError."""
        with pytest.raises(APIError, match="API failed"):
            raise APIError("API failed")
    
    def test_raise_lidarr_api_error(self):
        """Test raising LidarrAPIError."""
        with pytest.raises(LidarrAPIError, match="Lidarr connection failed"):
            raise LidarrAPIError("Lidarr connection failed")
    
    def test_raise_musicbrainz_api_error(self):
        """Test raising MusicBrainzAPIError."""
        with pytest.raises(MusicBrainzAPIError, match="MusicBrainz timeout"):
            raise MusicBrainzAPIError("MusicBrainz timeout")
    
    def test_raise_rate_limit_error(self):
        """Test raising RateLimitError."""
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            raise RateLimitError("Rate limit exceeded")
    
    def test_raise_data_error(self):
        """Test raising DataError."""
        with pytest.raises(DataError, match="Invalid data"):
            raise DataError("Invalid data")
    
    def test_raise_artist_not_found_error(self):
        """Test raising ArtistNotFoundError."""
        with pytest.raises(ArtistNotFoundError, match="Artist not found"):
            raise ArtistNotFoundError("Artist not found")
    
    def test_raise_album_not_found_error(self):
        """Test raising AlbumNotFoundError."""
        with pytest.raises(AlbumNotFoundError, match="Album not found"):
            raise AlbumNotFoundError("Album not found")
    
    def test_raise_validation_error(self):
        """Test raising ValidationError."""
        with pytest.raises(ValidationError, match="Validation failed"):
            raise ValidationError("Validation failed")
    
    def test_raise_configuration_error(self):
        """Test raising ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Config missing"):
            raise ConfigurationError("Config missing")


class TestExceptionCatching:
    """Test catching exceptions at different levels."""
    
    def test_catch_lidarr_api_error_as_api_error(self):
        """Test catching specific error as parent type."""
        with pytest.raises(APIError):
            raise LidarrAPIError("test")
    
    def test_catch_lidarr_api_error_as_base(self):
        """Test catching specific error as base type."""
        with pytest.raises(LidarrImporterError):
            raise LidarrAPIError("test")
    
    def test_catch_musicbrainz_api_error_as_api_error(self):
        """Test catching MusicBrainz error as APIError."""
        with pytest.raises(APIError):
            raise MusicBrainzAPIError("test")
    
    def test_catch_rate_limit_as_api_error(self):
        """Test catching rate limit as APIError."""
        with pytest.raises(APIError):
            raise RateLimitError("test")
    
    def test_catch_artist_not_found_as_data_error(self):
        """Test catching artist error as DataError."""
        with pytest.raises(DataError):
            raise ArtistNotFoundError("test")
    
    def test_catch_album_not_found_as_data_error(self):
        """Test catching album error as DataError."""
        with pytest.raises(DataError):
            raise AlbumNotFoundError("test")
    
    def test_catch_validation_as_data_error(self):
        """Test catching validation error as DataError."""
        with pytest.raises(DataError):
            raise ValidationError("test")
    
    def test_catch_any_error_as_base(self):
        """Test that all custom errors can be caught as base."""
        errors = [
            LidarrAPIError("test"),
            MusicBrainzAPIError("test"),
            RateLimitError("test"),
            ArtistNotFoundError("test"),
            AlbumNotFoundError("test"),
            ValidationError("test"),
            ConfigurationError("test"),
        ]
        
        for error in errors:
            with pytest.raises(LidarrImporterError):
                raise error


class TestExceptionMessages:
    """Test exception messages and string representation."""
    
    def test_exception_stores_message(self):
        """Test that exceptions store their message."""
        error = LidarrAPIError("Custom error message")
        assert str(error) == "Custom error message"
    
    def test_exception_with_formatted_message(self):
        """Test exceptions with formatted strings."""
        artist = "Taylor Swift"
        error = ArtistNotFoundError(f"Artist not found: {artist}")
        assert "Taylor Swift" in str(error)
    
    def test_exception_with_multiline_message(self):
        """Test exceptions with multiline messages."""
        message = "Error occurred:\n- Line 1\n- Line 2"
        error = ValidationError(message)
        assert "Line 1" in str(error)
        assert "Line 2" in str(error)
    
    def test_exception_with_empty_message(self):
        """Test exceptions can be raised with empty message."""
        error = ConfigurationError()
        # Should not crash
        str(error)


class TestExceptionUseCases:
    """Test realistic use cases for exceptions."""
    
    def test_catch_specific_then_raise_generic(self):
        """Test catching specific error and re-raising as generic."""
        def risky_operation():
            raise LidarrAPIError("Connection failed")
        
        with pytest.raises(APIError):
            try:
                risky_operation()
            except LidarrAPIError as e:
                # Could log or handle specific error here
                raise APIError(f"API operation failed: {e}")
    
    def test_distinguish_between_api_errors(self):
        """Test distinguishing between different API errors."""
        def check_error_type(error):
            if isinstance(error, LidarrAPIError):
                return "lidarr"
            elif isinstance(error, MusicBrainzAPIError):
                return "musicbrainz"
            elif isinstance(error, RateLimitError):
                return "rate_limit"
            else:
                return "unknown"
        
        assert check_error_type(LidarrAPIError("test")) == "lidarr"
        assert check_error_type(MusicBrainzAPIError("test")) == "musicbrainz"
        assert check_error_type(RateLimitError("test")) == "rate_limit"
    
    def test_exception_with_additional_context(self):
        """Test adding context to exceptions."""
        artist = "Unknown Artist"
        album = "Unknown Album"
        
        error = AlbumNotFoundError(
            f"Album '{album}' by '{artist}' not found in MusicBrainz. "
            f"Check spelling and try again."
        )
        
        assert "Unknown Album" in str(error)
        assert "Unknown Artist" in str(error)
        assert "MusicBrainz" in str(error)


class TestExceptionGrouping:
    """Test exception grouping and categorization."""
    
    def test_all_api_errors_catchable_together(self):
        """Test that all API-related errors can be caught together."""
        api_errors = [
            LidarrAPIError("test"),
            MusicBrainzAPIError("test"),
            RateLimitError("test"),
        ]
        
        for error in api_errors:
            with pytest.raises(APIError):
                raise error
    
    def test_all_data_errors_catchable_together(self):
        """Test that all data-related errors can be caught together."""
        data_errors = [
            ArtistNotFoundError("test"),
            AlbumNotFoundError("test"),
            ValidationError("test"),
        ]
        
        for error in data_errors:
            with pytest.raises(DataError):
                raise error
    
    def test_configuration_error_separate_from_others(self):
        """Test that ConfigurationError is not an API or Data error."""
        error = ConfigurationError("test")
        
        assert not isinstance(error, APIError)
        assert not isinstance(error, DataError)
        assert isinstance(error, LidarrImporterError)


class TestExceptionBehavior:
    """Test exception behavior and attributes."""
    
    def test_exception_is_instance_of_exception(self):
        """Test that custom exceptions are instances of Exception."""
        errors = [
            LidarrImporterError(),
            LidarrAPIError(),
            MusicBrainzAPIError(),
            ArtistNotFoundError(),
            ConfigurationError(),
        ]
        
        for error in errors:
            assert isinstance(error, Exception)
    
    def test_exception_args_attribute(self):
        """Test that exception args are accessible."""
        message = "Test error message"
        error = LidarrAPIError(message)
        
        assert error.args[0] == message
    
    def test_exception_equality(self):
        """Test exception equality based on message."""
        error1 = LidarrAPIError("same message")
        error2 = LidarrAPIError("same message")
        error3 = LidarrAPIError("different message")
        
        # Exceptions are compared by identity, not message
        assert error1 is not error2
        assert error1 is not error3
        # But their messages are equal
        assert str(error1) == str(error2)
        assert str(error1) != str(error3)

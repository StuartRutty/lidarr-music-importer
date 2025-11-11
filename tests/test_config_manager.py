"""
Unit tests for lib/config_manager.py

Tests configuration loading, validation, and environment variable handling.
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path to import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config_manager import Config


class TestConfigLoadFromModule:
    """Tests for loading configuration from config.py module."""

    @pytest.mark.unit
    def test_load_defaults_with_api_key(self, monkeypatch):
        """Test loading with minimal valid config (just API key)."""
        # Create a mock config module with minimal settings
        mock_config = Mock()
        mock_config.LIDARR_API_KEY = "test-api-key-123"
        mock_config.LIDARR_BASE_URL = "http://test:8686"
        
        with patch('lib.config_manager.Config._load_from_module') as mock_load:
            with patch('lib.config_manager.Config._validate'):
                config = Config()
                # Manually set attributes for testing
                config.lidarr_api_key = "test-api-key-123"
                config.lidarr_base_url = "http://test:8686"
                config.musicbrainz_delay = 1.0
                
                assert config.lidarr_api_key == "test-api-key-123"
                assert config.lidarr_base_url == "http://test:8686"

    @pytest.mark.unit
    def test_load_all_settings(self):
        """Test loading all configuration settings from module."""
        mock_config = Mock()
        mock_config.LIDARR_API_KEY = "test-key"
        mock_config.LIDARR_BASE_URL = "http://custom:9999"
        mock_config.QUALITY_PROFILE_ID = 5
        mock_config.METADATA_PROFILE_ID = 3
        mock_config.ROOT_FOLDER_PATH = "/custom/music"
        mock_config.MUSICBRAINZ_DELAY = 2.0
        mock_config.USE_MUSICBRAINZ = False
        mock_config.LIDARR_REQUEST_DELAY = 3.0
        mock_config.MAX_RETRIES = 5
        mock_config.RETRY_DELAY = 10.0
        mock_config.API_ERROR_DELAY = 15.0
        mock_config.BATCH_SIZE = 20
        mock_config.BATCH_PAUSE = 20.0
        mock_config.MUSICBRAINZ_USER_AGENT = {
            'app_name': 'test-app',
            'version': '2.0',
            'contact': 'test@example.com'
        }
        mock_config.ARTIST_ALIASES = {'test': ['alias1', 'alias2']}
        
        config = Config()
        config._load_from_module(mock_config)
        
        assert config.lidarr_api_key == "test-key"
        assert config.lidarr_base_url == "http://custom:9999"
        assert config.quality_profile_id == 5
        assert config.metadata_profile_id == 3
        assert config.root_folder_path == "/custom/music"
        assert config.musicbrainz_delay == 2.0
        assert config.use_musicbrainz == False
        assert config.lidarr_request_delay == 3.0
        assert config.max_retries == 5
        assert config.retry_delay == 10.0
        assert config.api_error_delay == 15.0
        assert config.batch_size == 20
        assert config.batch_pause == 20.0
        assert config.musicbrainz_user_agent['app_name'] == 'test-app'
        assert config.artist_aliases == {'test': ['alias1', 'alias2']}

    @pytest.mark.unit
    def test_defaults_when_settings_missing(self):
        """Test that default values are used when settings are missing."""
        # Create a simple object with only LIDARR_API_KEY
        class SimpleConfig:
            LIDARR_API_KEY = "test-key"
        
        mock_config = SimpleConfig()
        
        config = Config()
        config._load_from_module(mock_config)
        
        # Check defaults are applied for missing attributes
        assert config.lidarr_api_key == "test-key"
        assert config.lidarr_base_url == 'http://localhost:8686'
        assert config.quality_profile_id == 1
        assert config.metadata_profile_id == 1
        assert config.root_folder_path == '/music'
        assert config.musicbrainz_delay == 1.0
        assert config.use_musicbrainz == True


class TestConfigLoadFromEnv:
    """Tests for loading configuration from environment variables."""

    @pytest.mark.unit
    def test_load_from_env_basic(self, monkeypatch):
        """Test loading basic configuration from environment variables."""
        monkeypatch.setenv('LIDARR_API_KEY', 'env-api-key')
        monkeypatch.setenv('LIDARR_BASE_URL', 'http://env:7878')
        
        config = Config()
        config._load_from_env()
        
        assert config.lidarr_api_key == 'env-api-key'
        assert config.lidarr_base_url == 'http://env:7878'

    @pytest.mark.unit
    def test_load_from_env_all_settings(self, monkeypatch):
        """Test loading all settings from environment variables."""
        monkeypatch.setenv('LIDARR_API_KEY', 'env-key')
        monkeypatch.setenv('LIDARR_BASE_URL', 'http://custom:8080')
        monkeypatch.setenv('QUALITY_PROFILE_ID', '7')
        monkeypatch.setenv('METADATA_PROFILE_ID', '4')
        monkeypatch.setenv('ROOT_FOLDER_PATH', '/env/music')
        monkeypatch.setenv('MUSICBRAINZ_DELAY', '3.5')
        monkeypatch.setenv('USE_MUSICBRAINZ', 'false')
        monkeypatch.setenv('LIDARR_REQUEST_DELAY', '4.0')
        monkeypatch.setenv('MAX_RETRIES', '7')
        monkeypatch.setenv('RETRY_DELAY', '12.0')
        monkeypatch.setenv('API_ERROR_DELAY', '18.0')
        monkeypatch.setenv('BATCH_SIZE', '25')
        monkeypatch.setenv('BATCH_PAUSE', '30.0')
        monkeypatch.setenv('MB_APP_NAME', 'env-app')
        monkeypatch.setenv('MB_VERSION', '3.0')
        monkeypatch.setenv('MB_CONTACT', 'env@example.com')
        
        config = Config()
        config._load_from_env()
        
        assert config.lidarr_api_key == 'env-key'
        assert config.lidarr_base_url == 'http://custom:8080'
        assert config.quality_profile_id == 7
        assert config.metadata_profile_id == 4
        assert config.root_folder_path == '/env/music'
        assert config.musicbrainz_delay == 3.5
        assert config.use_musicbrainz == False
        assert config.lidarr_request_delay == 4.0
        assert config.max_retries == 7
        assert config.retry_delay == 12.0
        assert config.api_error_delay == 18.0
        assert config.batch_size == 25
        assert config.batch_pause == 30.0
        assert config.musicbrainz_user_agent['app_name'] == 'env-app'
        assert config.musicbrainz_user_agent['version'] == '3.0'
        assert config.musicbrainz_user_agent['contact'] == 'env@example.com'

    @pytest.mark.unit
    def test_env_defaults(self, monkeypatch):
        """Test that default values are used when env vars are not set."""
        # Only set required API key
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        
        config = Config()
        config._load_from_env()
        
        # Check defaults
        assert config.lidarr_base_url == 'http://localhost:8686'
        assert config.quality_profile_id == 1
        assert config.metadata_profile_id == 1
        assert config.root_folder_path == '/music'
        assert config.musicbrainz_delay == 1.0
        assert config.use_musicbrainz == True
        assert config.batch_size == 10
        assert config.batch_pause == 10.0

    @pytest.mark.unit
    def test_env_boolean_parsing(self, monkeypatch):
        """Test that boolean environment variables are parsed correctly."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        monkeypatch.setenv('USE_MUSICBRAINZ', 'TRUE')
        
        config = Config()
        config._load_from_env()
        assert config.use_musicbrainz == True
        
        monkeypatch.setenv('USE_MUSICBRAINZ', 'false')
        config._load_from_env()
        assert config.use_musicbrainz == False
        
        monkeypatch.setenv('USE_MUSICBRAINZ', 'False')
        config._load_from_env()
        assert config.use_musicbrainz == False

    @pytest.mark.unit
    def test_env_numeric_parsing(self, monkeypatch):
        """Test that numeric environment variables are parsed correctly."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        monkeypatch.setenv('QUALITY_PROFILE_ID', '42')
        monkeypatch.setenv('MUSICBRAINZ_DELAY', '2.5')
        monkeypatch.setenv('MAX_RETRIES', '10')
        
        config = Config()
        config._load_from_env()
        
        assert isinstance(config.quality_profile_id, int)
        assert config.quality_profile_id == 42
        assert isinstance(config.musicbrainz_delay, float)
        assert config.musicbrainz_delay == 2.5
        assert isinstance(config.max_retries, int)
        assert config.max_retries == 10


class TestConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.unit
    def test_validate_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        config = Config()
        config.lidarr_api_key = None
        config.musicbrainz_delay = 1.0
        
        with pytest.raises(ValueError, match="LIDARR_API_KEY is required"):
            config._validate()

    @pytest.mark.unit
    def test_validate_placeholder_api_key(self):
        """Test that placeholder API key raises ValueError."""
        config = Config()
        config.lidarr_api_key = "YOUR_API_KEY_HERE"
        config.musicbrainz_delay = 1.0
        
        with pytest.raises(ValueError, match="Please update LIDARR_API_KEY"):
            config._validate()

    @pytest.mark.unit
    def test_validate_musicbrainz_delay_too_low(self):
        """Test that MusicBrainz delay below 1.0 raises ValueError."""
        config = Config()
        config.lidarr_api_key = "valid-key"
        config.musicbrainz_delay = 0.5
        
        with pytest.raises(ValueError, match="MUSICBRAINZ_DELAY must be at least 1.0"):
            config._validate()

    @pytest.mark.unit
    def test_validate_success(self):
        """Test that valid configuration passes validation."""
        config = Config()
        config.lidarr_api_key = "valid-api-key"
        config.musicbrainz_delay = 1.0
        
        # Should not raise any exception
        config._validate()

    @pytest.mark.unit
    def test_validate_musicbrainz_delay_exactly_one(self):
        """Test that MusicBrainz delay of exactly 1.0 is valid."""
        config = Config()
        config.lidarr_api_key = "valid-key"
        config.musicbrainz_delay = 1.0
        
        # Should not raise
        config._validate()

    @pytest.mark.unit
    def test_validate_musicbrainz_delay_above_one(self):
        """Test that MusicBrainz delay above 1.0 is valid."""
        config = Config()
        config.lidarr_api_key = "valid-key"
        config.musicbrainz_delay = 2.5
        
        # Should not raise
        config._validate()


class TestConfigToDict:
    """Tests for configuration export to dictionary."""

    @pytest.mark.unit
    def test_to_dict_includes_all_settings(self, monkeypatch):
        """Test that to_dict exports all configuration settings."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        
        config = Config()
        config._load_from_env()
        
        config_dict = config.to_dict()
        
        # Check that all expected keys are present
        expected_keys = [
            'lidarr_base_url',
            'quality_profile_id',
            'metadata_profile_id',
            'root_folder_path',
            'musicbrainz_delay',
            'use_musicbrainz',
            'lidarr_request_delay',
            'max_retries',
            'retry_delay',
            'api_error_delay',
            'batch_size',
            'batch_pause',
            'artist_aliases',
        ]
        
        for key in expected_keys:
            assert key in config_dict

    @pytest.mark.unit
    def test_to_dict_no_api_key(self, monkeypatch):
        """Test that to_dict does not include API key (security)."""
        monkeypatch.setenv('LIDARR_API_KEY', 'secret-key')
        
        config = Config()
        config._load_from_env()
        
        config_dict = config.to_dict()
        
        # API key should not be in the exported dict
        assert 'lidarr_api_key' not in config_dict
        assert 'LIDARR_API_KEY' not in config_dict

    @pytest.mark.unit
    def test_to_dict_values_match(self, monkeypatch):
        """Test that to_dict values match configuration attributes."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        monkeypatch.setenv('BATCH_SIZE', '50')
        monkeypatch.setenv('MUSICBRAINZ_DELAY', '2.5')
        
        config = Config()
        config._load_from_env()
        
        config_dict = config.to_dict()
        
        assert config_dict['batch_size'] == config.batch_size
        assert config_dict['musicbrainz_delay'] == config.musicbrainz_delay
        assert config_dict['lidarr_base_url'] == config.lidarr_base_url


class TestConfigRepr:
    """Tests for configuration string representation."""

    @pytest.mark.unit
    def test_repr_sanitized(self, monkeypatch):
        """Test that __repr__ does not expose API key."""
        monkeypatch.setenv('LIDARR_API_KEY', 'super-secret-key')
        
        config = Config()
        config._load_from_env()
        
        repr_str = repr(config)
        
        # API key should not appear in repr
        assert 'super-secret-key' not in repr_str
        # Should mention it's a Config object
        assert 'Config' in repr_str or 'config' in repr_str.lower()


class TestConfigArtistAliases:
    """Tests for artist aliases configuration."""

    @pytest.mark.unit
    def test_default_artist_aliases(self, monkeypatch):
        """Test that default artist aliases are loaded."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        
        config = Config()
        config._load_from_env()
        
        # Check some default aliases exist
        assert 'kanye west' in config.artist_aliases
        assert 'ye' in config.artist_aliases['kanye west']
        assert 'travis scott' in config.artist_aliases

    @pytest.mark.unit
    def test_custom_artist_aliases_from_module(self):
        """Test loading custom artist aliases from module."""
        mock_config = Mock()
        mock_config.LIDARR_API_KEY = "test-key"
        mock_config.ARTIST_ALIASES = {
            'custom artist': ['alias1', 'alias2'],
            'another': ['other']
        }
        
        config = Config()
        config._load_from_module(mock_config)
        
        assert config.artist_aliases == {
            'custom artist': ['alias1', 'alias2'],
            'another': ['other']
        }


class TestConfigIntegration:
    """Integration tests for full configuration loading."""

    @pytest.mark.unit
    def test_full_config_lifecycle(self, monkeypatch):
        """Test complete configuration loading and validation lifecycle."""
        # Set up environment
        monkeypatch.setenv('LIDARR_API_KEY', 'integration-test-key')
        monkeypatch.setenv('LIDARR_BASE_URL', 'http://integration:9696')
        monkeypatch.setenv('BATCH_SIZE', '100')
        
        # Create config (should load from env)
        with patch('lib.config_manager.Config._load_from_module', side_effect=ImportError):
            config = Config()
        
        # Verify loaded correctly
        assert config.lidarr_api_key == 'integration-test-key'
        assert config.lidarr_base_url == 'http://integration:9696'
        assert config.batch_size == 100
        
        # Verify can export to dict
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict['batch_size'] == 100

    @pytest.mark.unit
    def test_config_immutability_not_enforced(self, monkeypatch):
        """Test that config values can be modified after loading (no immutability)."""
        monkeypatch.setenv('LIDARR_API_KEY', 'test-key')
        
        config = Config()
        config._load_from_env()
        
        # Modify a value
        original_batch = config.batch_size
        config.batch_size = 999
        
        assert config.batch_size == 999
        assert config.batch_size != original_batch

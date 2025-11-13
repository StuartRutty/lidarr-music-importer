import os
from pathlib import Path
import sys

import pytest

from lib.config_manager import Config


def test_load_from_env_defaults():
    """Test that Config can load from environment with defaults."""
    c = Config()
    
    # Should have default values even without config.py
    assert c.lidarr_base_url == 'http://localhost:8686'
    assert c.quality_profile_id == 1
    assert c.metadata_profile_id == 1
    assert c.musicbrainz_delay == 1.0
    assert c.use_musicbrainz is True
    assert c.batch_size == 10


def test_load_from_env_variables(monkeypatch):
    """Test that environment variables are used when config.py import fails."""
    # Mock the import to fail, forcing env variable loading
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == 'config':
            raise ImportError("Mocked: config.py not available")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, '__import__', mock_import)
    monkeypatch.setenv('LIDARR_BASE_URL', 'http://test.local:8686')
    monkeypatch.setenv('QUALITY_PROFILE_ID', '5')
    monkeypatch.setenv('MUSICBRAINZ_DELAY', '2.5')
    monkeypatch.setenv('USE_MUSICBRAINZ', 'false')
    monkeypatch.setenv('BATCH_SIZE', '42')
    
    c = Config()
    
    assert c.lidarr_base_url == 'http://test.local:8686'
    assert c.quality_profile_id == 5
    assert abs(c.musicbrainz_delay - 2.5) < 1e-6
    assert c.use_musicbrainz is False
    assert c.batch_size == 42


def test_to_dict_exports_config():
    """Test that to_dict exports configuration values."""
    c = Config()
    
    d = c.to_dict()
    
    assert 'lidarr_base_url' in d
    assert 'quality_profile_id' in d
    assert 'musicbrainz_delay' in d
    assert 'use_musicbrainz' in d
    assert 'batch_size' in d
    assert 'artist_aliases' in d


def test_repr_sanitized():
    """Test that __repr__ doesn't expose sensitive data."""
    c = Config()
    
    repr_str = repr(c)
    
    assert 'Config(' in repr_str
    assert 'lidarr_url=' in repr_str
    assert 'musicbrainz_delay=' in repr_str
    # Should not contain API key
    assert 'api_key' not in repr_str.lower()

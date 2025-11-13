import os
from pathlib import Path

import importlib
import sys

import pytest

from lib.config import Config, get_config


def write_temp_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "temp_config.py"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_from_config_file_and_properties(tmp_path, monkeypatch):
    cfg_text = (
        "LIDARR_BASE_URL = 'http://example.local'\n"
        "LIDARR_API_KEY = 'S3CR3T'\n"
        "QUALITY_PROFILE_ID = 5\n"
        "MUSICBRAINZ_DELAY = 1.5\n"
        "USE_MUSICBRAINZ = False\n"
        "BATCH_SIZE = 42\n"
    )

    p = write_temp_config(tmp_path, cfg_text)

    c = Config(config_file=str(p))

    assert c.LIDARR_BASE_URL == "http://example.local"
    # API key remains accessible via property but masked in to_dict
    assert c.LIDARR_API_KEY == "S3CR3T"
    assert c.QUALITY_PROFILE_ID == 5
    assert abs(c.MUSICBRAINZ_DELAY - 1.5) < 1e-6
    assert c.USE_MUSICBRAINZ is False
    assert c.BATCH_SIZE == 42


def test_environment_overrides_config_file(tmp_path, monkeypatch):
    cfg_text = (
        "LIDARR_BASE_URL = 'http://fromfile'\n"
        "QUALITY_PROFILE_ID = 2\n"
    )
    p = write_temp_config(tmp_path, cfg_text)

    monkeypatch.setenv('LIDARR_BASE_URL', 'http://fromenv')
    # the environment mapping uses the LIDARR_ prefix for quality id
    monkeypatch.setenv('LIDARR_QUALITY_PROFILE_ID', '7')

    c = Config(config_file=str(p))

    # environment should override base url
    assert c.LIDARR_BASE_URL == 'http://fromenv'
    # note: the env mapping stores LIDARR_QUALITY_PROFILE_ID separately from
    # QUALITY_PROFILE_ID (legacy naming); ensure the env value was recorded
    assert c._config_data.get('LIDARR_QUALITY_PROFILE_ID') == 7
    # file value remains present under QUALITY_PROFILE_ID
    assert c.QUALITY_PROFILE_ID == 2


def test_to_dict_masks_api_key_and_override(tmp_path):
    cfg_text = "LIDARR_API_KEY = 'MYKEY'\nLIDARR_BASE_URL = 'x'\n"
    p = write_temp_config(tmp_path, cfg_text)
    c = Config(config_file=str(p))

    d = c.to_dict()
    assert d['LIDARR_API_KEY'] == '***'

    # override should update values returned by properties
    c.override(LIDARR_REQUEST_DELAY=2.2, BATCH_SIZE=99)
    assert abs(c.LIDARR_REQUEST_DELAY - 2.2) < 1e-6
    assert c.BATCH_SIZE == 99


def test_get_config_singleton(monkeypatch):
    # Ensure module-level singleton behaves as expected
    import lib.config as cfg_mod

    # Reset any default config
    cfg_mod._default_config = None
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2


def test_invalid_env_value_logs_warning(monkeypatch, caplog):
    # put invalid int into an int field and ensure no exception; warning logged
    # invalid value for the env var that the module checks
    monkeypatch.setenv('LIDARR_QUALITY_PROFILE_ID', 'not-an-int')
    caplog.clear()
    caplog.set_level('WARNING')

    c = Config(config_file=None)

    # property should fall back to default when env invalid
    assert c.QUALITY_PROFILE_ID == 1
    assert any('Invalid value for LIDARR_QUALITY_PROFILE_ID' in rec.message for rec in caplog.records)

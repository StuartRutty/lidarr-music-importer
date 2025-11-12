"""Configuration management for Lidarr Music Importer."""

import os
from typing import Dict, Any

class Config:
    """Configuration container with validation."""
    
    def __init__(self):
        """Initialize configuration from environment or config.py file."""
        # Try to import from config.py first
        try:
            import sys
            from pathlib import Path
            
            # Add parent directory to path to import config
            config_dir = Path(__file__).parent.parent
            if str(config_dir) not in sys.path:
                sys.path.insert(0, str(config_dir))
            
            try:
                import config as config_module
                self._load_from_module(config_module)
            except ImportError:
                self._load_from_env()
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
        
        # Do not auto-validate in __init__ — tests construct Config() and then
        # call `_load_from_module` / `_load_from_env` or `_validate()` explicitly.
        # Leaving validation to an explicit call avoids raising during test setup
        # when a placeholder `config.py` is present in the working tree.
    
    def _load_from_module(self, config_module) -> None:
        """Load configuration from config.py module."""
        # Lidarr connection
        self.lidarr_base_url = getattr(config_module, 'LIDARR_BASE_URL', 'http://localhost:8686')
        self.lidarr_api_key = getattr(config_module, 'LIDARR_API_KEY', None)
        
        # Lidarr import settings
        self.quality_profile_id = getattr(config_module, 'QUALITY_PROFILE_ID', 1)
        self.metadata_profile_id = getattr(config_module, 'METADATA_PROFILE_ID', 1)
        self.root_folder_path = getattr(config_module, 'ROOT_FOLDER_PATH', '/music')
        
        # API rate limiting
        self.musicbrainz_delay = getattr(config_module, 'MUSICBRAINZ_DELAY', 1.0)
        self.use_musicbrainz = getattr(config_module, 'USE_MUSICBRAINZ', True)
        self.lidarr_request_delay = getattr(config_module, 'LIDARR_REQUEST_DELAY', 2.0)
        self.max_retries = getattr(config_module, 'MAX_RETRIES', 3)
        self.retry_delay = getattr(config_module, 'RETRY_DELAY', 5.0)
        self.api_error_delay = getattr(config_module, 'API_ERROR_DELAY', 5.0)
        
        # Batch processing
        self.batch_size = getattr(config_module, 'BATCH_SIZE', 10)
        self.batch_pause = getattr(config_module, 'BATCH_PAUSE', 10.0)
        
        # MusicBrainz user agent
        mb_ua = getattr(config_module, 'MUSICBRAINZ_USER_AGENT', {})
        self.musicbrainz_user_agent = {
            'app_name': mb_ua.get('app_name', 'lidarr-album-import-script'),
            'version': mb_ua.get('version', '1.0'),
            'contact': mb_ua.get('contact', 'rutty.stuart@gmail.com')
        }
        
        # Artist aliases
        self.artist_aliases = getattr(config_module, 'ARTIST_ALIASES', {
            'kanye west': ['ye', 'kanye'],
            'ye': ['kanye west', 'kanye'],
            'travis scott': ['travi$ scott'],
            'a$ap rocky': ['asap rocky'],
            'mø': ['mo', 'mö'],
        })
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables (fallback)."""
        # Lidarr connection
        self.lidarr_base_url = os.getenv('LIDARR_BASE_URL', 'http://localhost:8686')
        self.lidarr_api_key = os.getenv('LIDARR_API_KEY')
        
        # Lidarr import settings
        self.quality_profile_id = int(os.getenv('QUALITY_PROFILE_ID', '1'))
        self.metadata_profile_id = int(os.getenv('METADATA_PROFILE_ID', '1'))
        self.root_folder_path = os.getenv('ROOT_FOLDER_PATH', '/music')
        
        # API rate limiting
        self.musicbrainz_delay = float(os.getenv('MUSICBRAINZ_DELAY', '1.0'))
        self.use_musicbrainz = os.getenv('USE_MUSICBRAINZ', 'true').lower() == 'true'
        self.lidarr_request_delay = float(os.getenv('LIDARR_REQUEST_DELAY', '2.0'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = float(os.getenv('RETRY_DELAY', '5.0'))
        self.api_error_delay = float(os.getenv('API_ERROR_DELAY', '5.0'))
        
        # Batch processing
        self.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        self.batch_pause = float(os.getenv('BATCH_PAUSE', '10.0'))
        
        # MusicBrainz user agent
        self.musicbrainz_user_agent = {
            'app_name': os.getenv('MB_APP_NAME', 'lidarr-album-import-script'),
            'version': os.getenv('MB_VERSION', '1.0'),
            'contact': os.getenv('MB_CONTACT', 'rutty.stuart@gmail.com')
        }
        
        # Artist aliases (simplified for env vars)
        self.artist_aliases = {
            'kanye west': ['ye', 'kanye'],
            'ye': ['kanye west', 'kanye'],
            'travis scott': ['travi$ scott'],
            'a$ap rocky': ['asap rocky'],
            'mø': ['mo', 'mö'],
        }
    
    def _validate(self) -> None:
        """Validate required configuration values."""
        if not self.lidarr_api_key:
            raise ValueError(
                "LIDARR_API_KEY is required. Set it in config.py or LIDARR_API_KEY environment variable."
            )
        
        if self.lidarr_api_key == "YOUR_API_KEY_HERE":
            raise ValueError(
                "Please update LIDARR_API_KEY in config.py with your actual API key."
            )
        
        if self.musicbrainz_delay < 1.0:
            raise ValueError(
                "MUSICBRAINZ_DELAY must be at least 1.0 second to respect MusicBrainz rate limits."
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'lidarr_base_url': self.lidarr_base_url,
            'quality_profile_id': self.quality_profile_id,
            'metadata_profile_id': self.metadata_profile_id,
            'root_folder_path': self.root_folder_path,
            'musicbrainz_delay': self.musicbrainz_delay,
            'use_musicbrainz': self.use_musicbrainz,
            'lidarr_request_delay': self.lidarr_request_delay,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'api_error_delay': self.api_error_delay,
            'batch_size': self.batch_size,
            'batch_pause': self.batch_pause,
            'artist_aliases': self.artist_aliases,
        }
    
    def __repr__(self) -> str:
        """String representation (sanitized - no API key)."""
        return (
            f"Config(lidarr_url={self.lidarr_base_url}, "
            f"musicbrainz_delay={self.musicbrainz_delay}s, "
            f"batch_size={self.batch_size})"
        )

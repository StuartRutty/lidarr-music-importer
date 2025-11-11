# Lidarr Music Importer Configuration Template
# Copy this file to config.py and update with your settings

# ========== LIDARR CONNECTION SETTINGS ==========
LIDARR_BASE_URL = "http://localhost:8686"  # Your Lidarr instance URL
LIDARR_API_KEY = "YOUR_API_KEY_HERE"       # From Settings -> General -> Security

# ========== LIDARR IMPORT SETTINGS ==========
# Get these values from your Lidarr UI:

# Quality Profile ID (Settings -> Profiles -> Quality Profiles)
QUALITY_PROFILE_ID = 1

# Metadata Profile ID (Settings -> Profiles -> Metadata Profiles)  
METADATA_PROFILE_ID = 1

# Root Folder Path (Settings -> Media Management -> Root Folders)
ROOT_FOLDER_PATH = "/music"

# ========== API RATE LIMITING ==========
# Adjust these if you experience API issues

MUSICBRAINZ_DELAY = 1.0         # Seconds between MusicBrainz queries (min 1.0)
LIDARR_REQUEST_DELAY = 2.0      # Seconds between Lidarr API requests
MAX_RETRIES = 3                 # Maximum retries for failed API calls
RETRY_DELAY = 5.0               # Base delay for exponential backoff

# ========== BATCH PROCESSING ==========
# Controls processing speed and API load

BATCH_SIZE = 10                 # Items to process before pausing
BATCH_PAUSE = 10.0              # Seconds to pause between batches

# ========== LOGGING SETTINGS ==========
LOG_LEVEL = "INFO"              # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"

# ========== MUSICBRAINZ SETTINGS ==========
# Required user agent for MusicBrainz API
MUSICBRAINZ_USER_AGENT = {
    "app_name": "lidarr-album-import-script",
    "version": "1.0", 
    "contact": "your.email@example.com"  # UPDATE THIS
}
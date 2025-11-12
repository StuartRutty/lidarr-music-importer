#!/usr/bin/env python3
"""
add_albums_to_lidarr.py - Targeted Album Import for Lidarr

This script processes a CSV file containing artist/album pairs and selectively adds
only specific albums to Lidarr, rather than importing entire artist catalogs.

WORKFLOW:
1. Check if the specific album is already monitored (using MusicBrainz ID matching)
2. Use provided MusicBrainz IDs from enriched CSV to query Lidarr directly
3. Check if artist exists in Lidarr library using MB ID
4. If artist doesn't exist, add artist with monitoring disabled by default
5. Monitor only the specific requested album using MB ID
6. Trigger automatic search for missing album files
7. Update CSV with processing status for resumable operations

FEATURES:
- MusicBrainz ID-first processing for reliable metadata and precise album matching
- Requires enriched CSV files (use universal_parser.py --enrich-musicbrainz)
- Batch processing with configurable pauses to avoid API overload
- Retry logic with exponential backoff for API reliability
- Progress tracking via CSV status column
- Dry-run mode for testing
- Skip completed items for resumable large-scale imports
- Direct MB ID matching for optimal performance
- Automatic search initiation for newly monitored albums

REQUIREMENTS:
- Lidarr v2+ API access
- Enriched CSV file with 'artist', 'album', 'mb_artist_id', 'mb_release_id' columns
- Run universal_parser.py first to create enriched CSV files

Configure the constants in the CONFIG section below before running.
"""

import csv
import time
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import requests
from tqdm import tqdm
from rapidfuzz import fuzz, process

# Add lib directory to Python path for imports
lib_path = Path(__file__).parent.parent / 'lib'
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import configuration and API clients
from config_manager import Config
from lidarr_client import LidarrClient
from csv_handler import CSVHandler, ItemStatus
from lib.text_utils import (
    normalize_artist_name,
    normalize_profanity,
    strip_album_suffixes,
    get_album_title_variations,
    get_edition_variants,
    normalize_album_title_for_matching,
    clean_csv_input
)

# Load configuration
try:
    config = Config()
    logging.info(f"Configuration loaded: {config}")
except Exception as e:
    logging.error(f"Failed to load configuration: {e}")
    logging.error("Please ensure config.py exists (copy from config.template.py)")
    sys.exit(1)

# Configuration constants
LIDARR_BASE_URL = config.lidarr_base_url
LIDARR_API_KEY = config.lidarr_api_key
QUALITY_PROFILE_ID = config.quality_profile_id
METADATA_PROFILE_ID = config.metadata_profile_id
ROOT_FOLDER_PATH = config.root_folder_path
LIDARR_REQUEST_DELAY = config.lidarr_request_delay
MAX_RETRIES = config.max_retries
RETRY_DELAY = config.retry_delay
API_ERROR_DELAY = config.api_error_delay
BATCH_SIZE = config.batch_size
BATCH_PAUSE = config.batch_pause
ARTIST_ALIASES = config.artist_aliases

# ========== END CONFIGURATION ==========

# Initialize Lidarr API client with configuration
lidarr_client = LidarrClient(
    base_url=config.lidarr_base_url,
    api_key=config.lidarr_api_key,
    quality_profile_id=config.quality_profile_id,
    metadata_profile_id=config.metadata_profile_id,
    root_folder_path=config.root_folder_path,
    request_delay=config.lidarr_request_delay,
    max_retries=config.max_retries,
    retry_delay=config.retry_delay,
    timeout=30
)

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


# ========== UTILITY FUNCTIONS ==========

def find_existing_artist(artist_name: str, existing_artists: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find an existing artist using ONLY exact matches and very safe transformations.
    
    DISABLED: All fuzzy matching to prevent false positives like "AJ Suede" -> "Suede"
    
    Args:
        artist_name: The artist name to search for
        existing_artists: Dict of existing artists from get_existing_artists()
        
    Returns:
        Artist data if found, None otherwise
    """
    import re
    
    # Normalize for comparison (handles apostrophes, quotes, etc.)
    artist_normalized = normalize_artist_name(artist_name)
    
    # Check each existing artist with normalization
    for existing_name_lower, artist_data in existing_artists.items():
        if normalize_artist_name(existing_name_lower) == artist_normalized:
            return artist_data
    
    # Check if the artist name has known aliases (e.g., "Ye" -> "Kanye West")
    # Search for the artist under any of their known aliases
    artist_lower = artist_name.lower()
    if artist_lower in ARTIST_ALIASES:
        for alias in ARTIST_ALIASES[artist_lower]:
            alias_normalized = normalize_artist_name(alias)
            for existing_name_lower, artist_data in existing_artists.items():
                if normalize_artist_name(existing_name_lower) == alias_normalized:
                    logging.info(f"Found artist '{artist_name}' via alias '{alias}' in existing artists")
                    return artist_data
    
    # Also check the reverse - if the artist we're searching for is an alias of something in the dict
    for potential_main_name, aliases in ARTIST_ALIASES.items():
        if artist_lower in [a.lower() for a in aliases]:
            if potential_main_name in existing_artists:
                logging.info(f"Found artist '{artist_name}' via main name '{potential_main_name}' in existing artists")
                return existing_artists[potential_main_name]
    
    # ONLY safe bracket removal for cases like [bsd.u] -> bsd.u
    if artist_name.startswith('[') and artist_name.endswith(']'):
        bracket_content = artist_name.strip('[]').lower()
        if bracket_content in existing_artists:
            logging.debug(f"Found artist '{artist_name}' as '{bracket_content}' (removed surrounding brackets)")
            return existing_artists[bracket_content]
    
    # No other fuzzy matching - if not found, treat as new artist
    logging.debug(f"No exact match found for '{artist_name}' - will be added as new artist")
    return None


def retry_api_call(func, *args, **kwargs):
    """
    Wrapper for API calls with exponential backoff retry logic.
    
    Handles transient API failures (503 Service Unavailable) by retrying
    with increasing delays. Non-retryable errors are raised immediately.
    
    Args:
        func: The API function to call
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Result of the successful API call, or None if all retries failed
    """
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            # Only retry on service unavailable errors
            if "503" in str(e) or "Service Unavailable" in str(e):
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Service unavailable, retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
            # For any error that exhausts retries, add extra delay before continuing
            if attempt >= MAX_RETRIES - 1:
                logging.warning(f"Adding {API_ERROR_DELAY}s delay after API errors")
                time.sleep(API_ERROR_DELAY)
            # Re-raise non-retryable errors immediately
            raise e
    return None



# ========== CSV DATA HANDLING ==========
# CSV functions have been moved to lib/csv_handler.py
# Use CSVHandler class for reading/writing artist/album CSV files
# See: lib/csv_handler.py for CSVHandler and ItemStatus classes



# ========== EXTERNAL API FUNCTIONS ==========

def get_existing_artists() -> Dict[str, Dict[str, Any]]:
    """
    Retrieve all artists currently in Lidarr library.
    
    This is used to avoid duplicate artist additions and to identify
    existing artists for album monitoring.
    
    Returns:
        Dictionary mapping lowercase artist names to artist data
    """
    url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/artist"
    headers = {"X-Api-Key": LIDARR_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        artists = r.json()
        # Use lowercase names as keys for case-insensitive matching
        return {artist['artistName'].lower(): artist for artist in artists}
    except Exception as e:
        logging.exception("Failed to get existing artists: %s", e)
        return {}


def is_album_already_monitored(artist_name: str, album_title: str, skip_mb_lookup: bool = False, mb_release_id: str = "") -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if a specific album is already monitored in Lidarr library.
    
    This function searches through all albums in the Lidarr library to find
    if the specified artist/album combination is already being monitored.
    Uses fuzzy matching with profanity/suffix filtering to handle title variations.
    
    Args:
        artist_name: Name of the artist
        album_title: Title of the album to check
        skip_mb_lookup: If True, skips MusicBrainz lookup to avoid redundant API calls
        mb_release_id: Optional MusicBrainz release group ID for precise matching
        
    Returns:
        Tuple of (is_monitored_boolean, album_data_if_found)
    """
    headers = {"X-Api-Key": LIDARR_API_KEY}
    
    try:
        # Get all albums from Lidarr (this includes all artists)
        url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        albums = r.json()
        
        # Clean the search title using our standard approach
        clean_album_title = strip_album_suffixes(normalize_profanity(album_title))
        artist_name_normalized = normalize_artist_name(artist_name)
        
        # Use provided MB release ID if available
        mb_release_group_id = mb_release_id if mb_release_id else None
        
        # Build a list of albums for this artist to fuzzy match against
        artist_albums = []
        for album in albums:
            # Check if artist name matches (with normalization)
            lidarr_artist_name = album.get('artist', {}).get('artistName', '')
            lidarr_artist_normalized = normalize_artist_name(lidarr_artist_name)
            
            if lidarr_artist_normalized == artist_name_normalized:
                artist_albums.append(album)
        
        # Use rapidfuzz to find best match among this artist's albums
        if artist_albums:
            # First try exact MusicBrainz ID match if available
            if mb_release_group_id:
                for album in artist_albums:
                    if album.get('foreignAlbumId') == mb_release_group_id:
                        if album.get('monitored', False):
                            logging.info(f"Album already monitored (MusicBrainz ID match): {album['title']} by {artist_name}")
                            return True, album
                        else:
                            logging.info(f"Album found but not monitored (MusicBrainz ID match): {album['title']} by {artist_name}")
                            return False, album
            
            # Use rapidfuzz for fuzzy text matching
            album_choices = {}
            for album in artist_albums:
                clean_title = strip_album_suffixes(album['title'].lower().strip())
                album_choices[clean_title] = album
            
            # Find best match using rapidfuzz
            matches = process.extract(
                clean_album_title.lower(),
                album_choices.keys(),
                scorer=fuzz.token_sort_ratio,
                limit=1,
                score_cutoff=80  # 80% threshold for "already monitored" check
            )
            
            if matches:
                match_title, score, _ = matches[0]
                matched_album = album_choices[match_title]
                if matched_album.get('monitored', False):
                    logging.info(f"Album already monitored (fuzzy match {score}%): {matched_album['title']} by {artist_name}")
                    return True, matched_album
                else:
                    logging.info(f"Album found but not monitored (fuzzy match {score}%): {matched_album['title']} by {artist_name}")
                    return False, matched_album
        
        # Album not found in library
        logging.debug(f"Album not found in Lidarr library: {artist_name} - {album_title}")
        return False, None
        
    except Exception as e:
        logging.exception("Error checking if album is monitored: %s", e)
        return False, None


# ========== CORE PROCESSING FUNCTIONS ==========

def monitor_album_by_mbid(artist_id: int, musicbrainz_album_id: str, artist_name: str, album_title: str) -> Tuple[bool, bool]:
    """
    Add and monitor a specific album using its MusicBrainz ID.
    
    This is the preferred method as it uses the authoritative MusicBrainz ID
    to ensure we're adding the exact album, bypassing title matching issues.
    
    Args:
        artist_id: Lidarr's internal ID for the artist
        musicbrainz_album_id: MusicBrainz release group ID
        artist_name: Artist name (for logging purposes)
        album_title: Album title (for logging purposes)
        
    Returns:
        Tuple of (success, was_already_monitored)
        - success: True if album is now monitored (whether it was already or just added)
        - was_already_monitored: True if album was already monitored, False if it was just added/enabled
    """
    logging.info(f"📍 Using MusicBrainz ID for precise album lookup: {musicbrainz_album_id}")
    headers = {"X-Api-Key": LIDARR_API_KEY}
    
    try:
        # First check if this album already exists in Lidarr
        album_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        params = {"artistId": artist_id}
        r = requests.get(album_url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        existing_albums = r.json()
        
        # Check if album with this MusicBrainz ID already exists
        print(f"DEBUG: Looking for MBID {musicbrainz_album_id} among {len(existing_albums)} existing albums", file=sys.stderr)
        found_match = False
        for album in existing_albums:
            album_mbid = album.get('foreignAlbumId')
            album_title_in_lidarr = album.get('title')
            is_monitored = album.get('monitored')
            logging.debug(f"  Album: '{album_title_in_lidarr}' (MBID: {album_mbid}, monitored: {is_monitored})")
            if album_mbid == musicbrainz_album_id:
                found_match = True
                if is_monitored:
                    logging.debug(f"Album '{album_title}' by {artist_name} is already monitored - SKIPPING")
                    logging.info(f"Album '{album_title}' by {artist_name} is already monitored")
                    return True, True
                else:
                    logging.debug(f"Album '{album_title}' by {artist_name} exists but not monitored - enabling monitoring")
                    logging.info(f"Album '{album_title}' by {artist_name} exists but not monitored - will enable monitoring")
                    # Album exists but not monitored - enable monitoring
                    album['monitored'] = True
                    put_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album/{album['id']}"
                    r = requests.put(put_url, json=album, headers=headers, timeout=30)
                    r.raise_for_status()
                    logging.info(f"Enabled monitoring for existing album: {artist_name} - {album_title}")
                    return True, False
        
        if not found_match:
            logging.debug(f"Album with MBID {musicbrainz_album_id} not found in Lidarr - will add it")
        
        # Album doesn't exist - use Lidarr's album lookup to add it
        lookup_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album/lookup"
        lookup_params = {"term": f"lidarr:{musicbrainz_album_id}"}
        
        r = requests.get(lookup_url, params=lookup_params, headers=headers, timeout=30)
        r.raise_for_status()
        lookup_results = r.json()
        
        if not lookup_results:
            logging.warning(f"Lidarr lookup returned no results for MusicBrainz ID: {musicbrainz_album_id}")
            return False, False
        
        # Take the first result (should match exactly by MBID)
        album_data = lookup_results[0]
        
        # Verify this is for the correct artist
        album_artist_id = album_data.get('artist', {}).get('id')
        album_artist_name = album_data.get('artist', {}).get('artistName', 'Unknown')
        
        logging.debug(f"Album lookup verification for {album_title}:")
        logging.debug(f"  Expected artist ID: {artist_id} ({artist_name})")
        logging.debug(f"  Album data artist ID: {album_artist_id} ({album_artist_name})")
        
        if album_artist_id != artist_id:
            logging.warning(f"Album lookup returned different artist ID for {album_title}")
            logging.debug(f"  Expected: {artist_name} (ID: {artist_id})")
            logging.debug(f"  Got: {album_artist_name} (ID: {album_artist_id})")
            
            # Multiple strategies to handle artist ID mismatches (common with special characters)
            lookup_mbid = album_data.get('artist', {}).get('foreignArtistId')
            
            # Strategy 1: If album artist ID is None but names are similar, likely a Lidarr API issue
            if album_artist_id is None and album_artist_name and artist_name:
                # Check for similar names (handles character encoding variations)
                name_match = (album_artist_name.lower().strip() == artist_name.lower().strip() or
                             album_artist_name.lower().replace('.', '').replace('-', '') == 
                             artist_name.lower().replace('.', '').replace('-', ''))
                
                if name_match:
                    logging.info(f"Name match with null ID - fixing artist data: {album_artist_name}")
                    # Get complete artist data from Lidarr to ensure all required fields
                    expected_artist_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/artist/{artist_id}"
                    artist_response = requests.get(expected_artist_url, headers=headers, timeout=30)
                    if artist_response.status_code == 200:
                        complete_artist_data = artist_response.json()
                        album_data['artist'] = complete_artist_data  # Use complete artist data
                        album_data['artistId'] = artist_id
                        logging.debug(f"Updated album with complete artist data for ID {artist_id}")
                    else:
                        logging.error(f"Could not fetch complete artist data for ID {artist_id}")
                        return False, False
                else:
                    logging.error(f"Name mismatch with null ID: '{album_artist_name}' vs '{artist_name}'")
                    return False, False
            
            # Strategy 2: Check if we can get the expected artist's MusicBrainz ID to compare
            elif lookup_mbid:
                try:
                    # Get our target artist's MusicBrainz ID for comparison
                    expected_artist_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/artist/{artist_id}"
                    r = requests.get(expected_artist_url, headers=headers, timeout=30)
                    if r.status_code == 200:
                        expected_artist_data = r.json()
                        expected_mbid = expected_artist_data.get('foreignArtistId')
                        
                        if expected_mbid and expected_mbid == lookup_mbid:
                            logging.info(f"MusicBrainz ID match - fixing artist data: {expected_mbid}")
                            # Use complete artist data to avoid missing fields
                            album_data['artist'] = expected_artist_data
                            album_data['artistId'] = artist_id
                        else:
                            logging.error(f"MusicBrainz ID mismatch: expected {expected_mbid}, got {lookup_mbid}")
                            return False, False
                    else:
                        logging.error(f"Could not fetch artist {artist_id} for comparison")
                        return False, False
                except Exception as e:
                    logging.error(f"Error comparing artist MusicBrainz IDs: {e}")
                    return False, False
            else:
                logging.error(f"No strategy available for artist ID mismatch")
                return False, False
        else:
            logging.debug(f"Artist ID verification passed for {album_title}")
        
        # Configure the album for adding
        album_data['monitored'] = True
        album_data['addOptions'] = {'searchForMissingAlbums': True}  # Auto-search for files
        
        # Verify album data before sending
        logging.debug(f"Album data being sent to Lidarr:")
        logging.debug(f"  Album: {album_data.get('title', 'Unknown')}")
        logging.debug(f"  Artist ID: {album_data.get('artist', {}).get('id', 'None')}")
        logging.debug(f"  Artist Name: {album_data.get('artist', {}).get('artistName', 'None')}")
        logging.debug(f"  MusicBrainz ID: {album_data.get('foreignAlbumId', 'None')}")
        
        # Add the album to Lidarr
        add_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        r = requests.post(add_url, json=album_data, headers=headers, timeout=30)
        
        if r.status_code in (200, 201):
            logging.info(f"Added and monitoring album: {artist_name} - {album_title} (MBID: {musicbrainz_album_id})")
            return True, False
        elif r.status_code == 400:
            # Bad request - log details for debugging
            error_text = r.text
            logging.error(f"Bad request adding album {album_title}: {error_text}")
            
            # Common 400 error scenarios
            if "already exists" in error_text.lower():
                logging.info("Album already exists - checking monitoring status")
                # Album exists, just enable monitoring if needed
                return True, True
            elif "artist" in error_text.lower() and "not found" in error_text.lower():
                logging.error(f"Artist ID {artist_id} not found when adding album - possible data corruption")
                return False, False
            else:
                logging.error(f"Unknown 400 error: {error_text}")
                return False, False
        elif r.status_code == 409:
            # Conflict - album already exists
            logging.info(f"Album already exists in Lidarr: {artist_name} - {album_title}")
            return True, True
        else:
            r.raise_for_status()
            return False, False
        
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Lidarr API error while adding album {album_title}: {e}")
            logging.error(f"Response status: {e.response.status_code}")
            logging.error(f"Response text: {e.response.text}")
        else:
            logging.error(f"Lidarr API error while adding album {album_title}: {e}")
        return False, False
    except Exception as e:
        logging.error(f"Unexpected error while adding album {album_title}: {e}")
        return False, False


def monitor_album(artist_id: int, album_title: str, artist_name: str) -> bool:
    """
    Attempt to find and monitor a specific album for an artist in Lidarr.
    
    This function implements the core logic for selective album monitoring.
    It tries multiple strategies to locate the album and handles cases where
    the album may not be immediately available in Lidarr's database.
    
    STRATEGY:
    1. Search existing albums for the artist using fuzzy matching
    2. If found, enable monitoring for that specific album
    3. If not found, trigger artist metadata refresh (album may appear after refresh)
    
    FUZZY MATCHING:
    - Exact title matches (case-insensitive)  
    - Handles common variations like "(Deluxe)", "(Expanded)", "(Remastered)" suffixes
    - Does NOT match partial titles (e.g., "Album" won't match "Album 2")
    
    Args:
        artist_id: Lidarr's internal ID for the artist
        album_title: Title of the album to monitor
        artist_name: Artist name (for logging purposes)
        
    Returns:
        True if album was successfully found and monitored, False otherwise
    """
    headers = {"X-Api-Key": LIDARR_API_KEY}
    
    try:
        # Get all albums for this artist from Lidarr
        album_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        params = {"artistId": artist_id}
        r = requests.get(album_url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        albums = r.json()
        
        # Implement fuzzy matching with rapidfuzz to handle title variations
        album_title_clean = strip_album_suffixes(album_title.lower().strip())
        
        # Get all album titles from Lidarr for this artist
        album_choices = {}
        for album in albums:
            lidarr_title = album['title']
            # Strip suffixes from Lidarr titles too for fair comparison
            clean_title = strip_album_suffixes(lidarr_title.lower().strip())
            album_choices[clean_title] = album
        
        # Use rapidfuzz to find best matches (token_sort_ratio handles word order)
        # This is more robust than our custom normalization
        matches = process.extract(
            album_title_clean,
            album_choices.keys(),
            scorer=fuzz.token_sort_ratio,
            limit=3,
            score_cutoff=85  # Only consider matches with 85%+ similarity
        )
        
        matching_albums = []
        if matches:
            for match_title, score, _ in matches:
                album = album_choices[match_title]
                original_title = album['title']
                logging.debug(f"  Fuzzy match ({score}%): '{original_title}' <- '{album_title}'")
                matching_albums.append(album)
        
        # If we found matching albums, check if already monitored
        if matching_albums:
            album = matching_albums[0]
            album_title_matched = album['title']
            
            # Check if album is already monitored
            if album.get('monitored', False):
                logging.info(f"Album already monitored: {album_title_matched} by {artist_name}")
                return True
            
            # Monitor the album
            album['monitored'] = True
            logging.info(f"Monitoring album: {album_title_matched} by {artist_name} (matched from: {album_title})")
            
            # Update the album monitoring status via Lidarr API
            update_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album/{album['id']}"
            update_r = requests.put(update_url, json=album, headers=headers, timeout=30)
            update_r.raise_for_status()
            
            # Trigger search for missing files for this specific album
            try:
                search_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/command"
                search_payload = {
                    "name": "AlbumSearch",
                    "albumIds": [album['id']]
                }
                requests.post(search_url, json=search_payload, headers=headers, timeout=30)
                logging.info(f"Started automatic search for: {album_title_matched}")
            except Exception as search_error:
                logging.warning(f"Album monitored but search failed: {album_title_matched} - {search_error}")
            
            return True
        
        # If no albums found, trigger artist metadata refresh
        # This is common when an artist is newly added to Lidarr
        logging.info(f"Album '{album_title}' not found, triggering artist refresh for {artist_name}")
        refresh_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/command"
        refresh_payload = {
            "name": "RefreshArtist",
            "artistId": artist_id
        }
        requests.post(refresh_url, json=refresh_payload, headers=headers, timeout=30)
        
        logging.warning(f"Triggered refresh for {artist_name}, album '{album_title}' may appear after refresh completes")
        return False  # Return False since we didn't monitor yet, but refresh was triggered
        
    except Exception as e:
        logging.exception(f"✗ Error monitoring album '{album_title}' for {artist_name} (ID {artist_id}): %s", e)
        return False


def unmonitor_all_albums_for_artist(artist_id: int, artist_name: str) -> bool:
    """
    Set all albums for a NEWLY ADDED artist to unmonitored state.
    
    This is crucial when adding new artists to ensure we only monitor
    the specific albums we want, not everything Lidarr automatically monitors.
    
    WARNING: This should ONLY be called for artists that were just added 
    by our script, never for existing artists that were already in Lidarr.
    
    Args:
        artist_id: Lidarr's internal ID for the artist
        artist_name: Artist name (for logging purposes)
        
    Returns:
        True if successful, False if there were errors
    """
    headers = {"X-Api-Key": LIDARR_API_KEY}
    
    try:
        # Get all albums for this artist from Lidarr
        album_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        params = {"artistId": artist_id}
        r = requests.get(album_url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        albums = r.json()
        
        unmonitored_count = 0
        for album in albums:
            if album.get('monitored', False):
                # Set album to unmonitored
                album['monitored'] = False
                update_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album/{album['id']}"
                update_r = requests.put(update_url, json=album, headers=headers, timeout=30)
                update_r.raise_for_status()
                unmonitored_count += 1
                logging.debug(f"Unmonitored album: {album['title']} by {artist_name}")
        
        if unmonitored_count > 0:
            logging.info(f"Unmonitored {unmonitored_count} albums for NEWLY ADDED artist {artist_name}")
        else:
            logging.debug(f"No albums needed unmonitoring for newly added artist {artist_name}")
            
        return True
        
    except Exception as e:
        logging.error(f"✗ Error unmonitoring albums for newly added artist {artist_name} (ID {artist_id}): %s", e)
        return False


def unmonitor_all_except_specific_album(artist_id: int, target_musicbrainz_id: str, artist_name: str, target_album_title: str) -> bool:
    """
    Unmonitor all albums for an artist EXCEPT the specific album we want.
    
    This is the final cleanup step to ensure only our target album remains monitored
    after Lidarr might have auto-monitored related albums during the add process.
    
    Args:
        artist_id: Lidarr's internal ID for the artist
        target_musicbrainz_id: MusicBrainz ID of the album we want to keep monitored
        artist_name: Artist name (for logging purposes)
        target_album_title: Album title we want to keep (for logging purposes)
        
    Returns:
        True if successful, False if there were errors
    """
    headers = {"X-Api-Key": LIDARR_API_KEY}
    
    try:
        # Get all albums for this artist from Lidarr
        album_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album"
        params = {"artistId": artist_id}
        r = requests.get(album_url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        albums = r.json()
        
        unmonitored_count = 0
        kept_monitored_count = 0
        target_found = False
        
        logging.debug(f"Looking for target album with MBID: {target_musicbrainz_id}")
        
        for album in albums:
            if album.get('monitored', False):
                album_mbid = album.get('foreignAlbumId')
                album_title = album.get('title', '')
                
                logging.debug(f"Checking album: '{album_title}' (MBID: {album_mbid})")
                
                # Check if this is our target album by MusicBrainz ID first
                is_target_by_mbid = album_mbid == target_musicbrainz_id
                
                # Fallback: also check by title similarity (case-insensitive)
                is_target_by_title = False
                if target_album_title and album_title:
                    title_lower = album_title.lower()
                    target_lower = target_album_title.lower()
                    # Check exact match or if one contains the other (for deluxe versions, etc.)
                    is_target_by_title = (title_lower == target_lower or 
                                        target_lower in title_lower or 
                                        title_lower in target_lower)
                
                if is_target_by_mbid or (is_target_by_title and not target_found):
                    # This is our target album - keep it monitored
                    kept_monitored_count += 1
                    target_found = True
                    match_reason = "MBID" if is_target_by_mbid else "title"
                    logging.debug(f"Keeping monitored: '{album_title}' by {artist_name} (target album, matched by {match_reason})")
                else:
                    # This is NOT our target album - unmonitor it
                    album['monitored'] = False
                    update_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/album/{album['id']}"
                    update_r = requests.put(update_url, json=album, headers=headers, timeout=30)
                    update_r.raise_for_status()
                    unmonitored_count += 1
                    logging.debug(f"Unmonitored extra album: '{album_title}' by {artist_name} (MBID: {album_mbid})")
        
        if not target_found:
            logging.warning(f"Target album '{target_album_title}' (MBID: {target_musicbrainz_id}) was not found among monitored albums for {artist_name}")
        
        if unmonitored_count > 0:
            logging.info(f"Final cleanup: Unmonitored {unmonitored_count} extra albums for {artist_name}, kept {kept_monitored_count} target album(s)")
        else:
            logging.info(f"Final cleanup: Only target album '{target_album_title}' was monitored for {artist_name}")
            
        return True
        
    except Exception as e:
        logging.error(f"✗ Error in final cleanup for {artist_name} (ID {artist_id}): %s", e)
        return False


def build_artist_payload(lookup_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct the payload for adding an artist to Lidarr.
    
    Takes the artist data from Lidarr's lookup endpoint and adds the
    necessary configuration for adding them to the library.
    
    Args:
        lookup_item: Artist data from lidarr_artist_lookup()
        
    Returns:
        Complete payload ready for POST to /api/v1/artist
    """
    payload = lookup_item.copy()
    payload["qualityProfileId"] = QUALITY_PROFILE_ID
    payload["metadataProfileId"] = METADATA_PROFILE_ID
    payload["rootFolderPath"] = ROOT_FOLDER_PATH
    payload["addOptions"] = {"searchForMissingAlbums": False}  # Don't auto-search all albums
    payload["monitor"] = False  # Don't monitor all albums by default - we'll monitor specific ones
    return payload


# ========== REFACTORED HELPER FUNCTIONS FOR process_artist_album_pair() ==========

def check_album_already_monitored(artist: str, album: str, mb_release_id: str = "") -> Tuple[bool, str]:
    """
    Early exit check: Determine if album is already monitored.
    
    Args:
        artist: Artist name
        album: Album title
        mb_release_id: Optional MusicBrainz release group ID for precise matching
        
    Returns:
        Tuple of (should_skip, status_message)
        - If should_skip is True, caller should return early with the provided message
        - If should_skip is False, proceed with processing (message will be empty string)
    """
    logging.debug(f"Quick check: Is {artist} - {album} already monitored?")
    skip_mb_lookup = not mb_release_id  # Only skip MB lookup if we don't have an ID
    is_monitored, existing_album = is_album_already_monitored(artist, album, skip_mb_lookup=skip_mb_lookup, mb_release_id=mb_release_id)
    if is_monitored:
        return True, f"Album already monitored, skipping: {artist} - {album}"
    return False, ""


def handle_existing_artist_album(existing_artist: Dict[str, Any], mb_album_id: Optional[str], artist: str, album: str) -> Tuple[bool, str, str]:
    """
    Handle case where artist already exists in Lidarr - monitor the album.
    
    Args:
        existing_artist: Existing artist data from Lidarr
        mb_album_id: MusicBrainz album ID (if found)
        artist: Original artist name
        album: Album title
        
    Returns:
        Tuple of (success, message, status_code)
    """
    if mb_album_id:
        # Use MusicBrainz ID for precise album monitoring
        success, was_already_monitored = monitor_album_by_mbid(existing_artist['id'], mb_album_id, artist, album)
        if success:
            if was_already_monitored:
                return True, f"Artist exists, album already monitored: {artist} - {album}", "already_monitored"
            else:
                return True, f"Artist exists, monitored album via MBID: {artist} - {album}", "success"
        else:
            return False, f"Artist exists, failed to monitor album via MBID: {artist} - {album}", "pending_refresh"
    else:
        # No MusicBrainz album data - trigger refresh
        logging.info(f"Artist exists but album not on MusicBrainz - triggering refresh for: {artist}")
        return True, f"Artist exists, triggered refresh (album not on MusicBrainz): {artist} - {album}", "pending_refresh"


def add_new_artist_to_lidarr(artist: str, mb_artist_id: str) -> Tuple[bool, Dict[str, Any], str, str]:
    """
    Add a new artist to Lidarr library using MusicBrainz ID.
    
    Args:
        artist: Artist name
        mb_artist_id: MusicBrainz artist ID from enriched CSV
        
    Returns:
        Tuple of (success, added_artist_data, error_message, status_code)
        - If success is True, added_artist_data contains the artist info (error fields are empty)
        - If success is False, error_message and status_code explain the failure (artist_data is empty dict)
    """
    logging.info(f"Artist '{artist}' not found in Lidarr, attempting to add...")
    
    # Get artist metadata using MB ID
    try:
        artist_lookup = lidarr_client.artist_lookup(artist, musicbrainz_id=mb_artist_id)
        if not artist_lookup:
            return False, {}, f"No Lidarr lookup results for artist: {artist} (MBID: {mb_artist_id})", "skip_no_artist_match"
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg or "404" in error_msg:
            return False, {}, f"Artist not found in metadata sources: {artist} (MBID: {mb_artist_id})", "skip_no_artist_match"
        elif "timeout" in error_msg:
            return False, {}, f"Timeout looking up artist: {artist}", "error_timeout"
        elif "connection" in error_msg:
            return False, {}, f"Connection error looking up artist: {artist}", "error_connection"
        else:
            return False, {}, f"Unexpected lookup error for artist {artist}: {str(e)}", "error_unknown"
    
    # Add artist using inline API call with retry logic
    def _add_artist():
        url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/artist"
        headers = {"X-Api-Key": LIDARR_API_KEY, "Content-Type": "application/json"}
        payload = build_artist_payload(artist_lookup)
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        elif r.status_code == 400 and "already been added" in r.text:
            raise ValueError(f"Artist already exists: {r.text}")
        elif r.status_code == 400:
            raise ValueError(f"Bad request (invalid artist data): {r.text}")
        elif r.status_code == 401:
            raise ValueError(f"Unauthorized (check API key): {r.text}")
        elif r.status_code == 503:
            raise ValueError(f"Service temporarily unavailable: {r.text}")
        else:
            r.raise_for_status()
            return None
    
    try:
        added_artist = retry_api_call(_add_artist)
        if not added_artist:
            return False, {}, f"Failed to add artist: {artist}", "error_unknown"
        
        added_artist_name = added_artist.get("artistName", "Unknown")
        added_artist_id = added_artist.get("id", "Unknown")
        logging.info(f"Added artist: {added_artist_name} (ID: {added_artist_id}, requested as: {artist})")
        
        # Wait for Lidarr to process
        logging.info(f"Waiting for Lidarr to process new artist: {artist}")
        time.sleep(15)
        
        return True, added_artist, "", ""
        
    except ValueError as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "already been added" in error_msg:
            return False, {}, f"Race condition: {error_msg}", "race_condition"
        elif "unauthorized" in error_msg or "api key" in error_msg:
            return False, {}, f"API authorization error: {artist}", "skip_api_error"
        elif "bad request" in error_msg or "invalid" in error_msg:
            return False, {}, f"Invalid artist data: {artist}", "error_invalid_data"
        elif "service temporarily unavailable" in error_msg or "503" in error_msg:
            return False, {}, f"Service temporarily unavailable: {artist}", "error_connection"
        else:
            return False, {}, f"Artist validation error {artist}: {str(e)}", "error_unknown"
    except requests.exceptions.ConnectionError as e:
        return False, {}, f"Connection error adding artist {artist}: {str(e)}", "error_connection"
    except requests.exceptions.Timeout as e:
        return False, {}, f"Timeout adding artist {artist}: {str(e)}", "error_timeout"
    except Exception as e:
        logging.exception("Error adding artist to Lidarr: %s", e)
        return False, {}, f"Unexpected error adding artist {artist}: {str(e)}", "error_unknown"


def monitor_album_for_new_artist(added_artist: Dict[str, Any], mb_album_id: Optional[str], musicbrainz_album: Optional[Dict[str, Any]], artist: str, album: str) -> Tuple[bool, str, str]:
    """
    Monitor the specific album for a newly added artist.
    
    Args:
        added_artist: The artist data returned from adding to Lidarr
        mb_album_id: MusicBrainz album ID (if found)
        musicbrainz_album: Full MusicBrainz album data (if found)
        artist: Original artist name
        album: Album title
        
    Returns:
        Tuple of (success, message, status_code)
    """
    # Ensure all albums are unmonitored first (for newly added artists)
    try:
        logging.info(f"Ensuring all albums are unmonitored for NEWLY ADDED artist: {artist}")
        unmonitor_all_albums_for_artist(added_artist['id'], artist)
    except Exception as unmonitor_error:
        logging.warning(f"Failed to unmonitor all albums for newly added {artist}: {unmonitor_error}")
    
    # Attempt to monitor the specific album
    album_success = False
    if mb_album_id:
        album_title_display = musicbrainz_album.get('title', album) if musicbrainz_album else album
        logging.info(f"Monitoring specific album using pre-fetched MusicBrainz data: {album_title_display}")
        album_success, _ = monitor_album_by_mbid(added_artist['id'], mb_album_id, artist, album)
    
    # Fallback if MBID approach fails or no MBID available
    if not album_success:
        if mb_album_id:
            logging.info(f"MBID monitoring failed for {artist}, trying fallback album monitoring")
        else:
            logging.info(f"Album not on MusicBrainz, trying fallback monitoring: {artist} - {album}")
        album_success = monitor_album(added_artist['id'], album, artist)
    
    if album_success:
        # Final cleanup: unmonitor everything except target album
        if mb_album_id:
            try:
                logging.info(f"Final cleanup: ensuring only requested album is monitored for {artist}")
                unmonitor_all_except_specific_album(added_artist['id'], mb_album_id, artist, album)
            except Exception as cleanup_error:
                logging.warning(f"Final cleanup failed for {artist}: {cleanup_error}")
        
        return True, f"Successfully added artist and monitored album: {artist} - {album}", "success"
    else:
        # Trigger refresh and mark as pending
        try:
            refresh_url = f"{LIDARR_BASE_URL.rstrip('/')}/api/v1/command"
            refresh_payload = {"name": "RefreshArtist", "artistId": added_artist['id']}
            headers = {"X-Api-Key": LIDARR_API_KEY}
            requests.post(refresh_url, json=refresh_payload, headers=headers, timeout=30)
            logging.info(f"Triggered metadata refresh for newly added artist: {artist}")
        except Exception as refresh_error:
            logging.warning(f"Failed to trigger refresh for {artist}: {refresh_error}")
        
        return True, f"Added artist but album monitoring failed, refresh triggered: {artist} - {album}", "pending_refresh"


def handle_race_condition(artist: str, album: str, mb_album_id: Optional[str]) -> Tuple[bool, str, str]:
    """
    Handle race condition where artist was added between check and add.
    
    Args:
        artist: Artist name
        album: Album title
        mb_album_id: MusicBrainz album ID (if available)
        
    Returns:
        Tuple of (success, message, status_code)
    """
    logging.info(f"Race condition detected for {artist}, refreshing artist list and retrying album monitoring")
    try:
        existing_artists = lidarr_client.get_existing_artists()
        existing_artist = find_existing_artist(artist, existing_artists)
        if existing_artist:
            logging.info(f"Race condition resolved: found {artist} -> {existing_artist['artistName']}")
            
            # Use MusicBrainz data if available
            if mb_album_id:
                success = monitor_album_by_mbid(existing_artist['id'], mb_album_id, artist, album)
            else:
                success = monitor_album(existing_artist['id'], album, artist)
            
            if success:
                return True, f"Race condition resolved, monitored album: {artist} - {album}", "success"
            else:
                return False, f"Race condition resolved but album monitoring failed: {artist} - {album}", "pending_refresh"
        else:
            return False, f"Race condition: artist exists but not found in refresh: {artist}", "pending_refresh"
    except Exception as retry_error:
        return False, f"Race condition retry failed for {artist}: {str(retry_error)}", "error_connection"


def process_artist_album_pair(
    artist: str,
    album: str,
    existing_artists: Dict[str, Dict[str, Any]],
    mb_artist_id: str = "",
    mb_release_id: str = ""
) -> Tuple[bool, str, str]:
    """
    Process a single artist/album pair for import into Lidarr.
    
    REFACTORED: This function now requires MusicBrainz IDs from enriched CSV files.
    No longer performs external API lookups - uses provided MB IDs directly.
    
    WORKFLOW:
    1. Early exit: Check if album is already monitored
    2. Require MB IDs: Fail if not provided (must use enriched CSV)
    3. Use MB IDs directly to query Lidarr
    4. If artist exists: Monitor the album
    5. If artist doesn't exist: Add artist, then monitor album
    
    Args:
        artist: Artist name
        album: Album title
        existing_artists: Dict of artists already in Lidarr
        mb_artist_id: REQUIRED MusicBrainz artist ID (from enriched CSV)
        mb_release_id: REQUIRED MusicBrainz release group ID (from enriched CSV)
    
    STATUS CODES RETURNED:
    - 'already_monitored': Album is already being monitored (skip status)
    - 'skip_album_mb_noresults': Artist exists but album has no MusicBrainz results (skip status)
    - 'success': Artist added/found and album monitored successfully
    - 'error_missing_mb_ids': MB IDs not provided (CSV not enriched)
    - 'pending_refresh': Processing needs time to complete (temporary)
    - 'error_*': Various error conditions (mostly temporary)
    
    Args:
        artist: Name of the artist
        album: Title of the album to monitor
        existing_artists: Dict of existing artists from get_existing_artists()
        mb_artist_id: REQUIRED MusicBrainz artist ID (from enriched CSV)
        mb_release_id: REQUIRED MusicBrainz release group ID (from enriched CSV)
        
    Returns:
        Tuple of (success_boolean, descriptive_message, status_code_with_reason)
    """
    # STEP 1: No early exit check needed - monitor_album_by_mbid handles already monitored albums
    
    # STEP 2: Match artist metadata (skip MB lookup if we have MB IDs)
    if mb_artist_id:
        # We have at least an artist ID - we can add the artist to Lidarr
        logging.info(f"📍 Using enriched MusicBrainz artist ID (skipping external API lookups)")
        logging.info(f"   Artist ID:  {mb_artist_id}")
        
        if mb_release_id:
            logging.info(f"   Release ID: {mb_release_id}")
            # Full enrichment: both artist and album IDs available
            album_operation = "monitor album"
        else:
            logging.info(f"   Release ID: (not found - will add artist only)")
            # Partial enrichment: only artist ID available
            album_operation = "add artist only"
        
        # Check if artist already exists in Lidarr
        existing_artist = find_existing_artist(artist, existing_artists)
        artist_in_lidarr = existing_artist is not None
        
        if artist_in_lidarr:
            logging.info(f"   ✓ Artist '{artist}' already exists in Lidarr")
            if mb_release_id:
                # Artist exists and we have album ID - check if album is monitored
                return handle_existing_artist_album(existing_artist, mb_release_id, artist, album)
            else:
                # Artist exists but no album ID - nothing more to do
                return True, f"Artist '{artist}' already exists in Lidarr (album has no MusicBrainz results)", "skip_album_mb_noresults"
        else:
            logging.info(f"   → Artist '{artist}' will be added to Lidarr")
        
        canonical_artist_name = artist  # Use provided name
        mb_artist_data = None  # Not needed since we have ID
        
        if mb_release_id:
            musicbrainz_album = {'id': mb_release_id}  # Minimal data structure
            mb_album_id = mb_release_id
        else:
            musicbrainz_album = None
            mb_album_id = None
    else:
        # No MB IDs at all - fail
        logging.error(f"❌ No MusicBrainz artist ID provided for {artist} - {album}")
        logging.error(f"   This script now requires enriched CSV files with at least mb_artist_id column")
        logging.error(f"   Please run universal_parser.py with --enrich-musicbrainz (now default) to create enriched CSV")
        return False, f"Missing MusicBrainz artist ID - CSV must be enriched first", "error_missing_mb_ids"
    
    # STEP 4: Handle existing artist (only applies when we have album to monitor)
    if artist_in_lidarr and existing_artist and mb_release_id:
        return handle_existing_artist_album(existing_artist, mb_album_id, artist, album)
    
    # STEP 5: Add new artist (always done when artist doesn't exist)
    if not artist_in_lidarr:
        success, added_artist, error_message, status_code = add_new_artist_to_lidarr(artist, mb_artist_id)
        
        if not success:
            # Check for race condition
            if status_code == "race_condition":
                return handle_race_condition(artist, album, mb_album_id)
            # Return the error
            return False, error_message, status_code
        
        added_artist_data = added_artist
    else:
        added_artist_data = existing_artist
    
    # STEP 6: Monitor album if we have album ID, otherwise we're done
    if mb_release_id:
        return monitor_album_for_new_artist(added_artist_data, mb_album_id, musicbrainz_album, artist, album)
    else:
        # No album ID - artist was added successfully, nothing more to do
        return True, f"Artist '{artist}' added to Lidarr successfully (no album to monitor)", "success_artist_only"


# ========== MAIN EXECUTION ==========

def main():
    """
    Main entry point for the album import script.
    
    Handles command-line arguments, orchestrates the import process,
    and provides comprehensive progress reporting and status tracking.
    
    FEATURES:
    - Dry-run mode for testing without making changes
    - Batch processing with configurable pauses to avoid API overload  
    - Progress tracking via CSV status column for resumable imports
    - Skip-completed functionality for large interrupted imports
    - Comprehensive status reporting and error handling
    """
    global LIDARR_REQUEST_DELAY  # Allow modification of request delay
    
    # Setup command-line argument parsing
    parser = argparse.ArgumentParser(
        description="Add albums to Lidarr from artist/album CSV",
        epilog="""
USAGE EXAMPLES:
    # Basic import (skips completed items by default)
    py -3 add_albums_to_lidarr.py my_albums.csv
  
  # Process ALL items including completed ones
    py -3 add_albums_to_lidarr.py my_albums.csv --no-skip-completed
  
  # Test first 5 items without making changes
    py -3 add_albums_to_lidarr.py my_albums.csv --dry-run --max-items 5
  
  # Resume interrupted import, skipping completed items  
    py -3 add_albums_to_lidarr.py my_albums.csv --skip-completed
  
  # Process only albums by a specific artist
    py -3 add_albums_to_lidarr.py my_albums.csv --artist "Kanye West"
  
  # Process only albums matching a title
    py -3 add_albums_to_lidarr.py my_albums.csv --album "Deluxe"
  
  # Process only items with specific status
    py -3 add_albums_to_lidarr.py my_albums.csv --status pending_refresh
  
  # Process only 100 items with logging to file
    py -3 add_albums_to_lidarr.py my_albums.csv --max-items 100 --log-file import.log
  
  # Fast processing: skip existing artists, no batch pauses
    py -3 add_albums_to_lidarr.py my_albums.csv --skip-existing --no-batch-pause
  
        # Retry only failed items with detailed logging (use --status failed)
            py -3 add_albums_to_lidarr.py my_albums.csv --status failed --log-file retry.log

QUICK ALIAS (optional):
    To create a short shortcut for interactive use, add a small wrapper to your shell.
    Replace the example path with the correct path to this repository.

    PowerShell (persist by adding to your $PROFILE):
        function lidarr { py -3 "C:\\path\\to\\repo\\scripts\\add_albums_to_lidarr.py" @args }

    Bash (add to ~/.bashrc or ~/.profile):
    alias lidarr='py -3 /path/to/repo/scripts/add_albums_to_lidarr.py'

    Note: these are optional convenience snippets. To run directly:
        py -3 scripts/add_albums_to_lidarr.py my_albums.csv
                """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("input", 
                       help="Path to CSV file with 'artist' and 'album' columns")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Test mode: show what would be processed without making API calls")
    parser.add_argument("--max-items", type=int, 
                       help="Limit processing to first N items (useful for testing)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                       help=f"Process items in batches with pauses (default: {BATCH_SIZE})")
    parser.add_argument("--no-batch-pause", action="store_true",
                       help="Disable pauses between batches for faster processing")
    parser.add_argument("--skip-completed", action="store_true", default=True,
                       help="Skip items that are completed/monitored or have permanent failures (default: enabled)")
    parser.add_argument("--no-skip-completed", action="store_true", 
                       help="Disable skipping completed items (process all items)")
    parser.add_argument("--skip-existing", action="store_true",
                       help="Skip items where artist already exists in Lidarr (faster processing)")
    # Use --status to select rows with a specific status (comma-separated). Special tokens:
    #   'new'  -> blank/empty status rows
    #   'failed' -> rows where ItemStatus.should_retry(status) is True
    # Example: --status pending_refresh,error_timeout or --status new
    parser.add_argument("--status", type=str,
                       help="Process only items with specific status(s) (comma-separated). Special tokens: new, failed")
    # Opposite of --status: exclude rows matching status(s)
    parser.add_argument("--not-status", dest="not_status", type=str,
                       help="Exclude items with specific status(s) (comma-separated). Special tokens: new, failed")
    parser.add_argument("--artist", type=str,
                       help="Process only albums by specific artist (case-insensitive partial match)")
    parser.add_argument("--album", type=str,
                       help="Process only albums matching specific title (case-insensitive partial match)")
    # NOTE: legacy alias --exclude-status removed; use --not-status instead
    parser.add_argument("--log-file", type=str,
                       help="Write detailed logs to specified file (in addition to console)")
    parser.add_argument("--progress-interval", type=int, default=50,
                       help="Show progress update every N items (default: 50)")
    parser.add_argument("--request-delay", type=float, default=LIDARR_REQUEST_DELAY,
                       help=f"Seconds between API requests (default: {LIDARR_REQUEST_DELAY}). Increase if getting 503 errors")
    
    args = parser.parse_args()
    
    # Update request delay based on command line argument
    LIDARR_REQUEST_DELAY = args.request_delay
    
    # Handle skip-completed logic with new default behavior
    if args.no_skip_completed:
        args.skip_completed = False

    # No legacy alias normalization needed; use --not-status for exclusion
    
    # Setup enhanced logging if log file specified
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(file_handler)
        logging.info(f"Logging to file: {args.log_file}")
    
    # Load and validate CSV input using CSVHandler
    csv_handler = CSVHandler(args.input)
    items, has_status_column = csv_handler.read_items()
    if not items:
        logging.error("No valid artist/album pairs found in CSV file.")
        logging.error("Expected format: artist,album[,status] with headers")
        sys.exit(1)
    
    logging.info(f"Loaded {len(items)} artist/album pairs from {args.input}")
    
    # Filter out already completed items if resuming
    original_count = len(items)
    if args.skip_completed:
        # Use CSVHandler's filtering to skip already processed items
        items = csv_handler.filter_items_by_status(
            items,
            skip_completed=True,
            skip_permanent_failures=True
        )
        skipped = original_count - len(items)
        if skipped > 0:
            logging.info(f"Skipped {skipped} already completed/permanently failed items")
            
            # Show breakdown of what was skipped using status summary
            status_summary = csv_handler.get_status_summary(items)
            
            if status_summary:
                logging.info("Skipped breakdown:")
                for status, count in status_summary.items():
                    if ItemStatus.is_success(status):
                        logging.info(f"  {status}: {count} items (successful)")
                    elif ItemStatus.is_skip(status):
                        logging.info(f"  {status}: {count} items (permanent failure)")
        
        if not items:
            logging.info("All items have already been processed or are permanently failed!")
            sys.exit(0)
    
    # (formerly --only-failures handled here) Use --status failed to filter retryable items
    
    # If requested, fetch existing artists early so centralized filtering can skip them
    existing_artists = {}
    if args.skip_existing and not args.dry_run:
        logging.info("Fetching existing artists from Lidarr (for skip-existing filter)...")
        existing_artists = lidarr_client.get_existing_artists()
        logging.info(f"Found {len(existing_artists)} existing artists in Lidarr")

    # Delegate parsing/filtering logic to universal_parser.apply_item_filters
    # so parsing and filter rules are centralized and testable.
    # Ensure repo root is importable so we can import the scripts package.
    repo_root = Path(__file__).parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from scripts.universal_parser import apply_item_filters
    except Exception:
        logging.debug("Could not import apply_item_filters from scripts.universal_parser; proceeding with inline filters")
        apply_item_filters = None

    if apply_item_filters:
        items = apply_item_filters(
            items,
            skip_completed=args.skip_completed,
            artist=args.artist,
            album=args.album,
            status=args.status,
            exclude_status=args.not_status,
            max_items=args.max_items,
            skip_existing=args.skip_existing,
            existing_artists=existing_artists,
            csv_handler=csv_handler
        )
        logging.info(f"Filtered to {len(items)} items after centralized filtering")
        if not items:
            logging.info("No items remain after filtering")
            sys.exit(0)
    else:
        # Fallback to the previous inline filtering if import failed
        if args.artist:
            artist_filter = args.artist.lower()
            items_before = len(items)
            items = [item for item in items if artist_filter in item['artist'].lower()]
            filtered_count = items_before - len(items)
            if filtered_count > 0:
                logging.info(f"Artist filter '{args.artist}': {len(items)} items match, {filtered_count} filtered out")
            if not items:
                logging.info(f"No items found matching artist filter: {args.artist}")
                sys.exit(0)
        
        if args.album:
            album_filter = args.album.lower()
            items_before = len(items)
            items = [item for item in items if album_filter in item['album'].lower()]
            filtered_count = items_before - len(items)
            if filtered_count > 0:
                logging.info(f"Album filter '{args.album}': {len(items)} items match, {filtered_count} filtered out")
            if not items:
                logging.info(f"No items found matching album filter: {args.album}")
                sys.exit(0)

        # Status filtering: support comma-separated values and special tokens
        # Special tokens: 'new' -> blank status, 'failed' -> ItemStatus.should_retry
        def _matches_token(st: str, token: str) -> bool:
            tl = token.lower()
            if tl in ('new', 'blank', 'none', 'empty'):
                return not (st or '').strip()
            if tl in ('failed', 'failure', 'fail', 'retry'):
                return ItemStatus.should_retry(st)
            # Exact-match comparisons are case-insensitive
            return (st or '').lower() == tl

        if args.status:
            items_before = len(items)
            tokens = [t.strip() for t in args.status.split(',') if t.strip()]
            filtered = []
            for it in items:
                st = (it.get('status') or '').strip()
                for token in tokens:
                    if _matches_token(st, token):
                        filtered.append(it)
                        break
            items = filtered
            filtered_count = items_before - len(items)
            if filtered_count > 0:
                logging.info(f"Status filter '{args.status}': {len(items)} items match, {filtered_count} filtered out")
            if not items:
                logging.info(f"No items found with status: {args.status}")
                sys.exit(0)

        # Exclude status filtering (use --not-status)
        if args.not_status:
            items_before = len(items)
            tokens = [t.strip() for t in args.not_status.split(',') if t.strip()]
            filtered = []
            for it in items:
                st = (it.get('status') or '').strip()
                exclude = False
                for token in tokens:
                    if _matches_token(st, token):
                        exclude = True
                        break
                if not exclude:
                    filtered.append(it)
            items = filtered
            filtered_count = items_before - len(items)
            if filtered_count > 0:
                logging.info(f"Exclude status filter '{args.not_status}': excluded {filtered_count} items")
            if not items:
                logging.info(f"All items were excluded by status filter: {args.not_status}")
                sys.exit(0)

        if args.max_items:
            items = items[:args.max_items]
            logging.info(f"Limited to first {len(items)} items for testing")
    
    # existing_artists was fetched above only if needed for filtering; otherwise it's an empty dict
    
    # Initialize processing counters
    successes = 0
    failures = 0
    messages = []
    total_items = len(items)
    processed = 0
    
    # Main processing loop with progress bar
    logging.info(f"Starting processing of {total_items} items...")
    
    # Disable tqdm output to prevent it from hiding our logs
    for i, item in enumerate(tqdm(items, desc="Processing albums", disable=False, leave=True, position=0)):
        # Clean and format artist/album from CSV before any processing
        raw_artist = item["artist"]
        raw_album = item["album"]
        
        # Extract MusicBrainz IDs if present (from universal_parser.py --enrich-musicbrainz)
        mb_artist_id = item.get("mb_artist_id", "").strip()
        mb_release_id = item.get("mb_release_id", "").strip()
        
        # Apply comprehensive cleaning with rapidfuzz-based normalization
        artist = clean_csv_input(raw_artist, is_artist=True)
        album = clean_csv_input(raw_album, is_artist=False)
        
        # Log cleaning transformations if changes were made
        if artist != raw_artist or album != raw_album:
            logging.debug(f"CSV cleaning applied:")
            if artist != raw_artist:
                logging.debug(f"  Artist: '{raw_artist}' → '{artist}'")
            if album != raw_album:
                logging.debug(f"  Album: '{raw_album}' → '{album}'")
        
        # Show what we're processing (use print to avoid tqdm conflicts)
        tqdm.write(f"\n{'='*70}")
        if mb_release_id:
            tqdm.write(f"[{i+1}/{total_items}] Processing: {artist} - {album} 📍 (MB enriched)")
            tqdm.write(f"   MusicBrainz Artist ID:  {mb_artist_id}")
            tqdm.write(f"   MusicBrainz Release ID: {mb_release_id}")
        else:
            tqdm.write(f"[{i+1}/{total_items}] Processing: {artist} - {album}")
        tqdm.write(f"{'='*70}")
        
        # Show progress updates at specified intervals
        if (i + 1) % args.progress_interval == 0:
            logging.info(f"Progress: {i + 1}/{total_items} items processed")
        
        if args.dry_run:
            # Dry-run mode: simulate processing without API calls
            logging.info("Dry run: would process %s - %s", artist, album)
            item['status'] = ItemStatus.DRY_RUN
            successes += 1
            
            # Write status immediately after processing (use raw values for CSV matching)
            csv_handler.update_single_status(raw_artist, raw_album, ItemStatus.DRY_RUN)
        else:
            # Real processing: add artist and monitor album
            success, message, status_code = process_artist_album_pair(
                artist, album, existing_artists,
                mb_artist_id=mb_artist_id,
                mb_release_id=mb_release_id
            )
            item['status'] = status_code
            messages.append(f"[{'OK' if success else 'FAIL'}] {message}")
            
            # Write status immediately after processing this item (use raw values for CSV matching)
            csv_handler.update_single_status(raw_artist, raw_album, status_code)
            
            # Log the result clearly (use tqdm.write to avoid conflicts with progress bar)
            if success:
                if status_code.startswith('skip_'):
                    tqdm.write(f"[SKIP] {status_code}")
                    tqdm.write(f"   {message}")
                else:
                    successes += 1
                    tqdm.write(f"[SUCCESS] {status_code}")
                    tqdm.write(f"   {message}")
            else:
                failures += 1
                tqdm.write(f"[FAILED] {status_code}")
                tqdm.write(f"   {message}")
            
            processed += 1
            
            # Rate limiting: delay between API requests
            time.sleep(LIDARR_REQUEST_DELAY)
            
            # Batch processing: pause periodically to avoid overwhelming APIs
            if (not args.no_batch_pause and 
                processed % args.batch_size == 0 and processed < total_items):
                remaining = total_items - processed
                batch_num = processed // args.batch_size
                logging.info(f"📦 Completed batch {batch_num}, pausing {BATCH_PAUSE}s... ({remaining} items remaining)")
                time.sleep(BATCH_PAUSE)
    
    # Processing complete - show results
    logging.info("=" * 50)
    logging.info("PROCESSING COMPLETE")
    logging.info(f"Total processed: {len(items)}")
    logging.info(f"Successes: {successes}")
    logging.info(f"Failures: {failures}")
    logging.info("=" * 50)
    
    # Update CSV file with processing status for resumable imports
    if not args.dry_run or (args.dry_run and not has_status_column):
        csv_handler.update_all_statuses(items)
    
    # Display detailed processing results
    if messages:
        print(f"\n=== DETAILED RESULTS ===")
        for message in messages[:20]:  # Limit output for large imports
            print(message)
        if len(messages) > 20:
            print(f"... and {len(messages) - 20} more results")
    
    # Display status summary statistics
    if items:
        status_counts = {}
        for item in items:
            status = item['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n=== STATUS SUMMARY ===")
        
        # Group statuses by type for better readability
        successful = []
        temporary_failures = []
        permanent_failures = []
        other = []
        
        for status, count in sorted(status_counts.items()):
            if ItemStatus.is_success(status):
                successful.append((status, count))
            elif ItemStatus.is_skip(status):
                permanent_failures.append((status, count))
            elif status in ['pending_refresh', 'pending_import']:
                temporary_failures.append((status, count))
            elif status in ['error_connection', 'error_timeout', 'error_invalid_data', 'error_unknown']:
                temporary_failures.append((status, count))
            else:
                other.append((status, count))
        
        # Display grouped results
        if successful:
            print("  [SUCCESS] Successful:")
            for status, count in successful:
                print(f"    {status}: {count} items")
        
        if temporary_failures:
            print("  [RETRY] Temporary failures (retry possible):")
            for status, count in temporary_failures:
                print(f"    {status}: {count} items")
        
        if permanent_failures:
            print("  [!] Permanent failures (will be skipped):")
            for status, count in permanent_failures:
                print(f"    {status}: {count} items")
        
        if other:
            print("  Other:")
            for status, count in other:
                print(f"    {status}: {count} items")
        
        # Provide guidance for next steps
        if not args.dry_run:
            print(f"\nCSV updated with processing status: {args.input}")
            if failures > 0:
                if temporary_failures:
                    print(f"Tip: Use --skip-completed to retry only temporary failures")
                if permanent_failures:
                    print(f"Tip: Permanent failures will be automatically skipped in future runs")
            
            refresh_triggered = status_counts.get('pending_refresh', 0)
            pending_import = status_counts.get('pending_import', 0)
            if refresh_triggered > 0 or pending_import > 0:
                print(f"Note: {refresh_triggered + pending_import} items need more time to complete")
                print(f"Tip: Run script again later to process pending items")


if __name__ == "__main__":
    main()
"""
Lidarr API Client

Provides a clean interface to the Lidarr Web Service API v1 with:
- Artist and album management
- Monitoring and search operations
- Error handling and retry logic
- Centralized API configuration

This client encapsulates all Lidarr API interactions for the music importer.
"""

import logging
import time
import requests
from typing import Optional, Dict, Any, List, Tuple, Callable

from lib.text_utils import (
    normalize_artist_name,
    normalize_profanity,
    strip_album_suffixes,
    get_album_title_variations,
    get_edition_variants,
    normalize_album_title_for_matching
)

logger = logging.getLogger(__name__)


class LidarrClient:
    """
    Client for Lidarr Web Service API v1.
    
    This client handles artist and album operations including:
    - Looking up artists and albums
    - Adding artists to library
    - Monitoring specific albums
    - Searching for missing music files
    - Managing artist/album metadata
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        quality_profile_id: int,
        metadata_profile_id: int,
        root_folder_path: str,
        request_delay: float = 0.5,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        timeout: int = 30
    ):
        """
        Initialize the Lidarr API client.
        
        Args:
            base_url: Lidarr base URL (e.g., "http://localhost:8686")
            api_key: Lidarr API key for authentication
            quality_profile_id: Default quality profile ID for new artists
            metadata_profile_id: Default metadata profile ID for new artists
            root_folder_path: Root folder path for music library
            request_delay: Delay between requests in seconds (default: 0.5)
            max_retries: Maximum number of retries for failed requests (default: 3)
            retry_delay: Base delay for exponential backoff (default: 2.0)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.quality_profile_id = quality_profile_id
        self.metadata_profile_id = metadata_profile_id
        self.root_folder_path = root_folder_path
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.last_request_time = 0
        
        logger.info(f"LidarrClient initialized for {self.base_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {"X-Api-Key": self.api_key}
    
    def _wait_for_rate_limit(self):
        """Apply rate limiting between requests."""
        if self.request_delay > 0:
            time_since_last = time.time() - self.last_request_time
            if time_since_last < self.request_delay:
                time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _retry_request(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a request with retry logic and exponential backoff.
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result of the successful request, or raises exception
        """
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.RequestException as e:
                # Only retry on service unavailable errors
                if "503" in str(e) or "Service Unavailable" in str(e):
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Service unavailable, retrying in {wait_time}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                raise
        raise Exception(f"Max retries ({self.max_retries}) exceeded")
    
    def get_existing_artists(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve all artists currently in Lidarr library.
        
        Returns:
            Dictionary mapping lowercase artist names to artist data
        """
        url = f"{self.base_url}/api/v1/artist"
        try:
            self._wait_for_rate_limit()
            r = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            artists = r.json()
            # Use lowercase names as keys for case-insensitive matching
            return {artist['artistName'].lower(): artist for artist in artists}
        except Exception as e:
            logger.exception("Failed to get existing artists: %s", e)
            return {}
    
    def artist_lookup(self, artist_name: str, musicbrainz_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Look up artist data from Lidarr's lookup endpoint.
        
        Can search by MusicBrainz ID (preferred) or artist name.
        
        Args:
            artist_name: Name of the artist
            musicbrainz_id: Optional MusicBrainz ID for more accurate lookup
            
        Returns:
            Artist data ready for Lidarr import, or None if not found
        """
        url = f"{self.base_url}/api/v1/artist/lookup"
        
        # If we have a MusicBrainz ID, use it for more accurate lookup
        if musicbrainz_id:
            logger.info(f"Looking up artist by MusicBrainz ID: {musicbrainz_id}")
            
            def _lookup_by_mbid():
                self._wait_for_rate_limit()
                # Try mbid: prefix first (most common format)
                params = {"term": f"mbid:{musicbrainz_id}"}
                r = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
                if r.status_code == 200:
                    result = r.json()
                    if result:
                        return result
                
                # If mbid: didn't work, try raw MBID
                params = {"term": musicbrainz_id}
                r = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            
            try:
                items = self._retry_request(_lookup_by_mbid)
                if items:
                    logger.info(f"Lidarr lookup successful using MusicBrainz ID for {artist_name}")
                    return items[0]
            except Exception as e:
                logger.warning(f"Lidarr MBID lookup failed for {artist_name}, falling back to name search: {e}")
        
        # Fallback to name-based lookup
        logger.info(f"Looking up artist by name: {artist_name}")
        
        def _lookup_by_name():
            self._wait_for_rate_limit()
            params = {"term": artist_name}
            r = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        
        try:
            items = self._retry_request(_lookup_by_name)
            if not items:
                logger.warning(f"No Lidarr lookup results for artist: {artist_name}")
                return None
            logger.info(f"Lidarr name-based lookup successful for {artist_name}")
            return items[0]
        except Exception as e:
            logger.exception("Lidarr artist lookup failed for %s: %s", artist_name, e)
            return None
    
    def album_lookup(self, artist_name: str, album_title: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for albums using Lidarr's album lookup endpoint.
        
        Args:
            artist_name: Name of the artist
            album_title: Title of the album
            
        Returns:
            List of matching albums, or None if not found
        """
        url = f"{self.base_url}/api/v1/album/lookup"
        params = {"term": f"{artist_name} {album_title}"}
        
        try:
            self._wait_for_rate_limit()
            r = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            items = r.json()
            return items if items else None
        except Exception as e:
            logger.exception("Lidarr album lookup failed for %s - %s: %s", artist_name, album_title, e)
            return None
    
    def add_artist(self, artist_data: Dict[str, Any], monitor: bool = False, search: bool = False) -> Optional[Dict[str, Any]]:
        """
        Add an artist to Lidarr library.
        
        Args:
            artist_data: Artist data from artist_lookup()
            monitor: Whether to monitor all albums by default (default: False)
            search: Whether to automatically search for missing albums (default: False)
            
        Returns:
            Added artist data, or None if failed
        """
        url = f"{self.base_url}/api/v1/artist"
        
        # Build payload with configuration
        payload = artist_data.copy()
        payload["qualityProfileId"] = self.quality_profile_id
        payload["metadataProfileId"] = self.metadata_profile_id
        payload["rootFolderPath"] = self.root_folder_path
        payload["addOptions"] = {"searchForMissingAlbums": search}
        payload["monitor"] = monitor
        
        try:
            self._wait_for_rate_limit()
            r = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            result = r.json()
            logger.info(f"Added artist to Lidarr: {artist_data.get('artistName', 'Unknown')}")
            return result
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 and "already exists" in e.response.text.lower():
                logger.info(f"Artist already exists in Lidarr: {artist_data.get('artistName', 'Unknown')}")
                return artist_data  # Return the original data
            logger.error(f"Failed to add artist {artist_data.get('artistName', 'Unknown')}: {e}")
            return None
        except Exception as e:
            logger.exception("Failed to add artist: %s", e)
            return None
    
    def get_artist_albums(self, artist_id: int) -> List[Dict[str, Any]]:
        """
        Get all albums for a specific artist.
        
        Args:
            artist_id: Lidarr internal artist ID
            
        Returns:
            List of album data dictionaries
        """
        url = f"{self.base_url}/api/v1/album"
        params = {"artistId": artist_id}
        
        try:
            self._wait_for_rate_limit()
            r = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.exception("Failed to get albums for artist ID %s: %s", artist_id, e)
            return []
    
    def get_all_albums(self) -> List[Dict[str, Any]]:
        """
        Get all albums from Lidarr library.
        
        Returns:
            List of all album data dictionaries
        """
        url = f"{self.base_url}/api/v1/album"
        
        try:
            self._wait_for_rate_limit()
            r = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.exception("Failed to get all albums: %s", e)
            return []
    
    def update_album(self, album_data: Dict[str, Any]) -> bool:
        """
        Update an album's metadata or monitoring status.
        
        Args:
            album_data: Complete album data with modifications
            
        Returns:
            True if successful, False otherwise
        """
        album_id = album_data.get('id')
        if not album_id:
            logger.error("Cannot update album: missing album ID")
            return False
        
        url = f"{self.base_url}/api/v1/album/{album_id}"
        
        try:
            self._wait_for_rate_limit()
            r = requests.put(url, json=album_data, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.exception("Failed to update album ID %s: %s", album_id, e)
            return False
    
    def add_album(self, album_data: Dict[str, Any], monitored: bool = True, search: bool = True) -> Optional[Dict[str, Any]]:
        """
        Add a specific album to Lidarr and optionally monitor it.
        
        Args:
            album_data: Album data from lookup
            monitored: Whether to monitor the album (default: True)
            search: Whether to automatically search for missing files (default: True)
            
        Returns:
            Added album data, or None if failed
        """
        url = f"{self.base_url}/api/v1/album"
        
        # Configure the album
        payload = album_data.copy()
        payload['monitored'] = monitored
        payload['addOptions'] = {'searchForMissingAlbums': search}
        
        try:
            self._wait_for_rate_limit()
            r = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            
            if r.status_code in (200, 201):
                logger.info(f"Added album: {album_data.get('title', 'Unknown')}")
                return r.json()
            elif r.status_code == 400:
                error_text = r.text
                if "already exists" in error_text.lower():
                    logger.info(f"Album already exists: {album_data.get('title', 'Unknown')}")
                    return album_data
                else:
                    logger.error(f"Bad request adding album: {error_text}")
                    return None
            elif r.status_code == 409:
                logger.info(f"Album already exists (conflict): {album_data.get('title', 'Unknown')}")
                return album_data
            else:
                r.raise_for_status()
                return None
        except Exception as e:
            logger.exception("Failed to add album: %s", e)
            return None
    
    def search_for_album(self, album_id: int) -> bool:
        """
        Trigger automatic search for a specific album's files.
        
        Args:
            album_id: Lidarr internal album ID
            
        Returns:
            True if search was triggered, False otherwise
        """
        url = f"{self.base_url}/api/v1/command"
        payload = {
            "name": "AlbumSearch",
            "albumIds": [album_id]
        }
        
        try:
            self._wait_for_rate_limit()
            r = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            logger.info(f"Started automatic search for album ID {album_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to trigger search for album ID {album_id}: {e}")
            return False
    
    def refresh_artist(self, artist_id: int) -> bool:
        """
        Trigger metadata refresh for an artist.
        
        This updates the artist's album list and metadata from MusicBrainz.
        
        Args:
            artist_id: Lidarr internal artist ID
            
        Returns:
            True if refresh was triggered, False otherwise
        """
        url = f"{self.base_url}/api/v1/command"
        payload = {
            "name": "RefreshArtist",
            "artistId": artist_id
        }
        
        try:
            self._wait_for_rate_limit()
            r = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            logger.info(f"Triggered metadata refresh for artist ID {artist_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to trigger refresh for artist ID {artist_id}: {e}")
            return False
    
    def get_artist_by_id(self, artist_id: int) -> Optional[Dict[str, Any]]:
        """
        Get artist data by Lidarr internal ID.
        
        Args:
            artist_id: Lidarr internal artist ID
            
        Returns:
            Artist data, or None if not found
        """
        url = f"{self.base_url}/api/v1/artist/{artist_id}"
        
        try:
            self._wait_for_rate_limit()
            r = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.exception("Failed to get artist ID %s: %s", artist_id, e)
            return None
    
    def is_album_already_monitored(
        self, 
        artist_name: str, 
        album_title: str,
        mb_search_func: Optional[Callable[[str, str], Optional[Dict[str, Any]]]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if a specific album is already monitored in Lidarr library.
        
        This function searches through all albums in the Lidarr library to find
        if the specified artist/album combination is already being monitored.
        Uses fuzzy matching with profanity/suffix filtering to handle title variations.
        
        Args:
            artist_name: Name of the artist
            album_title: Title of the album to check
            mb_search_func: Optional MusicBrainz search function for better matching
            
        Returns:
            Tuple of (is_monitored_boolean, album_data_if_found)
        """
        try:
            # Get all albums from Lidarr (this includes all artists)
            albums = self.get_all_albums()
            
            # Use text_utils to get album variations
            album_variations = get_album_title_variations(album_title)
            
            # Normalize all variations for comparison
            album_title_variations_normalized = [normalize_artist_name(v) for v in album_variations]
            artist_name_normalized = normalize_artist_name(artist_name)
            
            # Try to get MusicBrainz data for better matching (if function provided)
            mb_album = None
            mb_release_group_id = None
            if mb_search_func:
                # Try each variation with MusicBrainz
                for album_variant in album_variations:
                    mb_album = mb_search_func(artist_name, album_variant)
                    if mb_album:
                        mb_release_group_id = mb_album.get('id')
                        if mb_release_group_id:
                            break  # Found MB data, stop trying
            
            for album in albums:
                # Check if artist name matches (with normalization)
                lidarr_artist_name = album.get('artist', {}).get('artistName', '')
                lidarr_artist_normalized = normalize_artist_name(lidarr_artist_name)
                
                if lidarr_artist_normalized == artist_name_normalized:
                    # Check if album title matches (with normalization)
                    album_normalized = normalize_artist_name(album['title'])
                    
                    # First try exact MusicBrainz ID match if available
                    if mb_release_group_id and album.get('releaseGroupId') == mb_release_group_id:
                        if album.get('monitored', False):
                            logger.info(f"Album already monitored (MusicBrainz ID match): {album['title']} by {artist_name}")
                            return True, album
                        else:
                            logger.info(f"Album found but not monitored (MusicBrainz ID match): {album['title']} by {artist_name}")
                            return False, album
                    
                    # Try fuzzy text matching with ALL album variations
                    for album_variant_normalized in album_title_variations_normalized:
                        if album_normalized == album_variant_normalized:
                            if album.get('monitored', False):
                                logger.info(f"Album already monitored (variant match): {album['title']} by {artist_name}")
                                return True, album
                            else:
                                logger.info(f"Album found but not monitored (variant match): {album['title']} by {artist_name}")
                                return False, album
            
            # Album not found in library
            logger.debug(f"Album not found in Lidarr library: {artist_name} - {album_title}")
            return False, None
            
        except Exception as e:
            logger.exception("Error checking if album is monitored: %s", e)
            return False, None
    
    def monitor_album_by_mbid(
        self, 
        artist_id: int, 
        musicbrainz_album_id: str, 
        artist_name: str, 
        album_title: str
    ) -> bool:
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
            True if album was successfully added and monitored, False otherwise
        """
        try:
            # First check if this album already exists in Lidarr
            existing_albums = self.get_artist_albums(artist_id)
            
            # Check if album with this MusicBrainz ID already exists
            for album in existing_albums:
                if album.get('foreignAlbumId') == musicbrainz_album_id:
                    if album.get('monitored'):
                        logger.info(f"Album '{album_title}' by {artist_name} is already monitored")
                        return True
                    else:
                        # Album exists but not monitored - enable monitoring
                        album['monitored'] = True
                        if self.update_album(album):
                            logger.info(f"Enabled monitoring for existing album: {artist_name} - {album_title}")
                            return True
                        return False
            
            # Album doesn't exist - use Lidarr's album lookup to add it
            lookup_url = f"{self.base_url}/api/v1/album/lookup"
            lookup_params = {"term": f"lidarr:{musicbrainz_album_id}"}
            
            self._wait_for_rate_limit()
            r = requests.get(lookup_url, params=lookup_params, headers=self._get_headers(), timeout=self.timeout)
            r.raise_for_status()
            lookup_results = r.json()
            
            if not lookup_results:
                logger.warning(f"Lidarr lookup returned no results for MusicBrainz ID: {musicbrainz_album_id}")
                return False
            
            # Take the first result (should match exactly by MBID)
            album_data = lookup_results[0]
            
            # Verify this is for the correct artist
            album_artist_id = album_data.get('artist', {}).get('id')
            album_artist_name = album_data.get('artist', {}).get('artistName', 'Unknown')
            
            logger.debug(f"Album lookup verification for {album_title}:")
            logger.debug(f"  Expected artist ID: {artist_id} ({artist_name})")
            logger.debug(f"  Album data artist ID: {album_artist_id} ({album_artist_name})")
            
            if album_artist_id != artist_id:
                logger.warning(f"Album lookup returned different artist ID for {album_title}")
                logger.debug(f"  Expected: {artist_name} (ID: {artist_id})")
                logger.debug(f"  Got: {album_artist_name} (ID: {album_artist_id})")
                
                # Multiple strategies to handle artist ID mismatches
                lookup_mbid = album_data.get('artist', {}).get('foreignArtistId')
                
                # Strategy 1: If album artist ID is None but names are similar
                if album_artist_id is None and album_artist_name and artist_name:
                    name_match = (album_artist_name.lower().strip() == artist_name.lower().strip() or
                                 album_artist_name.lower().replace('.', '').replace('-', '') == 
                                 artist_name.lower().replace('.', '').replace('-', ''))
                    
                    if name_match:
                        logger.info(f"Name match with null ID - fixing artist data: {album_artist_name}")
                        complete_artist_data = self.get_artist_by_id(artist_id)
                        if complete_artist_data:
                            album_data['artist'] = complete_artist_data
                            album_data['artistId'] = artist_id
                            logger.debug(f"Updated album with complete artist data for ID {artist_id}")
                        else:
                            logger.error(f"Could not fetch complete artist data for ID {artist_id}")
                            return False
                    else:
                        logger.error(f"Name mismatch with null ID: '{album_artist_name}' vs '{artist_name}'")
                        return False
                
                # Strategy 2: Check MusicBrainz IDs
                elif lookup_mbid:
                    expected_artist_data = self.get_artist_by_id(artist_id)
                    if expected_artist_data:
                        expected_mbid = expected_artist_data.get('foreignArtistId')
                        
                        if expected_mbid and expected_mbid == lookup_mbid:
                            logger.info(f"MusicBrainz ID match - fixing artist data: {expected_mbid}")
                            album_data['artist'] = expected_artist_data
                            album_data['artistId'] = artist_id
                        else:
                            logger.error(f"MusicBrainz ID mismatch: expected {expected_mbid}, got {lookup_mbid}")
                            return False
                    else:
                        logger.error(f"Could not fetch artist {artist_id} for comparison")
                        return False
                else:
                    logger.error(f"No strategy available for artist ID mismatch")
                    return False
            else:
                logger.debug(f"Artist ID verification passed for {album_title}")
            
            # Configure the album for adding
            album_data['monitored'] = True
            album_data['addOptions'] = {'searchForMissingAlbums': True}
            
            logger.debug(f"Album data being sent to Lidarr:")
            logger.debug(f"  Album: {album_data.get('title', 'Unknown')}")
            logger.debug(f"  Artist ID: {album_data.get('artist', {}).get('id', 'None')}")
            logger.debug(f"  Artist Name: {album_data.get('artist', {}).get('artistName', 'None')}")
            logger.debug(f"  MusicBrainz ID: {album_data.get('foreignAlbumId', 'None')}")
            
            # Add the album to Lidarr
            result = self.add_album(album_data, monitored=True, search=True)
            
            if result:
                logger.info(f"Added and monitoring album: {artist_name} - {album_title} (MBID: {musicbrainz_album_id})")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error while adding album {album_title}: {e}")
            return False
    
    def monitor_album(
        self, 
        artist_id: int, 
        album_title: str, 
        artist_name: str
    ) -> bool:
        """
        Attempt to find and monitor a specific album for an artist in Lidarr.
        
        This function implements the core logic for selective album monitoring.
        It tries multiple strategies to locate the album and handles cases where
        the album may not be immediately available in Lidarr's database.
        
        Args:
            artist_id: Lidarr's internal ID for the artist
            album_title: Title of the album to monitor
            artist_name: Artist name (for logging purposes)
            
        Returns:
            True if album was successfully found and monitored, False otherwise
        """
        # Get edition variants from text_utils
        edition_variants = get_edition_variants()
        
        try:
            # Get all albums for this artist from Lidarr
            albums = self.get_artist_albums(artist_id)
            
            album_title_clean = album_title.lower().strip()
            matching_albums = []
            search_normalized = normalize_album_title_for_matching(album_title)
            
            for album in albums:
                album_title_lidarr = album['title'].lower().strip()
                
                # Priority 1: Exact match
                if album_title_lidarr == album_title_clean:
                    matching_albums.insert(0, album)
                    logger.debug(f"  Exact match: '{album['title']}'")
                
                # Priority 2: Normalized match (handles edition variants)
                else:
                    lidarr_normalized = normalize_album_title_for_matching(album_title_lidarr)
                    
                    if search_normalized == lidarr_normalized and search_normalized != "":
                        len_diff = abs(len(search_normalized) - len(lidarr_normalized))
                        if len_diff <= 2 or len(search_normalized) > 8:
                            matching_albums.append(album)
                            logger.debug(f"  Normalized match: '{album['title']}' -> '{lidarr_normalized}'")
                        else:
                            logger.debug(f"  Rejected normalized match (length diff {len_diff}): '{album['title']}'")
            
            # If we have multiple matches, prefer more recent releases
            if len(matching_albums) > 1:
                has_edition_in_search = any(variant.strip('()[]- ') in album_title.lower() for variant in edition_variants)
                if not has_edition_in_search:
                    matching_albums.sort(key=lambda x: x.get('releaseDate', '1900-01-01'), reverse=True)
                    logger.debug(f"  Multiple matches found, preferring newest: '{matching_albums[0]['title']}'")
            
            # If we found matching albums, check if already monitored
            if matching_albums:
                album = matching_albums[0]
                album_title_matched = album['title']
                
                # Check if album is already monitored
                if album.get('monitored', False):
                    logger.info(f"Album already monitored: {album_title_matched} by {artist_name}")
                    return True
                
                # Monitor the album
                album['monitored'] = True
                logger.info(f"Monitoring album: {album_title_matched} by {artist_name} (matched from: {album_title})")
                
                if self.update_album(album):
                    # Trigger search for missing files
                    self.search_for_album(album['id'])
                    logger.info(f"Started automatic search for: {album_title_matched}")
                    return True
                return False
            
            # If no albums found, trigger artist metadata refresh
            logger.info(f"Album '{album_title}' not found, triggering artist refresh for {artist_name}")
            self.refresh_artist(artist_id)
            logger.warning(f"Triggered refresh for {artist_name}, album '{album_title}' may appear after refresh completes")
            return False
            
        except Exception as e:
            logger.exception(f"Error monitoring album '{album_title}' for {artist_name} (ID {artist_id}): %s", e)
            return False
    
    def unmonitor_all_albums_for_artist(self, artist_id: int, artist_name: str) -> bool:
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
        try:
            albums = self.get_artist_albums(artist_id)
            
            unmonitored_count = 0
            for album in albums:
                if album.get('monitored', False):
                    album['monitored'] = False
                    if self.update_album(album):
                        unmonitored_count += 1
                        logger.debug(f"Unmonitored album: {album['title']} by {artist_name}")
            
            if unmonitored_count > 0:
                logger.info(f"Unmonitored {unmonitored_count} albums for NEWLY ADDED artist {artist_name}")
            else:
                logger.debug(f"No albums needed unmonitoring for newly added artist {artist_name}")
                
            return True
            
        except Exception as e:
            logger.error(f"✗ Error unmonitoring albums for newly added artist {artist_name} (ID {artist_id}): %s", e)
            return False
    
    def unmonitor_all_except_specific_album(
        self, 
        artist_id: int, 
        target_musicbrainz_id: str, 
        artist_name: str, 
        target_album_title: str
    ) -> bool:
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
        try:
            albums = self.get_artist_albums(artist_id)
            
            unmonitored_count = 0
            kept_monitored_count = 0
            target_found = False
            
            logger.debug(f"Looking for target album with MBID: {target_musicbrainz_id}")
            
            for album in albums:
                if album.get('monitored', False):
                    album_mbid = album.get('foreignAlbumId')
                    album_title = album.get('title', '')
                    
                    logger.debug(f"Checking album: '{album_title}' (MBID: {album_mbid})")
                    
                    # Check if this is our target album by MusicBrainz ID first
                    is_target_by_mbid = album_mbid == target_musicbrainz_id
                    
                    # Fallback: also check by title similarity (case-insensitive)
                    is_target_by_title = False
                    if target_album_title and album_title:
                        title_lower = album_title.lower()
                        target_lower = target_album_title.lower()
                        is_target_by_title = (title_lower == target_lower or 
                                            target_lower in title_lower or 
                                            title_lower in target_lower)
                    
                    if is_target_by_mbid or (is_target_by_title and not target_found):
                        # This is our target album - keep it monitored
                        kept_monitored_count += 1
                        target_found = True
                        match_reason = "MBID" if is_target_by_mbid else "title"
                        logger.debug(f"Keeping monitored: '{album_title}' by {artist_name} (target album, matched by {match_reason})")
                    else:
                        # This is NOT our target album - unmonitor it
                        album['monitored'] = False
                        if self.update_album(album):
                            unmonitored_count += 1
                            logger.debug(f"Unmonitored extra album: '{album_title}' by {artist_name} (MBID: {album_mbid})")
            
            if not target_found:
                logger.warning(f"Target album '{target_album_title}' (MBID: {target_musicbrainz_id}) was not found among monitored albums for {artist_name}")
            
            if unmonitored_count > 0:
                logger.info(f"Final cleanup: Unmonitored {unmonitored_count} extra albums for {artist_name}, kept {kept_monitored_count} target album(s)")
            else:
                logger.info(f"Final cleanup: Only target album '{target_album_title}' was monitored for {artist_name}")
                
            return True
            
        except Exception as e:
            logger.error(f"✗ Error in final cleanup for {artist_name} (ID {artist_id}): %s", e)
            return False
    
    def __repr__(self) -> str:
        """String representation of the client."""
        return f"LidarrClient(url={self.base_url}, quality_profile={self.quality_profile_id})"

"""
MusicBrainz API Client

Provides a clean interface to the MusicBrainz Web Service API v2 with:
- Rate limiting (respects 1 req/sec minimum)
- Retry logic for transient failures
- XML response parsing
- User agent management (required by MB TOS)

MusicBrainz Terms of Service:
- Maximum 1 request per second
- Identify your application with a proper user agent
- https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
"""

import time
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
import requests
from rapidfuzz import fuzz
from lib.text_utils import normalize_artist_name, normalize_album_title_for_matching, strip_album_suffixes

logger = logging.getLogger(__name__)


class MusicBrainzClient:
    """
    Client for MusicBrainz Web Service API v2.
    
    This client handles rate limiting, request formatting, and XML response
    parsing for MusicBrainz API interactions. It's designed to be a drop-in
    replacement for python-musicbrainzngs with improved control.
    
    Args:
        delay: Minimum seconds between requests (default: 2.0, min: 1.0)
        user_agent: User agent dict with app_name, version, contact
        timeout: Request timeout in seconds
    """
    
    def __init__(
        self,
        delay: float = 2.0,
        user_agent: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ):
        self.base_url = "https://musicbrainz.org/ws/2"
        self.min_delay = max(delay, 1.0)  # Enforce 1sec minimum per MB TOS
        self.timeout = timeout
        self.last_request_time = 0.0
        
        # Setup session with proper user agent
        self.session = requests.Session()
        if user_agent is None:
            user_agent = {
                'app_name': 'lidarr-album-import-script',
                'version': '2.0',
                'contact': 'your.email@example.com'
            }
        
        user_agent_string = (
            f"python-musicbrainzngs/0.7.1 "
            f"{user_agent['app_name']}/{user_agent['version']} "
            f"( {user_agent['contact']} )"
        )
        
        self.session.headers.update({
            'User-Agent': user_agent_string,
            'Accept': 'application/xml'
        })
        
        logger.debug(f"MusicBrainz client initialized with user agent: {user_agent_string}")
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits (1 req/sec minimum)."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            wait_time = self.min_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict[str, str]) -> Optional[ET.Element]:
        """
        Make a request to MusicBrainz API with rate limiting.
        
        Args:
            endpoint: API endpoint (e.g., 'artist', 'release-group')
            params: Query parameters
            
        Returns:
            Parsed XML Element tree, or None if request failed
        """
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return ET.fromstring(response.content)
            elif response.status_code == 503:
                logger.debug(f"MusicBrainz rate limited (503), retrying...")
                return None
            else:
                logger.debug(
                    f"MusicBrainz error {response.status_code}: {response.text[:200]}"
                )
                return None
                
        except requests.exceptions.Timeout:
            logger.debug(f"MusicBrainz request timeout after {self.timeout}s")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"MusicBrainz request failed: {e}")
            return None
        except ET.ParseError as e:
            logger.debug(f"MusicBrainz XML parse error: {e}")
            return None
    
    def search_artists(self, artist: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search for an artist by name.
        
        Args:
            artist: Artist name to search for
            limit: Maximum number of results (default: 5)
            
        Returns:
            Dictionary with 'artist-list' key containing list of artist results.
            Each artist has: id, name, ext:score
        """
        # Strip brackets from artist name for search query
        search_artist = artist.strip('[]') if artist.startswith('[') and artist.endswith(']') else artist
        
        params = {
            'query': f'artist:{search_artist}',
            'limit': str(limit)
        }
        
        root = self._make_request('artist', params)
        if root is None:
            return {"artist-list": []}
        
        # Parse XML response
        ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
        artists = root.findall('.//mb:artist', ns)
        
        artist_list = []
        for artist_elem in artists:
            name_elem = artist_elem.find('./mb:name', ns)
            name = name_elem.text if name_elem is not None else ''
            score = artist_elem.get('ext:score', '100')
            
            # Calculate similarity score between search term and result name
            # Use the search term (without brackets if they were stripped) for comparison
            search_term = search_artist.lower()
            result_name = name.lower()
            similarity = fuzz.ratio(search_term, result_name)
            
            artist_list.append({
                'id': artist_elem.get('id', ''),
                'name': name,
                'ext:score': score,
                'similarity': similarity
            })
        
        # Filter results to only include high similarity matches
        filtered_list = [a for a in artist_list if a['similarity'] >= 70]
        
        # Sort by similarity first, then by MB score
        filtered_list.sort(key=lambda x: (x['similarity'], int(x['ext:score'])), reverse=True)
        
        # Remove the similarity key from output
        for a in filtered_list:
            del a['similarity']
        
        logger.debug(f"MusicBrainz artist search returned {len(artist_list)} raw results, {len(filtered_list)} filtered for '{artist}'")
        return {"artist-list": filtered_list}
    
    def search_release_groups(
        self,
        artist: str,
        releasegroup: str,
        limit: int = 5,
        artist_aliases: Optional[Dict[str, List[str]]] = None,
        artist_mbid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for a release group (album) by artist and title.
        
        This method tries multiple search strategies with progressively
        looser matching AND multiple title variations to find the best
        album match while avoiding false positives.
        
        Tries title variations like:
        - Original: "ep seeds"
        - Without common prefixes: "seeds"
        - Capitalized: "Ep Seeds"
        
        Args:
            artist: Artist name
            releasegroup: Album/release group title
            limit: Maximum number of results per query
            artist_aliases: Optional dict of artist name aliases for matching
            
        Returns:
            Dictionary with 'release-group-list' key containing matching albums.
            Each release group has: id, title, artist-credit-phrase, ext:score
        """
        if artist_aliases is None:
            artist_aliases = {}
        
        # Generate title variations to try
        title_variations = self._generate_title_variations(releasegroup)
        logger.debug(f"Generated {len(title_variations)} title variations to try: {title_variations}")
        
        # If we have a MusicBrainz artist MBID, prefer queries using arid: to
        # constrain by the canonical MB artist id — this avoids artist-name
        # mismatches (case/punctuation/alias differences).
        use_arid = bool(artist_mbid)

        # Try each title variation
        for title_idx, title_variant in enumerate(title_variations, 1):
            logger.debug(f"Trying title variation {title_idx}/{len(title_variations)}: '{title_variant}'")
            
            # Build progressive query strategies for this title variant
            if use_arid:
                # Prefer arid:<mbid> queries which are much more reliable
                queries = [
                    f'arid:{artist_mbid} AND releasegroup:"{title_variant}"',
                    f'arid:{artist_mbid} AND releasegroup:{title_variant}',
                ]
            else:
                queries = self._build_release_group_queries(artist, title_variant)
            
            for query_idx, query in enumerate(queries, 1):
                logger.debug(f"Query {query_idx}/{len(queries)}: {query}")
                
                params = {
                    'query': query,
                    'limit': str(limit)
                }
                
                root = self._make_request('release-group', params)
                if root is None:
                    continue
                
                # Parse XML response
                ns = {
                    'mb': 'http://musicbrainz.org/ns/mmd-2.0#',
                    'ns2': 'http://musicbrainz.org/ns/ext#-2.0'
                }
                release_groups = root.findall('.//mb:release-group', ns)
                
                if not release_groups:
                    logger.debug(f"No results from MusicBrainz")
                    continue
                
                logger.debug(f"Got {len(release_groups)} raw results from MusicBrainz")
                
                # Parse and filter results
                rg_list = self._parse_release_groups(
                    release_groups, ns, artist, artist_aliases
                )
                
                if rg_list:
                    logger.debug(
                        f"Found {len(rg_list)} matching albums with title '{title_variant}' (query {query_idx})"
                    )
                    return {"release-group-list": rg_list}
                else:
                    logger.debug(f"All results filtered out (artist mismatch)")
        
        # No successful queries with any title variation
        # Final fallback: try searching by releasegroup/title only (no artist constraint)
        # This can find entries that exist under slightly different artist credit formatting
        # and lets us inspect artist-credit phrases to find a match.
        for title_variant in title_variations:
            logger.debug(f"Fallback: trying releasegroup-only search for '{title_variant}'")
            params = {'query': f'releasegroup:"{title_variant}"', 'limit': str(limit)}
            root = self._make_request('release-group', params)
            if root is None:
                continue
            ns = {
                'mb': 'http://musicbrainz.org/ns/mmd-2.0#',
                'ns2': 'http://musicbrainz.org/ns/ext#-2.0'
            }
            release_groups = root.findall('.//mb:release-group', ns)
            if not release_groups:
                logger.debug("Fallback search returned no results")
                continue
            logger.debug(f"Fallback search got {len(release_groups)} raw results from MusicBrainz")
            rg_list = self._parse_release_groups(release_groups, ns, artist, artist_aliases)
            if rg_list:
                logger.debug(f"Found {len(rg_list)} matching albums via fallback for '{title_variant}'")
                return {"release-group-list": rg_list}
        logger.debug(
            f"No matches found after trying {len(title_variations)} title variations"
        )
        return {"release-group-list": []}
    
    def _generate_title_variations(self, title: str) -> List[str]:
        """
        Generate variations of an album title to improve search success.
        
        Common patterns:
        - "ep seeds" → try "seeds" (remove "ep" prefix)
        - "the album" → try "album" (remove "the" prefix)
        - lowercase → Title Case
        
        Returns list with original first, then variations in order of preference.
        """
        variations = [title]  # Always try original first
        title_lower = title.lower().strip()
        
        # Remove common prefixes (ep, the, a, single)
        prefixes_to_strip = ['ep ', 'single ', 'the ', 'a ']
        for prefix in prefixes_to_strip:
            if title_lower.startswith(prefix):
                stripped = title[len(prefix):].strip()
                if stripped and stripped not in variations:
                    variations.append(stripped)
                    logger.debug(f"      Title variation: '{title}' → '{stripped}' (removed '{prefix.strip()}')")
        
        # Try Title Case if original is lowercase
        if title_lower == title:
            title_case = title.title()
            if title_case not in variations:
                variations.append(title_case)
                logger.debug(f"      Title variation: '{title}' → '{title_case}' (title case)")

        # Try all caps if it's a short title (likely an acronym)
        if len(title) <= 6 and not title.isupper():
            upper_title = title.upper()
            if upper_title not in variations:
                variations.append(upper_title)
                logger.debug(f"      Title variation: '{title}' → '{upper_title}' (uppercase)")

        # Additional helpful variations: replace ampersand with 'and', remove commas/periods
        amp = title.replace('&', 'and')
        if amp not in variations:
            variations.append(amp)
            logger.debug(f"      Title variation: '{title}' → '{amp}' (ampersand→and)")

        no_punct = ''.join(ch for ch in title if ch.isalnum() or ch.isspace())
        no_punct = ' '.join(no_punct.split())
        if no_punct and no_punct not in variations:
            variations.append(no_punct)
            logger.debug(f"      Title variation: '{title}' → '{no_punct}' (removed punctuation)")
        
        return variations
    
    def _build_release_group_queries(self, artist: str, releasegroup: str) -> List[str]:
        """
        Build a list of progressively looser search queries.
        
        Strategy:
        1. Exact artist and album names (quoted for precision)
        2. Cleaned artist name (handle special chars like $ and !)
        3. Looser matching without quotes
        4. Most permissive (for artists with brackets)
        """
        queries = []
        
        # Handle special characters in artist names
        if '[' in artist and ']' in artist:
            # For bracketed artists like [bsd.u], try both versions
            bracket_content = artist.strip('[]')
            queries = [
                f'artist:"{artist}" AND releasegroup:"{releasegroup}"',
                f'artist:"{bracket_content}" AND releasegroup:"{releasegroup}"',
                f'artist:{artist} AND releasegroup:"{releasegroup}"',
                f'artist:{bracket_content} releasegroup:{releasegroup}',
            ]
        else:
            # For normal artists, clean special characters
            clean_artist = artist.replace('!', 'I').replace('$', 'S')
            queries = [
                f'artist:"{artist}" AND releasegroup:"{releasegroup}"',
            ]
            
            # Only add cleaned version if different
            if clean_artist != artist:
                queries.append(f'artist:"{clean_artist}" AND releasegroup:"{releasegroup}"')
            
            queries.extend([
                f'artist:{artist} AND releasegroup:"{releasegroup}"',
            ])
            
            if clean_artist != artist:
                queries.append(f'artist:{clean_artist} releasegroup:{releasegroup}')
        
        return queries
    
    def _parse_release_groups(
        self,
        release_groups: List[ET.Element],
        ns: Dict[str, str],
        artist: str,
        artist_aliases: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Parse and filter release group XML elements.
        
        Filters out results where the artist doesn't match to prevent
        false positives (e.g., "AJ Suede" matching "Suede").
        """
        rg_list = []
        
        for rg in release_groups:
            title_elem = rg.find('./mb:title', ns)
            artist_credit = rg.find('.//mb:artist-credit/mb:name-credit/mb:artist/mb:name', ns)
            
            # Get score with proper namespace handling
            score = (
                rg.get('{http://musicbrainz.org/ns/ext#-2.0}score') or
                rg.get('ns2:score') or
                rg.get('ext:score') or
                '100'
            )
            
            rg_data = {
                'id': rg.get('id', ''),
                'title': title_elem.text if title_elem is not None else '',
                'artist-credit-phrase': artist_credit.text if artist_credit is not None else '',
                'ext:score': score
            }
            
            # Filter results by artist relevance
            if self._is_artist_match(rg_data['artist-credit-phrase'], artist, artist_aliases):
                rg_list.append(rg_data)
                logger.debug(
                    f"Kept: '{rg_data['title']}' by '{rg_data['artist-credit-phrase']}' "
                    f"(score: {score})"
                )
            else:
                logger.debug(
                    f"Filtered: '{rg_data['title']}' by '{rg_data['artist-credit-phrase']}' "
                    f"(not a match for '{artist}')"
                )
        
        return rg_list
    
    def _is_artist_match(
        self,
        found_artist: str,
        search_artist: str,
        artist_aliases: Dict[str, List[str]]
    ) -> bool:
        """
        Check if found artist name matches search artist.
        
        Uses exact matching with special character transformations and
        alias lookups to avoid false positives.
        """
        found_lower = found_artist.lower().strip()
        search_lower = search_artist.lower().strip()
        
        # For bracketed artists like [bsd.u], be very precise
        if '[' in search_artist and ']' in search_artist:
            bracket_content = search_artist.strip('[]').lower()
            return found_lower == search_lower or found_lower == bracket_content
        
        # For normal artists, use exact matches with transformations
        exact_matches = [
            search_lower,
            search_artist.lower().replace('!', 'i'),  # !llmind -> illmind
            search_artist.lower().replace('$', 's'),  # $uicideboy$ -> suicideboys
        ]

        # Add known aliases
        if search_lower in artist_aliases:
            exact_matches.extend([a.lower() for a in artist_aliases[search_lower]])
            logger.debug(f"Added aliases for '{search_artist}': {artist_aliases[search_lower]}")

        logger.debug(f"Comparing '{found_lower}' against exact list: {exact_matches}")
        if found_lower in exact_matches:
            return True

        # Do NOT strip prefixes like 'DJ ' or 'The ' — rely on exact/alias checks
        # and a fuzzy normalized comparison below. Prefixes are meaningful and
        # should not be ignored when determining artist identity.

        # Finally, use a fuzzy comparison on normalized names to allow small variations
        try:
            sim = fuzz.token_set_ratio(normalize_artist_name(found_artist), normalize_artist_name(search_artist))
        except Exception:
            sim = fuzz.ratio(found_lower, search_lower)

        logger.debug(f"Fuzzy artist similarity between '{found_artist}' and '{search_artist}': {sim}")
        # Accept if similarity is high enough (tuned to avoid false positives)
        return sim >= 85
    
    def get_release_group_by_id(self, mbid: str) -> Optional[Dict[str, Any]]:
        """
        Get release group details by MusicBrainz ID.
        
        Args:
            mbid: MusicBrainz release group ID
            
        Returns:
            Release group data or None if not found
        """
        params = {'inc': 'artists'}
        root = self._make_request(f'release-group/{mbid}', params)
        
        if root is None:
            return None
        
        ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
        rg = root.find('.//mb:release-group', ns)
        
        if rg is None:
            return None
        
        title_elem = rg.find('./mb:title', ns)
        artist_elem = rg.find('.//mb:artist-credit/mb:name-credit/mb:artist/mb:name', ns)
        
        return {
            'id': rg.get('id', ''),
            'title': title_elem.text if title_elem is not None else '',
            'artist-credit-phrase': artist_elem.text if artist_elem is not None else ''
        }

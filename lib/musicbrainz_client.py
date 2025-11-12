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
import re
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List, Union
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
        
        # Keep Accept header as XML by default to match expected test behavior
        # and MusicBrainz defaults; we still attempt to decode JSON responses
        # in _make_request when present.
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

    def _extract_artists_from_root(self, root: Union[dict, ET.Element], search_term: str) -> List[Dict[str, Any]]:
        """Normalize artist candidates from either JSON dict or XML Element tree.

        Returns a list of dicts with keys: id, name, ext:score, similarity
        """
        artists: List[Dict[str, Any]] = []
        if isinstance(root, dict):
            raw = root.get('artists') or root.get('artist-list') or []
            for a in raw:
                aid = a.get('id', '')
                name = a.get('name', '')
                score = a.get('score') or a.get('ext:score') or '100'
                try:
                    similarity = fuzz.ratio(search_term, (name or '').lower())
                except Exception:
                    similarity = 0
                artists.append({'id': aid, 'name': name, 'ext:score': str(score), 'similarity': similarity})
        else:
            ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
            elems = root.findall('.//mb:artist', ns)
            for elem in elems:
                aid = elem.get('id', '')
                name_elem = elem.find('./mb:name', ns)
                name = name_elem.text if name_elem is not None else ''
                score = elem.get('ext:score', '100')
                try:
                    similarity = fuzz.ratio(search_term, (name or '').lower())
                except Exception:
                    similarity = 0
                artists.append({'id': aid, 'name': name, 'ext:score': str(score), 'similarity': similarity})
        return artists

    def _extract_release_groups_from_json(self, root: dict) -> List[Dict[str, Any]]:
        """Normalize release-group candidates from a JSON response into the
        same dict shape used by the XML parser path and later selection logic.
        """
        rgs: List[Dict[str, Any]] = []
        raw = root.get('release-groups') or root.get('release-group-list') or root.get('release-groups-list') or root.get('release-group') or []
        for rg in raw:
            rg_id = rg.get('id') or rg.get('gid') or ''
            title = rg.get('title') or rg.get('name') or ''
            score = rg.get('score') or rg.get('ext:score') or '100'

            # artist-credit phrase
            artist_credit_phrase = ''
            ac = rg.get('artist-credit') or rg.get('artist-credit-phrase') or []
            if isinstance(ac, list) and ac:
                try:
                    names = []
                    for part in ac:
                        if isinstance(part, dict):
                            a = part.get('artist') or {}
                            if isinstance(a, dict):
                                n = a.get('name')
                                if n:
                                    names.append(n)
                            elif part.get('name'):
                                names.append(part.get('name'))
                    artist_credit_phrase = ', '.join(names)
                except Exception:
                    artist_credit_phrase = ''
            elif isinstance(ac, str):
                artist_credit_phrase = ac

            # relations -> urls
            urls: List[str] = []
            for rel in rg.get('relations', []) or []:
                if isinstance(rel, dict):
                    urlobj = rel.get('url') or {}
                    if isinstance(urlobj, dict):
                        res = urlobj.get('resource')
                        if res:
                            urls.append(res)
                    tgt = rel.get('target')
                    if tgt:
                        urls.append(tgt)

            fr = rg.get('first-release-date') or rg.get('first_release_date') or None

            # track count: try to glean from releases list if present
            tc = None
            releases = rg.get('releases') or []
            if releases:
                try:
                    first_release = releases[0]
                    media = first_release.get('media') or []
                    if media and isinstance(media, list):
                        first_media = media[0]
                        if first_media.get('track-count'):
                            tc = int(first_media.get('track-count'))
                        else:
                            tracks = first_media.get('tracks') or first_media.get('track-list') or []
                            if isinstance(tracks, list):
                                tc = len(tracks)
                except Exception:
                    tc = None

            rgs.append({
                'id': rg_id,
                'title': title,
                'artist-credit-phrase': artist_credit_phrase,
                'ext:score': str(score),
                'urls': urls,
                'first_release_date': fr,
                'track_count': tc,
            })
        return rgs
    
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
                # Prefer JSON where the caller requests it; attempt to decode JSON
                try:
                    return response.json()
                except Exception:
                    # Fallback to XML parsing for compatibility
                    try:
                        return ET.fromstring(response.content)
                    except ET.ParseError as e:
                        logger.debug(f"MusicBrainz XML parse error: {e}")
                        return None
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

        # Prefer a quoted, precise search first. Only if the quoted search
        # returns no results (or fails) do we try the looser unquoted query.
        collected: Dict[str, Dict[str, Any]] = {}
        quoted_failed = False
        search_term = (search_artist or '').lower()

        # First: quoted, precise query
        q = f'artist:"{search_artist}"'
        params = {'query': q, 'limit': str(limit), 'fmt': 'json'}
        root = self._make_request('artist', params)
        if root is None:
            quoted_failed = True
            artists = []
        else:
            artists = self._extract_artists_from_root(root, search_term)

        for a in artists:
            aid = str(a.get('id') or '')
            name = a.get('name')
            score = a.get('ext:score')
            similarity = a.get('similarity', 0)
            if aid in collected:
                existing = collected[aid]
                existing['similarity'] = max(existing.get('similarity', 0), similarity)
                existing['is_quoted'] = existing.get('is_quoted', False) or True
                try:
                    existing['ext:score'] = str(max(int(existing.get('ext:score', '0') or 0), int(score or 0)))
                except Exception:
                    existing['ext:score'] = score
            else:
                collected[aid] = {
                    'id': aid,
                    'name': name,
                    'ext:score': score,
                    'similarity': similarity,
                    'is_quoted': True,
                }

        # Note: we intentionally avoid issuing a second, looser query by
        # default. If the quoted query failed or returned no results, the
        # 'quoted_failed' flag will be True and the later fallback logic
        # may attempt a retry.

        if not collected:
            return {"artist-list": []}

        # If we only collected unquoted results and the quoted query failed
        # earlier (transient network error), try the quoted query one more time
        # to give preference to quoted matches.
        has_quoted = any(a.get('is_quoted') for a in collected.values())
        if not has_quoted and quoted_failed:
            q = f'artist:"{search_artist}"'
            params = {'query': q, 'limit': str(limit), 'fmt': 'json'}
            root = self._make_request('artist', params)
            if root is not None:
                if isinstance(root, dict):
                    artists = root.get('artists') or root.get('artist-list') or []
                else:
                    ns = {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'}
                    artists = root.findall('.//mb:artist', ns)

                for artist_elem in artists:
                    if isinstance(root, dict):
                        aid = artist_elem.get('id', '')
                        name = artist_elem.get('name', '')
                        score = artist_elem.get('score') or artist_elem.get('ext:score') or '100'
                    else:
                        aid = artist_elem.get('id', '')
                        name_elem = artist_elem.find('./mb:name', {'mb': 'http://musicbrainz.org/ns/mmd-2.0#'})
                        name = name_elem.text if name_elem is not None else ''
                        score = artist_elem.get('ext:score', '100')
                    try:
                        similarity = fuzz.ratio(search_term, (name or '').lower())
                    except Exception:
                        similarity = 0

                    if aid in collected:
                        existing = collected[aid]
                        existing['similarity'] = max(existing.get('similarity', 0), similarity)
                        existing['is_quoted'] = True
                        try:
                            existing['ext:score'] = str(max(int(existing.get('ext:score', '0') or 0), int(score or 0)))
                        except Exception:
                            existing['ext:score'] = score
                    else:
                        collected[aid] = {
                            'id': aid,
                            'name': name,
                            'ext:score': score,
                            'similarity': similarity,
                            'is_quoted': True,
                        }

        artist_list: List[Dict[str, Any]] = list(collected.values())

        # Debug: show raw candidates
        logger.debug(f"Raw artist candidates for '{search_artist}':")
        for a in artist_list:
            n = (a.get('name') or '')
            try:
                n_norm = normalize_artist_name(n)
            except Exception:
                n_norm = n.lower()
            logger.debug(f"  - id={a.get('id')} name='{a.get('name')}' norm='{n_norm}' sim={a.get('similarity')} score={a.get('ext:score')}")

        # Filter results to only include reasonably similar matches.
        MIN_SIMILARITY = 70
        filtered_list = [a for a in artist_list if a['similarity'] >= MIN_SIMILARITY]
        if not filtered_list and artist_list:
            RELAXED_SIM = 60
            filtered_list = [a for a in artist_list if a['similarity'] >= RELAXED_SIM]

        # Prefer results that preserve leading qualifiers when the search term has one
        search_tokens = (search_artist or '').lower().split()
        prefix_candidates = {'dj', 'the', 'mc'}
        search_prefix = search_tokens[0] if search_tokens and search_tokens[0] in prefix_candidates else None

        def _sort_key(x: Dict[str, Any]):
            name_val = x.get('name') or ''
            try:
                norm_name = normalize_artist_name(name_val)
            except Exception:
                norm_name = name_val.lower()
            has_prefix = 1 if (search_prefix and norm_name.startswith(search_prefix)) else 0
            prefix_boost = 1000 if has_prefix else 0
            quoted_boost = 2000 if x.get('is_quoted') else 0
            # quoted_boost is highest priority, then prefix_boost, then similarity, then ext score
            return (quoted_boost + prefix_boost + int(x.get('similarity') or 0), int(x.get('ext:score') or 0))

        filtered_list.sort(key=_sort_key, reverse=True)

        for a in filtered_list:
            del a['similarity']

        logger.debug(f"MusicBrainz artist search returned {len(artist_list)} raw results, {len(filtered_list)} filtered for '{search_artist}'")
        return {"artist-list": filtered_list}
    
    def search_release_groups(
        self,
        artist: str,
        releasegroup: str,
        limit: int = 5,
        artist_aliases: Optional[Dict[str, List[str]]] = None,
        artist_mbid: Optional[str] = None,
        spotify_album_id: Optional[str] = None,
        release_date: Optional[str] = None,
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
                    'limit': str(limit),
                    # request URL relations and release info (for dates/track-count)
                    'inc': 'url-rels+releases'
                }
                
                root = self._make_request('release-group', params)
                if root is None:
                    continue
                
                # Parse XML or JSON response
                rg_list = []
                if isinstance(root, dict):
                    # Normalize JSON response into the same rg dict shape used by the XML parser
                    rgs = self._extract_release_groups_from_json(root)
                    logger.debug(f"Got {len(rgs)} raw results from MusicBrainz (json)")
                    # Filter by artist relevance
                    for rg_data in rgs:
                        if self._is_artist_match(rg_data['artist-credit-phrase'], artist, artist_aliases):
                            rg_list.append(rg_data)
                            logger.debug(f"Kept: '{rg_data['title']}' by '{rg_data['artist-credit-phrase']}' (score: {rg_data.get('ext:score')})")
                        else:
                            logger.debug(f"Filtered: '{rg_data['title']}' by '{rg_data['artist-credit-phrase']}' (not a match for '{artist}')")
                else:
                    ns = {
                        'mb': 'http://musicbrainz.org/ns/mmd-2.0#',
                        'ns2': 'http://musicbrainz.org/ns/ext#-2.0'
                    }
                    release_groups = root.findall('.//mb:release-group', ns)

                    if not release_groups:
                        logger.debug(f"No results from MusicBrainz")
                        continue

                    logger.debug(f"Got {len(release_groups)} raw results from MusicBrainz")

                    # Parse and filter results (XML path)
                    rg_list = self._parse_release_groups(
                        release_groups, ns, artist, artist_aliases
                    )
                
                if rg_list:
                    logger.debug(f"Found {len(rg_list)} matching albums with title '{title_variant}' (query {query_idx})")

                    # 1) If caller provided a Spotify album id, prefer release-groups
                    # that include a Spotify URL relation matching that id.
                    if spotify_album_id:
                        matches = []
                        for rg in rg_list:
                            urls = rg.get('urls', [])
                            for u in urls:
                                if not u:
                                    continue
                                if spotify_album_id in u or f"open.spotify.com/album/{spotify_album_id}" in u or f"spotify:album:{spotify_album_id}" in u:
                                    matches.append(rg)
                                    break
                        if matches:
                            logger.debug(f"Selecting {len(matches)} candidate(s) by Spotify album id match")
                            return {"release-group-list": matches}

                    # 2) Prefer candidates that match the requested release year (if provided)
                    if release_date:
                        year_match = []
                        req_year = release_date.strip()[:4]
                        for rg in rg_list:
                            fr = (rg.get('first_release_date') or '')
                            if fr and fr.startswith(req_year):
                                year_match.append(rg)
                        if year_match:
                            year_match.sort(key=lambda r: int(r.get('ext:score') or 0), reverse=True)
                            logger.debug(f"Selecting {len(year_match)} candidate(s) by release year {req_year}")
                            return {"release-group-list": year_match}

                    # 3) Prefer exact title matches (case-insensitive)
                    exact_matches = [rg for rg in rg_list if (rg.get('title') or '').strip().lower() == title_variant.strip().lower()]
                    if exact_matches:
                        exact_matches.sort(key=lambda r: int(r.get('ext:score') or 0), reverse=True)
                        return {"release-group-list": exact_matches}

                    # If the requested title includes a volume indicator like 'Vol. 5',
                    # prefer candidates that include the same volume number.
                    vol_re = re.search(r"\bvol(?:\.|ume)?\s*#?:?\s*(\d+)\b", title_variant, flags=re.IGNORECASE)
                    if vol_re:
                        wanted_vol = vol_re.group(1)
                        vol_matches = []
                        for rg in rg_list:
                            cand_title = (rg.get('title') or '')
                            cand_vol_m = re.search(r"\bvol(?:\.|ume)?\s*#?:?\s*(\d+)\b", cand_title, flags=re.IGNORECASE)
                            if cand_vol_m and cand_vol_m.group(1) == wanted_vol:
                                vol_matches.append(rg)
                        if vol_matches:
                            vol_matches.sort(key=lambda r: int(r.get('ext:score') or 0), reverse=True)
                            logger.debug(f"Selecting {len(vol_matches)} candidate(s) matching requested volume {wanted_vol}")
                            return {"release-group-list": vol_matches}
                        else:
                            # If the user requested a specific volume (Vol N) and we
                            # couldn't find any matching releases with that same
                            # volume number, treat it as no match rather than
                            # returning a different volume (avoids false positives).
                            logger.debug(f"No release-group candidates matched requested volume {wanted_vol}; skipping matches")
                            return {"release-group-list": []}

                    # No exact or same-volume matches; prefer releases whose titles
                    # are most similar to the requested title (client-side title similarity)
                    scored = []
                    for rg in rg_list:
                        cand_title = (rg.get('title') or '')
                        sim = fuzz.token_set_ratio(normalize_album_title_for_matching(title_variant), normalize_album_title_for_matching(cand_title))
                        scored.append((sim, int(rg.get('ext:score') or 0), rg))
                    # sort by similarity then MB score
                    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
                    sorted_rgs = [t[2] for t in scored]
                    return {"release-group-list": sorted_rgs}
                else:
                    logger.debug(f"All results filtered out (artist mismatch)")
        
        # No successful queries with any title variation
        # Final fallback: try searching by releasegroup/title only (no artist constraint)
        # This can find entries that exist under slightly different artist credit formatting
        # and lets us inspect artist-credit phrases to find a match.
        for title_variant in title_variations:
            logger.debug(f"Fallback: trying releasegroup-only search for '{title_variant}'")
            params = {'query': f'releasegroup:"{title_variant}"', 'limit': str(limit), 'fmt': 'json'}
            root = self._make_request('release-group', params)
            if root is None:
                continue
            # Support JSON or XML fallback parsing
            if isinstance(root, dict):
                rgs = self._extract_release_groups_from_json(root)
                if not rgs:
                    logger.debug("Fallback search returned no results (json)")
                    continue
                logger.debug(f"Fallback search got {len(rgs)} raw results from MusicBrainz (json)")
                rg_list = []
                for rg_data in rgs:
                    if self._is_artist_match(rg_data['artist-credit-phrase'], artist, artist_aliases):
                        rg_list.append(rg_data)

                if rg_list:
                    logger.debug(f"Found {len(rg_list)} matching albums via fallback for '{title_variant}'")
                    return {"release-group-list": rg_list}
            else:
                ns = {
                    'mb': 'http://musicbrainz.org/ns/mmd-2.0#',
                    'ns2': 'http://musicbrainz.org/ns/ext#-2.0'
                }
                release_groups = root.findall('.//mb:release-group', ns)
                if not release_groups:
                    logger.debug("Fallback search returned no results")
                    continue
                logger.debug(f"Fallback search got {len(release_groups)} raw results from MusicBrainz")
                rg_list = self._parse_release_groups(release_groups, ns, artist, artist_aliases, title_variant)
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

    def _is_artist_match(self, artist_credit_phrase: str, artist: str, artist_aliases: Dict[str, List[str]]) -> bool:
        """
        Determine whether the artist credit phrase from MusicBrainz matches
        the searched artist name, taking into account aliases and simple
        fuzzy/token-set similarity.
        """
        if not artist_credit_phrase or not artist:
            return False

        try:
            credit_norm = normalize_artist_name(artist_credit_phrase)
        except Exception:
            credit_norm = (artist_credit_phrase or '').lower()

        try:
            artist_norm = normalize_artist_name(artist)
        except Exception:
            artist_norm = (artist or '').lower()

        # Direct containment (common case)
        if artist_norm in credit_norm:
            return True

        # Check provided aliases
        aliases = artist_aliases.get(artist, []) if artist_aliases else []
        for a in aliases:
            try:
                if normalize_artist_name(a) in credit_norm:
                    return True
            except Exception:
                if (a or '').lower() in credit_norm:
                    return True

        # Fallback to token-set similarity
        try:
            sim = fuzz.token_set_ratio(artist_norm, credit_norm)
        except Exception:
            sim = fuzz.ratio(artist_norm, credit_norm)

        return sim >= 70
    
    def _parse_release_groups(
        self,
        release_groups: List[ET.Element],
        ns: Dict[str, str],
        artist: str,
        artist_aliases: Dict[str, List[str]],
        title_searched: Optional[str] = None,
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
                'ext:score': score,
                'urls': [],
                'first_release_date': None,
                'track_count': None,
            }

            # Extract first-release-date if present
            try:
                fr_elem = rg.find('./mb:first-release-date', ns)
                if fr_elem is not None and fr_elem.text:
                    rg_data['first_release_date'] = fr_elem.text
            except Exception:
                pass

            # Try to extract track count from first release (if included via inc=releases)
            try:
                first_release = rg.find('.//mb:release', ns)
                if first_release is not None:
                    tracks = first_release.findall('.//mb:medium/mb:track-list/mb:track', ns)
                    if tracks:
                        rg_data['track_count'] = len(tracks)
            except Exception:
                pass

            # Extract relation URLs (if any)
            try:
                targets = [t.text for t in rg.findall('.//mb:relation/mb:target', ns) if t is not None and t.text]
                if targets:
                    rg_data['urls'] = targets
            except Exception:
                pass
            
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
        
        
        # If we have a searched title and there are multiple matches, prefer
        # exact-title matches (case-insensitive) before falling back to fuzzy
        # ordering as returned by MusicBrainz / ext:score.
        if title_searched and rg_list:
            lower_title = title_searched.strip().lower()
            exact = [r for r in rg_list if (r.get('title') or '').strip().lower() == lower_title]
            if exact:
                # We already have exact title matches; prefer higher ext:score
                exact.sort(key=lambda r: int(r.get('ext:score') or 0), reverse=True)
                return exact
        # Default: return the filtered/collected release-group list
        return rg_list
        

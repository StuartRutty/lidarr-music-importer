from dataclasses import dataclass
from typing import Optional


@dataclass
class AlbumEntry:
    artist: str
    album: str
    album_search: str = ""
    track_count: int = 1
    source_format: str = ""
    matching_risk: bool = False
    risk_reason: str = ""
    mb_artist_id: str = ""
    mb_release_id: str = ""
    # Spotify metadata (optional)
    spotify_album_id: str = ""
    spotify_artist_id: str = ""
    spotify_album_url: str = ""
    release_date: str = ""
    total_tracks: Optional[int] = None
    track_titles: str = ""  # semicolon-separated
    track_isrcs: str = ""  # semicolon-separated

    def __hash__(self):
        return hash((self.artist.lower(), self.album.lower()))

    def __eq__(self, other):
        if not isinstance(other, AlbumEntry):
            return NotImplemented
        return (self.artist.lower(), self.album.lower()) == (other.artist.lower(), other.album.lower())

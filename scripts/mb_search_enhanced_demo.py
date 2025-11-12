#!/usr/bin/env python3
"""
Interactive demo: MusicBrainz enhanced search

This demo was previously in `tests/` and was collected by pytest which
caused test runs to block on input() and required an API key at import time.

Move it to `scripts/` to keep it available while preventing test collection.
"""

import sys
import logging
from pathlib import Path

# Add lib directory to Python path
lib_path = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(lib_path))

from musicbrainz_client import MusicBrainzClient
from config_manager import Config

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

# Load config
config = Config()

# Initialize MusicBrainz client
mb_client = MusicBrainzClient(
    delay=config.musicbrainz_delay,
    user_agent=config.musicbrainz_user_agent,
    timeout=30
)

print("=" * 80)
print("MUSICBRAINZ ENHANCED SEARCH DEMONSTRATION")
print("=" * 80)
print()

# Test cases that previously failed
test_cases = [
    ("eevee", "ep seeds"),
    ("eevee", "ep unexpected"),
    ("eevee", "ep unknown"),
    ("Cookin Soul", "Polo Beats"),
    ("DJ Drobitussin", "Screwed and Chopped Keep Calling"),
]

for artist, album in test_cases:
    print("\n" + "=" * 80)
    print(f"TEST: {artist} - {album}")
    print("=" * 80)
    
    result = mb_client.search_release_groups(
        artist=artist,
        releasegroup=album,
        limit=5
    )
    
    albums_found = result.get("release-group-list", [])
    
    if albums_found:
        print(f"\n✅ SUCCESS: Found {len(albums_found)} matching album(s)")
        for i, album_data in enumerate(albums_found, 1):
            print(f"   {i}. '{album_data['title']}' by '{album_data['artist-credit-phrase']}'")
            print(f"      MBID: {album_data['id']}")
            print(f"      Score: {album_data.get('ext:score', 'N/A')}")
    else:
        print("\n❌ FAILED: No matches found")
    
    print()
    input("Press Enter to continue to next test...")

print("=" * 80)
print("TESTING COMPLETE")
print("=" * 80)

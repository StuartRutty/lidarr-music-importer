#!/usr/bin/env python3
"""
Test CSV input cleaning functionality.

Tests the clean_csv_input function to ensure artist names and album titles
are properly normalized before MusicBrainz/Lidarr API searches.
"""

import sys
from pathlib import Path

# Add lib directory to Python path
lib_path = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(lib_path))

from text_utils import clean_csv_input


def test_artist_cleaning():
    """Test cleaning artist names from CSV input."""
    
    print("="*60)
    print("ARTIST NAME CLEANING TESTS")
    print("="*60)
    
    test_cases = [
        # (input, expected_output, description)
        ("  Son  Lux  ", "Son Lux", "Extra whitespace removal"),
        ("Ol' Burger Beats", "Ol' Burger Beats", "Curly apostrophe normalization"),
        ("Ol' Burger Beats", "Ol' Burger Beats", "Straight apostrophe preserved"),
        ("A$AP Rocky", "A$AP Rocky", "Special characters preserved for artists"),
        ("[bsd.u]", "[bsd.u]", "Brackets preserved for artists"),
        ("Kanye  West  ", "Kanye West", "Multiple spaces collapsed"),
        ("Beyoncé", "Beyoncé", "Unicode normalization"),
        ("  The  Weeknd  ", "The Weeknd", "Leading/trailing/internal whitespace"),
        ("F*ck Buttons", "Fuck Buttons", "Profanity normalization in artist names"),
    ]
    
    passed = 0
    failed = 0
    
    for raw_input, expected, description in test_cases:
        result = clean_csv_input(raw_input, is_artist=True)
        status = "✓" if result == expected else "✗"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} {description}")
        print(f"  Input:    '{raw_input}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        print()
    
    print(f"Artist tests: {passed} passed, {failed} failed")
    print()


def test_album_cleaning():
    """Test cleaning album titles from CSV input."""
    
    print("="*60)
    print("ALBUM TITLE CLEANING TESTS")
    print("="*60)
    
    test_cases = [
        # (input, expected_output, description)
        ("Winter  - EP", "Winter", "EP suffix removal"),
        ("F*ck Love  (Deluxe)", "Fuck Love", "Profanity + Deluxe removal"),
        ("Double Or Nothing (& Metro Boomin)", "Double Or Nothing", "Featuring artist removal"),
        ("Album Name  (Deluxe Edition)  ", "Album Name", "Deluxe Edition suffix removal"),
        ("Title [Explicit]", "Title", "Explicit tag removal"),
        ("My  Album  ", "My Album", "Extra whitespace removal"),
        ("Lanterns - EP", "Lanterns", "Hyphen EP removal"),
        ("DAMN. (Collector's Edition)", "DAMN.", "Collector's Edition removal"),
        ("To Pimp a Butterfly", "To Pimp a Butterfly", "No changes needed"),
        ("Yeezus  ", "Yeezus", "Simple trailing whitespace"),
        ("The Life of Pablo (feat. Rihanna)", "The Life of Pablo", "Featuring in parentheses"),
        ("1989 (Deluxe)", "1989", "Numeric album with Deluxe"),
        ("Good Kid, M.A.A.D City (Deluxe)", "Good Kid, M.A.A.D City", "Complex title with Deluxe"),
    ]
    
    passed = 0
    failed = 0
    
    for raw_input, expected, description in test_cases:
        result = clean_csv_input(raw_input, is_artist=False)
        status = "✓" if result == expected else "✗"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} {description}")
        print(f"  Input:    '{raw_input}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        print()
    
    print(f"Album tests: {passed} passed, {failed} failed")
    print()


def test_edge_cases():
    """Test edge cases and special scenarios."""
    
    print("="*60)
    print("EDGE CASE TESTS")
    print("="*60)
    
    test_cases = [
        # (input, is_artist, expected, description)
        ("", True, "", "Empty string"),
        ("   ", False, "", "Only whitespace"),
        ("A", True, "A", "Single character"),
        ("Σ", True, "Σ", "Greek letter (Unicode)"),
        ("Ö̈", True, "Ö̈", "Combined Unicode characters"),
        ("Test\u200BAlbum", False, "TestAlbum", "Zero-width space removal"),
    ]
    
    passed = 0
    failed = 0
    
    for raw_input, is_artist, expected, description in test_cases:
        result = clean_csv_input(raw_input, is_artist=is_artist)
        status = "✓" if result == expected else "✗"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} {description}")
        print(f"  Input:    '{repr(raw_input)}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        print()
    
    print(f"Edge case tests: {passed} passed, {failed} failed")
    print()


def test_real_world_examples():
    """Test with real-world CSV examples from the albums.csv file."""
    
    print("="*60)
    print("REAL-WORLD EXAMPLES")
    print("="*60)
    
    # Examples from your actual CSV
    examples = [
        ("Son Lux", "Lanterns - EP", False),
        ("Travis Scott", "UTOPIA", False),
        ("Kendrick Lamar", "good kid, m.A.A.d city (Deluxe)", False),
        ("Tyler, The Creator", "IGOR", False),
        ("Frank Ocean", "Blonde", False),
    ]
    
    for artist, album, is_artist in examples:
        clean_artist = clean_csv_input(artist, is_artist=True)
        clean_album = clean_csv_input(album, is_artist=False)
        
        print(f"Original: {artist} - {album}")
        print(f"Cleaned:  {clean_artist} - {clean_album}")
        
        if clean_artist != artist or clean_album != album:
            print(f"  Changes:")
            if clean_artist != artist:
                print(f"    Artist: '{artist}' -> '{clean_artist}'")
            if clean_album != album:
                print(f"    Album:  '{album}' -> '{clean_album}'")
        else:
            print(f"  No cleaning needed")
        print()


if __name__ == "__main__":
    test_artist_cleaning()
    test_album_cleaning()
    test_edge_cases()
    test_real_world_examples()
    
    print("="*60)
    print("TESTING COMPLETE")
    print("="*60)

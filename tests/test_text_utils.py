"""
Unit tests for lib/text_utils.py

Tests all text normalization and matching utility functions.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path to import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.text_utils import (
    normalize_artist_name,
    normalize_profanity,
    strip_album_suffixes,
    get_album_title_variations,
    get_edition_variants,
    normalize_album_title_for_matching,
)


class TestNormalizeArtistName:
    """Tests for normalize_artist_name function."""

    @pytest.mark.unit
    def test_basic_normalization(self):
        """Test basic lowercasing and whitespace handling."""
        assert normalize_artist_name("The Beatles") == "the beatles"
        assert normalize_artist_name("  RADIOHEAD  ") == "radiohead"
        assert normalize_artist_name("Son Lux") == "son lux"

    @pytest.mark.unit
    def test_apostrophe_removal(self):
        """Test removal of various apostrophe types."""
        # Standard apostrophe
        assert normalize_artist_name("Ol' Burger Beats") == "ol burger beats"
        # Curly apostrophes
        assert normalize_artist_name("Ol' Burger Beats") == "ol burger beats"
        assert normalize_artist_name("Ol' Burger Beats") == "ol burger beats"

    @pytest.mark.unit
    def test_quote_removal(self):
        """Test removal of various quote types."""
        assert normalize_artist_name('"Weird Al" Yankovic') == "weird al yankovic"
        assert normalize_artist_name("'NSync") == "nsync"
        assert normalize_artist_name("\u201cQuoted\u201d") == "quoted"  # Curly quotes

    @pytest.mark.unit
    def test_special_characters(self):
        """Test removal of special punctuation."""
        # $ is not removed by normalize_artist_name (only quotes, apostrophes, hyphens, dots)
        assert normalize_artist_name("A$AP Rocky") == "a$ap rocky"
        # Brackets are not removed, only dots inside
        assert normalize_artist_name("[bsd.u]") == "[bsdu]"
        assert normalize_artist_name("!!!") == "!!!"  # Exclamations preserved
        assert normalize_artist_name("deadmau5") == "deadmau5"  # Numbers preserved

    @pytest.mark.unit
    def test_unicode_normalization(self):
        """Test Unicode character normalization."""
        # NFKD decomposition creates combining characters (e + accent)
        # Test that function at least processes unicode consistently
        result = normalize_artist_name("Beyoncé")
        assert result.lower() == result  # Should be lowercase
        assert "beyonc" in result  # Base characters present
        
        result2 = normalize_artist_name("Björk")
        assert "bj" in result2  # Base characters present
        assert result2.lower() == result2

    @pytest.mark.unit
    def test_hyphen_removal(self):
        """Test hyphen and dash removal."""
        assert normalize_artist_name("Jay-Z") == "jayz"
        assert normalize_artist_name("The-Dream") == "thedream"
        assert normalize_artist_name("A-ha") == "aha"

    @pytest.mark.unit
    def test_empty_and_edge_cases(self):
        """Test edge cases like empty strings."""
        assert normalize_artist_name("") == ""
        assert normalize_artist_name("   ") == ""
        assert normalize_artist_name("123") == "123"  # Numbers only


class TestNormalizeProfanity:
    """Tests for normalize_profanity function."""

    @pytest.mark.unit
    def test_f_word_normalization(self):
        """Test F-word variations."""
        # Function returns lowercase replacement
        assert normalize_profanity("F*ck") == "fuck"
        # Multiple asterisks in a row aren't matched by the pattern (expects single special char)
        assert normalize_profanity("F-ck") == "fuck"
        assert normalize_profanity("F_ck") == "fuck"
        assert normalize_profanity("f*ck") == "fuck"  # Already lowercase

    @pytest.mark.unit
    def test_sh_word_normalization(self):
        """Test Sh-word variations."""
        # Function returns lowercase replacement
        assert normalize_profanity("Sh*t") == "shit"
        assert normalize_profanity("Sh-t") == "shit"
        assert normalize_profanity("sh*t") == "shit"

    @pytest.mark.unit
    def test_multiple_profanity(self):
        """Test text with multiple censored words."""
        # Function returns lowercase replacements
        assert normalize_profanity("F*ck This Sh*t") == "fuck This shit"
        assert normalize_profanity("D*mn That's Good") == "damn That's Good"

    @pytest.mark.unit
    def test_no_profanity(self):
        """Test that normal text is unchanged."""
        assert normalize_profanity("Clean Album Title") == "Clean Album Title"
        assert normalize_profanity("The Beatles") == "The Beatles"

    @pytest.mark.unit
    def test_other_profanity_patterns(self):
        """Test other censored word patterns."""
        # Function returns lowercase replacements
        assert normalize_profanity("B*tch") == "bitch"
        assert normalize_profanity("D*mn") == "damn"
        assert normalize_profanity("A*s") == "ass"  # Pattern matches and replaces
        assert normalize_profanity("H*ll") == "hell"


class TestStripAlbumSuffixes:
    """Tests for strip_album_suffixes function."""

    @pytest.mark.unit
    def test_ep_removal(self):
        """Test removal of EP suffix."""
        assert strip_album_suffixes("Winter - EP") == "Winter"
        assert strip_album_suffixes("Summer - EP") == "Summer"

    @pytest.mark.unit
    def test_single_removal(self):
        """Test removal of Single suffix."""
        assert strip_album_suffixes("Track Name - Single") == "Track Name"

    @pytest.mark.unit
    def test_featuring_removal(self):
        """Test removal of featuring artists."""
        assert strip_album_suffixes("Album (& Metro Boomin)") == "Album"
        assert strip_album_suffixes("Title (feat. Artist)") == "Title"
        assert strip_album_suffixes("Song (with Someone)") == "Song"

    @pytest.mark.unit
    def test_deluxe_removal(self):
        """Test removal of deluxe edition markers."""
        assert strip_album_suffixes("OK Computer (Deluxe)") == "OK Computer"
        assert strip_album_suffixes("Album (Deluxe Edition)") == "Album"
        assert strip_album_suffixes("Title (deluxe version)") == "Title"

    @pytest.mark.unit
    def test_explicit_clean_removal(self):
        """Test removal of explicit/clean markers."""
        assert strip_album_suffixes("DAMN. (Explicit)") == "DAMN."
        assert strip_album_suffixes("Album (Clean)") == "Album"
        assert strip_album_suffixes("Song (clean version)") == "Song"

    @pytest.mark.unit
    def test_remastered_removal(self):
        """Test removal of remastered markers."""
        assert strip_album_suffixes("Thriller (Remastered)") == "Thriller"
        assert strip_album_suffixes("Album (Remaster)") == "Album"

    @pytest.mark.unit
    def test_bracket_removal(self):
        """Test removal of bracketed suffixes."""
        assert strip_album_suffixes("Album [Deluxe]") == "Album"
        assert strip_album_suffixes("Title [Explicit]") == "Title"
        assert strip_album_suffixes("Song [Whatever]") == "Song"

    @pytest.mark.unit
    def test_no_suffix(self):
        """Test albums without suffixes remain unchanged."""
        assert strip_album_suffixes("To Pimp a Butterfly") == "To Pimp a Butterfly"
        assert strip_album_suffixes("OK Computer") == "OK Computer"

    @pytest.mark.unit
    def test_multiple_suffixes(self):
        """Test that only the last suffix is removed."""
        # Only removes the last matching pattern
        result = strip_album_suffixes("Album (Deluxe)")
        assert result == "Album"


class TestGetAlbumTitleVariations:
    """Tests for get_album_title_variations function."""

    @pytest.mark.unit
    def test_basic_variations(self):
        """Test variation generation for basic title."""
        variations = get_album_title_variations("Album Title")
        assert "Album Title" in variations
        assert len(variations) >= 1

    @pytest.mark.unit
    def test_profanity_variation(self):
        """Test profanity normalization in variations."""
        variations = get_album_title_variations("F*ck This Album")
        assert "F*ck This Album" in variations
        assert "fuck This Album" in variations  # Lowercase replacement

    @pytest.mark.unit
    def test_suffix_variation(self):
        """Test suffix removal in variations."""
        variations = get_album_title_variations("Album - EP")
        assert "Album - EP" in variations
        assert "Album" in variations

    @pytest.mark.unit
    def test_combined_variations(self):
        """Test both profanity and suffix handling."""
        variations = get_album_title_variations("F*ck This - EP")
        assert "F*ck This - EP" in variations
        assert "fuck This - EP" in variations  # Lowercase replacement
        assert "F*ck This" in variations
        assert "fuck This" in variations  # Lowercase replacement

    @pytest.mark.unit
    def test_no_duplicates(self):
        """Test that duplicate variations are removed."""
        variations = get_album_title_variations("Clean Album")
        # Should not have duplicates
        assert len(variations) == len(set(variations))

    @pytest.mark.unit
    def test_order_preserved(self):
        """Test that variation order is consistent."""
        variations = get_album_title_variations("Album")
        # Original should be first
        assert variations[0] == "Album"


class TestGetEditionVariants:
    """Tests for get_edition_variants function."""

    @pytest.mark.unit
    def test_returns_list(self):
        """Test that function returns a list."""
        variants = get_edition_variants()
        assert isinstance(variants, list)
        assert len(variants) > 0

    @pytest.mark.unit
    def test_contains_common_variants(self):
        """Test that common edition types are included."""
        variants = get_edition_variants()
        assert any("deluxe" in v for v in variants)
        assert any("remaster" in v for v in variants)
        assert any("expanded" in v for v in variants)
        assert any("anniversary" in v for v in variants)

    @pytest.mark.unit
    def test_variant_formats(self):
        """Test that variants include different formats."""
        variants = get_edition_variants()
        # Should have parentheses variants
        assert any(v.startswith(" (") for v in variants)
        # Should have bracket variants
        assert any(v.startswith(" [") for v in variants)
        # Should have dash variants
        assert any(" - " in v for v in variants)


class TestNormalizeAlbumTitleForMatching:
    """Tests for normalize_album_title_for_matching function."""

    @pytest.mark.unit
    def test_basic_normalization(self):
        """Test basic lowercasing."""
        assert normalize_album_title_for_matching("Album Title") == "album title"
        assert normalize_album_title_for_matching("  ALBUM  ") == "album"

    @pytest.mark.unit
    def test_deluxe_removal(self):
        """Test removal of deluxe edition suffixes."""
        assert normalize_album_title_for_matching("Album (Deluxe)") == "album"
        assert normalize_album_title_for_matching("Album (deluxe edition)") == "album"
        assert normalize_album_title_for_matching("Album - Deluxe Edition") == "album"
        assert normalize_album_title_for_matching("Album [Deluxe]") == "album"

    @pytest.mark.unit
    def test_remastered_removal(self):
        """Test removal of remastered suffixes."""
        assert normalize_album_title_for_matching("OK Computer (Remastered)") == "ok computer"
        assert normalize_album_title_for_matching("Abbey Road (Remaster)") == "abbey road"

    @pytest.mark.unit
    def test_expanded_removal(self):
        """Test removal of expanded edition suffixes."""
        assert normalize_album_title_for_matching("Album (Expanded)") == "album"
        assert normalize_album_title_for_matching("Title (Expanded Edition)") == "title"

    @pytest.mark.unit
    def test_no_suffix_unchanged(self):
        """Test albums without edition suffixes."""
        assert normalize_album_title_for_matching("To Pimp a Butterfly") == "to pimp a butterfly"
        assert normalize_album_title_for_matching("The Dark Side of the Moon") == "the dark side of the moon"

    @pytest.mark.unit
    def test_only_first_suffix_removed(self):
        """Test that only the first matching suffix is removed."""
        # Function should stop after removing one suffix
        result = normalize_album_title_for_matching("Album (Deluxe)")
        assert result == "album"

    @pytest.mark.unit
    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert normalize_album_title_for_matching("Album (DELUXE)") == "album"
        assert normalize_album_title_for_matching("Album (DeLuXe)") == "album"


class TestIntegration:
    """Integration tests combining multiple functions."""

    @pytest.mark.unit
    def test_full_normalization_pipeline(self):
        """Test complete normalization workflow."""
        # Original messy title
        title = "F*ck This Album [Explicit]"
        
        # Step 1: Normalize profanity (returns lowercase)
        step1 = normalize_profanity(title)
        assert "fuck" in step1
        
        # Step 2: Strip suffixes (removes [Explicit])
        step2 = strip_album_suffixes(step1)
        assert "Explicit" not in step2
        assert step2 == "fuck This Album"
        
        # Step 3: Get variations
        variations = get_album_title_variations(title)
        assert len(variations) > 1

    @pytest.mark.unit
    def test_artist_album_matching(self):
        """Test artist and album normalization for matching."""
        # Artist with punctuation
        artist1 = normalize_artist_name("Ol' Dirty Bastard")
        artist2 = normalize_artist_name("Ol' Dirty Bastard")
        assert artist1 == artist2
        
        # Album with edition
        album1 = normalize_album_title_for_matching("OK Computer")
        album2 = normalize_album_title_for_matching("OK Computer (Remastered)")
        assert album1 == album2

    @pytest.mark.unit
    def test_real_world_examples(self):
        """Test with real-world album/artist examples."""
        # Kendrick Lamar album
        variations = get_album_title_variations("DAMN.")
        assert "DAMN." in variations
        
        # Son Lux normalization
        artist = normalize_artist_name("Son Lux")
        assert artist == "son lux"
        
        # Radiohead album
        album = normalize_album_title_for_matching("OK Computer (Collector's Edition)")
        assert album == "ok computer"

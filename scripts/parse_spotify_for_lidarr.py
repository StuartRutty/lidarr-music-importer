#!/usr/bin/env python3
"""
parse_spotify_for_lidarr.py

Parse Spotify liked music CSV export to create artist/album pairs for Lidarr import.
Filters out artists with <3 total saved songs and albums with <2 total saved songs.

Output formats:
- CSV: artist,album for direct import to modified add_artists_to_lidarr.py
- JSON: structured data with counts for analysis
"""

import csv
import json
import argparse
import logging
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def parse_spotify_csv(csv_path: str) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """
    Parse Spotify CSV and return artist/album track counts.
    
    Returns:
        artist_albums: {artist_name: {album_name: track_count}}
        artist_totals: {artist_name: total_track_count}
    """
    artist_albums = defaultdict(lambda: defaultdict(int))
    artist_totals = defaultdict(int)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        
        for row in reader:
            if len(row) < 6:
                continue
                
            # Extract relevant fields
            artist_names = row[3].strip()  # Artist Name(s)
            album_name = row[5].strip()    # Album Name
            album_artist = row[7].strip()  # Album Artist Name(s)
            
            # Use album artist if available, otherwise fall back to track artist
            primary_artist = album_artist if album_artist else artist_names
            
            # Handle multiple artists (comma-separated)
            if ',' in primary_artist:
                primary_artist = primary_artist.split(',')[0].strip()
            
            # Skip empty entries
            if not primary_artist or not album_name:
                continue
                
            # Count this track
            artist_albums[primary_artist][album_name] += 1
            artist_totals[primary_artist] += 1
    
    return dict(artist_albums), dict(artist_totals)


def filter_data(artist_albums: Dict[str, Dict[str, int]], 
                artist_totals: Dict[str, int], 
                min_artist_songs: int = 3, 
                min_album_songs: int = 2) -> Dict[str, Dict[str, int]]:
    """
    Filter artists and albums based on minimum song counts.
    """
    filtered = {}
    
    for artist, albums in artist_albums.items():
        # Skip artists with too few total songs
        if artist_totals[artist] < min_artist_songs:
            continue
            
        # Filter albums with too few songs
        filtered_albums = {album: count for album, count in albums.items() 
                          if count >= min_album_songs}
        
        # Only include artist if they have qualifying albums
        if filtered_albums:
            filtered[artist] = filtered_albums
    
    return filtered


def generate_output(filtered_data: Dict[str, Dict[str, int]], 
                   output_csv: str, 
                   output_json: str = None):
    """
    Generate CSV and optionally JSON output files.
    """
    # Generate CSV for Lidarr import
    artist_album_pairs = []
    for artist, albums in filtered_data.items():
        for album in albums.keys():
            artist_album_pairs.append([artist, album])
    
    # Sort by artist name, then album name
    artist_album_pairs.sort(key=lambda x: (x[0].lower(), x[1].lower()))
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['artist', 'album'])  # Header
        writer.writerows(artist_album_pairs)
    
    logging.info(f"Created CSV with {len(artist_album_pairs)} artist/album pairs: {output_csv}")
    
    # Generate JSON for analysis (optional)
    if output_json:
        analysis_data = {
            'metadata': {
                'total_artists': len(filtered_data),
                'total_albums': sum(len(albums) for albums in filtered_data.values()),
                'total_artist_album_pairs': len(artist_album_pairs)
            },
            'artists': {}
        }
        
        for artist, albums in filtered_data.items():
            analysis_data['artists'][artist] = {
                'total_songs': sum(albums.values()),
                'albums': albums
            }
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Created analysis JSON: {output_json}")


def print_statistics(artist_totals: Dict[str, int], 
                    filtered_data: Dict[str, Dict[str, int]], 
                    min_artist_songs: int, 
                    min_album_songs: int):
    """
    Print filtering statistics.
    """
    total_artists = len(artist_totals)
    total_songs = sum(artist_totals.values())
    
    filtered_artists = len(filtered_data)
    filtered_albums = sum(len(albums) for albums in filtered_data.values())
    filtered_songs = sum(sum(albums.values()) for albums in filtered_data.values())
    
    print(f"\n=== FILTERING STATISTICS ===")
    print(f"Original data:")
    print(f"  - {total_artists} artists")
    print(f"  - {total_songs} total songs")
    
    print(f"\nFiltered data (≥{min_artist_songs} songs per artist, ≥{min_album_songs} songs per album):")
    print(f"  - {filtered_artists} artists ({filtered_artists/total_artists*100:.1f}%)")
    print(f"  - {filtered_albums} albums")
    print(f"  - {filtered_songs} songs ({filtered_songs/total_songs*100:.1f}%)")
    
    print(f"\nTop 10 artists by album count:")
    artist_album_counts = [(artist, len(albums)) for artist, albums in filtered_data.items()]
    artist_album_counts.sort(key=lambda x: x[1], reverse=True)
    
    for artist, album_count in artist_album_counts[:10]:
        song_count = sum(filtered_data[artist].values())
        print(f"  - {artist}: {album_count} albums, {song_count} songs")


def main():
    parser = argparse.ArgumentParser(description="Parse Spotify CSV for Lidarr import")
    parser.add_argument("input_csv", help="Path to Spotify liked songs CSV export")
    parser.add_argument("-o", "--output", default="artist_album_pairs.csv", 
                       help="Output CSV file (default: artist_album_pairs.csv)")
    parser.add_argument("--json", help="Optional JSON output file for analysis")
    parser.add_argument("--min-artist-songs", type=int, default=3,
                       help="Minimum songs per artist (default: 3)")
    parser.add_argument("--min-album-songs", type=int, default=2,
                       help="Minimum songs per album (default: 2)")
    parser.add_argument("--stats-only", action="store_true",
                       help="Only show statistics, don't generate output files")
    
    args = parser.parse_args()
    
    # Parse the CSV
    logging.info(f"Parsing Spotify CSV: {args.input_csv}")
    artist_albums, artist_totals = parse_spotify_csv(args.input_csv)
    
    # Apply filters
    filtered_data = filter_data(artist_albums, artist_totals, 
                               args.min_artist_songs, args.min_album_songs)
    
    # Show statistics
    print_statistics(artist_totals, filtered_data, 
                    args.min_artist_songs, args.min_album_songs)
    
    # Generate output files (unless stats-only)
    if not args.stats_only:
        generate_output(filtered_data, args.output, args.json)


if __name__ == "__main__":
    main()
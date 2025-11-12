#!/usr/bin/env python3
"""
Restore album titles from backup while keeping cleaned artist names and current status.
This script combines the cleaned artist names from albums.csv with the original 
album titles from albums_backup.csv.
"""

import csv
import shutil

def restore_album_titles():
    """Restore album titles from backup while preserving cleaned artist names and status."""
    
    backup_file = 'albums_backup.csv'
    current_file = 'albums.csv'
    output_file = 'albums_restored.csv'
    
    # Read the backup file to get original album titles
    backup_data = {}
    with open(backup_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use artist + album as key to match rows
            key = f"{row['artist']}|{row['album']}"
            backup_data[key] = {
                'artist': row['artist'],
                'album': row['album'],
                'status': row.get('status', '')
            }
    
    print(f"Loaded {len(backup_data)} entries from backup")
    
    # Read the current file with cleaned artist names
    current_data = []
    with open(current_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            current_data.append({
                'artist': row['artist'],
                'album': row['album'], 
                'status': row.get('status', '')
            })
    
    print(f"Loaded {len(current_data)} entries from current file")
    
    # Create restored data
    restored_data = []
    matches_found = 0
    
    for current_row in current_data:
        # Try to find matching entry in backup using different strategies
        match_found = False
        
        # Strategy 1: Try exact match with current artist name
        key1 = f"{current_row['artist']}|{current_row['album']}"
        if key1 in backup_data:
            # Use backup album title with current (cleaned) artist name and current status
            restored_data.append({
                'artist': current_row['artist'],  # Keep cleaned artist name
                'album': backup_data[key1]['album'],  # Restore original album title
                'status': current_row['status']  # Keep current status
            })
            matches_found += 1
            match_found = True
        else:
            # Strategy 2: Try to find by looking for original artist name patterns
            # Check if current artist is a cleaned version of a backup artist
            for backup_key, backup_row in backup_data.items():
                backup_artist = backup_row['artist']
                backup_album = backup_row['album']
                
                # Check if this could be the same artist (cleaned vs original)
                # Handle bracket removal: [bsd.u] -> bsd.u
                if (backup_artist.startswith('[') and backup_artist.endswith(']') and
                    backup_artist.strip('[]') == current_row['artist']):
                    if backup_album == current_row['album']:
                        restored_data.append({
                            'artist': current_row['artist'],  # Keep cleaned artist name
                            'album': backup_album,  # Use original album title
                            'status': current_row['status']  # Keep current status
                        })
                        matches_found += 1
                        match_found = True
                        break
                
                # Handle space variations in artist names
                if (backup_artist.replace(' ', '').lower() == current_row['artist'].replace(' ', '').lower() and
                    backup_album == current_row['album']):
                    restored_data.append({
                        'artist': current_row['artist'],  # Keep cleaned artist name
                        'album': backup_album,  # Use original album title
                        'status': current_row['status']  # Keep current status
                    })
                    matches_found += 1
                    match_found = True
                    break
        
        # If no match found, keep current row as-is
        if not match_found:
            restored_data.append(current_row)
    
    # Write restored data
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['artist', 'album', 'status']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(restored_data)
    
    print(f"Restoration complete!")
    print(f"  - Matches found and restored: {matches_found}")
    print(f"  - Total rows processed: {len(restored_data)}")
    print(f"  - Output written to: {output_file}")
    
    # Create final backup and replace original
    shutil.copy2(current_file, 'albums_before_restore.csv')
    shutil.move(output_file, current_file)
    
    print(f"  - Original file backed up as: albums_before_restore.csv")
    print(f"  - Restored file saved as: {current_file}")

if __name__ == '__main__':
    restore_album_titles()
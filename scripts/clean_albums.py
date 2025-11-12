#!/usr/bin/env python3
"""
Clean special characters from albums.csv for MusicBrainz and Lidarr compatibility.
Removes problematic characters like brackets, dollar signs, and other special chars
that can cause issues with music database lookups.
"""

import csv
import re
import shutil
import os

def clean_text(text):
    """Clean special characters from artist/album names."""
    if not text:
        return text
    
    # Remove brackets and their contents only if they contain specific patterns
    # Keep brackets that are part of album titles like "36 Chambers" but remove artist name brackets
    text = re.sub(r'^\[([^\]]+)\]$', r'\1', text)  # Remove brackets around entire field
    
    # Clean specific patterns
    text = re.sub(r'\[([^\]]*)\]', r'\1', text)  # Remove all brackets but keep content
    # Note: Keeping dollar signs as requested
    
    # Clean up any double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def main():
    input_file = 'albums.csv'
    output_file = 'albums_cleaned.csv'
    backup_file = 'albums_backup.csv'
    
    # Create backup
    if os.path.exists(input_file):
        shutil.copy2(input_file, backup_file)
        print(f"Created backup: {backup_file}")
    
    cleaned_count = 0
    total_count = 0
    
    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            
            # Process header
            headers = next(reader)
            writer.writerow(headers)
            
            # Process data rows
            for row in reader:
                total_count += 1
                original_row = row.copy()
                
                if len(row) >= 2:  # Ensure we have artist and album columns
                    # Clean artist name (first column)
                    cleaned_artist = clean_text(row[0])
                    
                    # Clean album name (second column)
                    cleaned_album = clean_text(row[1])
                    
                    # Update row
                    row[0] = cleaned_artist
                    row[1] = cleaned_album
                    
                    # Check if anything was changed
                    if original_row != row:
                        cleaned_count += 1
                        print(f"Cleaned: '{original_row[0]}' -> '{row[0]}', '{original_row[1]}' -> '{row[1]}'")
                
                writer.writerow(row)
    
    # Replace original file
    shutil.move(output_file, input_file)
    
    print(f"\nCleaning complete!")
    print(f"Total rows processed: {total_count}")
    print(f"Rows cleaned: {cleaned_count}")
    print(f"Original file backed up as: {backup_file}")

if __name__ == '__main__':
    main()
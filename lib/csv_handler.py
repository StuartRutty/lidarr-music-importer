"""
CSV Handler for Artist/Album Import

Provides functionality for reading and updating CSV files that track
artist/album pairs with processing status codes.

The status tracking enables resumable imports and detailed progress reporting.
"""

import csv
import logging
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ItemStatus:
    """
    Status codes for artist/album import tracking.
    
    These status codes provide clear, actionable feedback about the state
    of each import attempt and guide retry/skip logic.
    """
    # SUCCESS STATES (completed, no retry needed)
    SUCCESS = 'success'
    
    # PENDING STATES (temporary, retry recommended)
    PENDING_REFRESH = 'pending_refresh'
    PENDING_IMPORT = 'pending_import'
    
    # SKIP STATES (permanent, no retry needed)
    SKIP = 'skip'
    SKIP_NO_MUSICBRAINZ = 'skip_no_musicbrainz'
    SKIP_NO_ARTIST_MATCH = 'skip_no_artist_match'
    SKIP_API_ERROR = 'skip_api_error'
    SKIP_ARTIST_EXISTS = 'skip_artist_exists'
    SKIP_ALBUM_MB_NORESULTS = 'skip_album_mb_noresults'
    ALREADY_MONITORED = 'already_monitored'
    
    # ERROR STATES (temporary, retry possible)
    ERROR_CONNECTION = 'error_connection'
    ERROR_TIMEOUT = 'error_timeout'
    ERROR_INVALID_DATA = 'error_invalid_data'
    ERROR_UNKNOWN = 'error_unknown'
    
    # TESTING STATES
    DRY_RUN = 'dry_run'
    
    @classmethod
    def is_success(cls, status: str) -> bool:
        """Check if status indicates successful completion."""
        return status in (cls.SUCCESS,)
    
    @classmethod
    def is_pending(cls, status: str) -> bool:
        """Check if status indicates pending/in-progress state."""
        return status in (cls.PENDING_REFRESH, cls.PENDING_IMPORT)
    
    @classmethod
    def is_skip(cls, status: str) -> bool:
        """Check if status indicates permanent skip (don't retry)."""
        return status in (
            cls.SKIP, cls.SKIP_NO_MUSICBRAINZ, 
            cls.SKIP_NO_ARTIST_MATCH, cls.SKIP_API_ERROR,
            cls.SKIP_ARTIST_EXISTS, cls.SKIP_ALBUM_MB_NORESULTS,
            cls.ALREADY_MONITORED
        )
    
    @classmethod
    def is_error(cls, status: str) -> bool:
        """Check if status indicates temporary error (retry possible)."""
        return status in (
            cls.ERROR_CONNECTION, cls.ERROR_TIMEOUT,
            cls.ERROR_INVALID_DATA, cls.ERROR_UNKNOWN
        )
    
    @classmethod
    def should_retry(cls, status: str) -> bool:
        """Check if status indicates item should be retried."""
        return status == '' or cls.is_error(status) or cls.is_pending(status)


class CSVHandler:
    """
    Handler for CSV files containing artist/album pairs with status tracking.
    
    Expected CSV format:
        artist,album[,status]
        "Artist Name","Album Title"[,"status_code"]
    
    The status column is optional but enables resumable imports by tracking
    which items have been processed.
    """
    
    def __init__(self, csv_path: str):
        """
        Initialize the CSV handler.
        
        Args:
            csv_path: Path to the CSV file
        """
        self.csv_path = Path(csv_path)
        self.has_status_column = False
        
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        logger.info(f"CSVHandler initialized for {self.csv_path}")
    
    def read_items(self) -> Tuple[List[Dict[str, str]], bool]:
        """
        Read CSV file containing artist/album pairs with optional progress tracking.
        
        Also checks for MusicBrainz ID columns (mb_artist_id, mb_release_id) added
        by universal_parser.py --enrich-musicbrainz feature.
        
        Returns:
            Tuple of (list of items with artist/album/status/mb_ids, has_status_column boolean)
        """
        items = []
        
        with open(self.csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames
            
            # Auto-detect if CSV already has status tracking
            if fieldnames and 'status' in fieldnames:
                self.has_status_column = True
                logger.info("Found existing status column, will track progress")
            else:
                self.has_status_column = False
            
            # Check for MusicBrainz ID columns
            has_mb_ids = fieldnames and 'mb_artist_id' in fieldnames and 'mb_release_id' in fieldnames
            if has_mb_ids:
                logger.info("Found MusicBrainz ID columns (enriched CSV from universal_parser)")
            
            for row in reader:
                artist = row.get('artist', '').strip()
                album = row.get('album', '').strip()
                status = row.get('status', '').strip() if self.has_status_column else ''
                
                # Read MB IDs if present (will be empty strings if not enriched)
                mb_artist_id = row.get('mb_artist_id', '').strip() if has_mb_ids else ''
                mb_release_id = row.get('mb_release_id', '').strip() if has_mb_ids else ''
                
                # Only include rows with both artist and album
                if artist and album:
                    items.append({
                        "artist": artist, 
                        "album": album, 
                        "status": status,
                        "mb_artist_id": mb_artist_id,
                        "mb_release_id": mb_release_id,
                        "row_num": reader.line_num
                    })
        
        logger.info(f"Read {len(items)} items from CSV")
        if has_mb_ids:
            enriched_count = sum(1 for item in items if item.get('mb_release_id'))
            logger.info(f"  📍 {enriched_count} items have MusicBrainz IDs")
        return items, self.has_status_column
    
    def update_all_statuses(self, items: List[Dict[str, str]]):
        """
        Update the CSV file with processing status for all items.
        
        This is typically called after processing a batch of items to persist
        all status updates at once.
        
        Args:
            items: List of processed items with updated status
        """
        if not items:
            logger.info("No items to update in CSV")
            return
        
        logger.info(f"Updating CSV status for {len(items)} items...")
        
        try:
            # Read original file to preserve structure and order
            logger.debug(f"Reading original CSV file: {self.csv_path}")
            with open(self.csv_path, 'r', newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                fieldnames = list(reader.fieldnames) if reader.fieldnames else ['artist', 'album']
                
                # Add status column if it doesn't exist
                if 'status' not in fieldnames:
                    fieldnames.append('status')
                    logger.info("Added 'status' column to CSV")
                    self.has_status_column = True
                else:
                    logger.debug("CSV already has 'status' column")
                
                all_rows = list(reader)
            
            logger.debug(f"Read {len(all_rows)} rows from CSV")
            
            # Create lookup for status updates based on artist+album combination
            status_lookup = {f"{item['artist']}|{item['album']}": item['status'] for item in items}
            logger.debug(f"Created status lookup with {len(status_lookup)} entries")
            
            # Track what we're updating for debugging
            updates_made = 0
            
            # Write back with updated status information
            logger.debug(f"Writing updated CSV file: {self.csv_path}")
            with open(self.csv_path, 'w', newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in all_rows:
                    key = f"{row['artist']}|{row['album']}"
                    if key in status_lookup:
                        old_status = row.get('status', '')
                        new_status = status_lookup[key]
                        row['status'] = new_status
                        updates_made += 1
                        logger.debug(f"Updated status for '{key}': '{old_status}' -> '{new_status}'")
                    elif 'status' not in row:
                        row['status'] = ''  # Empty status for newly added column
                    writer.writerow(row)
            
            logger.info(f"✅ CSV update complete: {self.csv_path}")
            logger.info(f"   - Total rows: {len(all_rows)}")
            logger.info(f"   - Status updates made: {updates_made}")
            
        except PermissionError:
            logger.error(f"Permission denied writing to CSV file: {self.csv_path}")
            logger.error("Tip: Make sure the CSV file is not open in Excel or another program")
        except Exception as e:
            logger.exception(f"Failed to update CSV status: %s", e)
            if "encoding" in str(e).lower():
                logger.error("Tip: Try ensuring the CSV file uses UTF-8 encoding")
    
    def update_single_status(self, artist: str, album: str, status: str):
        """
        Update status for a single item in the CSV file immediately after processing.
        
        This provides real-time status updates during processing, allowing you to:
        - Monitor progress by checking the CSV file during execution
        - Resume interrupted runs with accurate status tracking
        - Identify failures as they happen without waiting for completion
        
        Args:
            artist: Artist name to match
            album: Album name to match
            status: New status code to set
        """
        try:
            # Read all rows
            with open(self.csv_path, 'r', newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                fieldnames = list(reader.fieldnames) if reader.fieldnames else ['artist', 'album']
                
                # Add status column if it doesn't exist
                if 'status' not in fieldnames:
                    fieldnames.append('status')
                    self.has_status_column = True
                
                all_rows = list(reader)
            
            # Update the matching row
            key = f"{artist}|{album}"
            updated = False
            for row in all_rows:
                row_key = f"{row['artist']}|{row['album']}"
                if row_key == key:
                    row['status'] = status
                    updated = True
                    break
            
            if not updated:
                logger.warning(f"Could not find row in CSV to update: {artist} - {album}")
                return
            
            # Write back
            with open(self.csv_path, 'w', newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            
            logger.debug(f"✅ Updated CSV status: {artist} - {album} -> {status}")
            
        except Exception as e:
            logger.warning(f"Failed to update single item status in CSV: {e}")
            # Don't fail the entire run if CSV update fails
    
    def filter_items_by_status(
        self, 
        items: List[Dict[str, str]], 
        skip_completed: bool = True,
        skip_permanent_failures: bool = True
    ) -> List[Dict[str, str]]:
        """
        Filter items based on their status codes.
        
        Args:
            items: List of items to filter
            skip_completed: Skip items with success status (default: True)
            skip_permanent_failures: Skip items with permanent skip status (default: True)
            
        Returns:
            Filtered list of items to process
        """
        filtered = []
        skipped_count = 0
        
        for item in items:
            status = item.get('status', '')
            
            # Skip successful items if requested
            if skip_completed and ItemStatus.is_success(status):
                skipped_count += 1
                continue
            
            # Skip permanent failures if requested
            if skip_permanent_failures and ItemStatus.is_skip(status):
                skipped_count += 1
                continue
            
            # Include everything else (empty, pending, errors)
            filtered.append(item)
        
        if skipped_count > 0:
            logger.info(f"Filtered out {skipped_count} already processed/failed items")
        
        return filtered
    
    def get_status_summary(self, items: List[Dict[str, str]]) -> Dict[str, int]:
        """
        Generate a summary of status codes across all items.
        
        Args:
            items: List of items to summarize
            
        Returns:
            Dictionary mapping status codes to counts
        """
        summary = {}
        for item in items:
            status = item.get('status', 'unknown')
            summary[status] = summary.get(status, 0) + 1
        return summary
    
    def __repr__(self) -> str:
        """String representation of the handler."""
        return f"CSVHandler(path={self.csv_path}, has_status={self.has_status_column})"

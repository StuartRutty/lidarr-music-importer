"""
Tests for CSV Handler Module

Tests the CSVHandler class and ItemStatus enum for reading, writing,
and filtering CSV files with status tracking.
"""

import pytest
import csv
from pathlib import Path
from lib.csv_handler import CSVHandler, ItemStatus


class TestItemStatus:
    """Test the ItemStatus enum and its helper methods."""
    
    def test_success_statuses(self):
        """Test identification of success statuses."""
        assert ItemStatus.is_success('success')
        assert not ItemStatus.is_success('already_monitored')
        assert not ItemStatus.is_success('pending_refresh')
        assert not ItemStatus.is_success('error_timeout')
    
    def test_pending_statuses(self):
        """Test identification of pending statuses."""
        assert ItemStatus.is_pending('pending_refresh')
        assert ItemStatus.is_pending('pending_import')
        assert not ItemStatus.is_pending('success')
        assert not ItemStatus.is_pending('error_timeout')
    
    def test_skip_statuses(self):
        """Test identification of skip statuses."""
        assert ItemStatus.is_skip('skip')
        assert ItemStatus.is_skip('skip_no_musicbrainz')
        assert ItemStatus.is_skip('skip_no_artist_match')
        assert ItemStatus.is_skip('skip_api_error')
        assert ItemStatus.is_skip('already_monitored')
        assert not ItemStatus.is_skip('success')
        assert not ItemStatus.is_skip('error_timeout')
    
    def test_error_statuses(self):
        """Test identification of error statuses."""
        assert ItemStatus.is_error('error_connection')
        assert ItemStatus.is_error('error_timeout')
        assert ItemStatus.is_error('error_invalid_data')
        assert ItemStatus.is_error('error_unknown')
        assert not ItemStatus.is_error('success')
        assert not ItemStatus.is_error('skip')
    
    def test_should_retry_logic(self):
        """Test retry logic for different statuses."""
        # Empty status should be retried
        assert ItemStatus.should_retry('')
        
        # Errors should be retried
        assert ItemStatus.should_retry('error_timeout')
        assert ItemStatus.should_retry('error_connection')
        
        # Pending should be retried
        assert ItemStatus.should_retry('pending_refresh')
        assert ItemStatus.should_retry('pending_import')
        
        # Success should not be retried
        assert not ItemStatus.should_retry('success')
        assert not ItemStatus.should_retry('already_monitored')
        
        # Skip should not be retried
        assert not ItemStatus.should_retry('skip_no_musicbrainz')
        assert not ItemStatus.should_retry('skip_api_error')


class TestCSVHandlerInit:
    """Test CSVHandler initialization."""
    
    def test_init_with_valid_file(self, sample_csv_file):
        """Test initialization with valid CSV file."""
        handler = CSVHandler(sample_csv_file)
        assert handler.csv_path == Path(sample_csv_file)
        assert handler.csv_path.exists()
    
    def test_init_with_nonexistent_file(self, tmp_path):
        """Test initialization with non-existent file raises error."""
        fake_path = tmp_path / "nonexistent.csv"
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            CSVHandler(str(fake_path))
    
    def test_repr(self, sample_csv_file):
        """Test string representation."""
        handler = CSVHandler(sample_csv_file)
        repr_str = repr(handler)
        assert 'CSVHandler' in repr_str
        assert str(sample_csv_file) in repr_str


class TestCSVHandlerReadItems:
    """Test reading items from CSV files."""
    
    def test_read_basic_csv_without_status(self, tmp_path):
        """Test reading CSV without status column."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("artist,album\nTaylor Swift,1989\nThe Beatles,Abbey Road\n")
        
        handler = CSVHandler(str(csv_file))
        items, has_status = handler.read_items()
        
        assert len(items) == 2
        assert not has_status
        assert items[0]['artist'] == 'Taylor Swift'
        assert items[0]['album'] == '1989'
        assert items[0]['status'] == ''
        assert items[1]['artist'] == 'The Beatles'
        assert items[1]['album'] == 'Abbey Road'
    
    def test_read_csv_with_status(self, tmp_path):
        """Test reading CSV with status column."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album,status\n"
            "Taylor Swift,1989,success\n"
            "The Beatles,Abbey Road,pending_refresh\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, has_status = handler.read_items()
        
        assert len(items) == 2
        assert has_status
        assert items[0]['status'] == 'success'
        assert items[1]['status'] == 'pending_refresh'
    
    def test_read_csv_skips_empty_rows(self, tmp_path):
        """Test that empty rows are skipped."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            "Taylor Swift,1989\n"
            ",\n"  # Empty row
            "The Beatles,Abbey Road\n"
            "Artist Only,\n"  # Missing album
            ",Album Only\n"  # Missing artist
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Only complete rows should be included
        assert len(items) == 2
        assert items[0]['artist'] == 'Taylor Swift'
        assert items[1]['artist'] == 'The Beatles'
    
    def test_read_csv_strips_whitespace(self, tmp_path):
        """Test that whitespace is stripped from values."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            " Taylor Swift , 1989 \n"
            "  The Beatles  ,  Abbey Road  \n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        assert items[0]['artist'] == 'Taylor Swift'
        assert items[0]['album'] == '1989'
        assert items[1]['artist'] == 'The Beatles'
        assert items[1]['album'] == 'Abbey Road'
    
    def test_read_csv_with_special_characters(self, tmp_path):
        """Test reading CSV with special characters."""
        csv_file = tmp_path / "test.csv"
        # Write with proper quoting for special characters
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['artist', 'album'])
            writer.writerow(['$uicideboy$', 'I Want to Die in New Orleans'])
            writer.writerow(['!llmind', 'Boomtrap Protocol'])
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        assert len(items) == 2
        assert items[0]['artist'] == '$uicideboy$'
        assert items[1]['artist'] == '!llmind'
    
    def test_read_includes_row_numbers(self, tmp_path):
        """Test that row numbers are tracked."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            "Taylor Swift,1989\n"
            "The Beatles,Abbey Road\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        assert 'row_num' in items[0]
        assert 'row_num' in items[1]
        # Row numbers start at 2 (after header)
        assert int(items[0]['row_num']) >= 2
        assert int(items[1]['row_num']) >= 3


class TestCSVHandlerUpdateAllStatuses:
    """Test batch status updates."""
    
    def test_update_all_statuses_adds_status_column(self, tmp_path):
        """Test that status column is added if missing."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("artist,album\nTaylor Swift,1989\n")
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Update status
        items[0]['status'] = 'success'
        handler.update_all_statuses(items)
        
        # Read back and verify
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            assert fieldnames is not None
            assert 'status' in fieldnames
            row = next(reader)
            assert row['status'] == 'success'
    
    def test_update_all_statuses_preserves_existing(self, tmp_path):
        """Test that existing status column is preserved."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album,status\n"
            "Taylor Swift,1989,pending\n"
            "The Beatles,Abbey Road,error\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Update statuses
        items[0]['status'] = 'success'
        items[1]['status'] = 'already_monitored'
        handler.update_all_statuses(items)
        
        # Read back
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]['status'] == 'success'
            assert rows[1]['status'] == 'already_monitored'
    
    def test_update_all_statuses_preserves_order(self, tmp_path):
        """Test that row order is preserved."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            "Artist A,Album A\n"
            "Artist B,Album B\n"
            "Artist C,Album C\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Update all statuses
        for item in items:
            item['status'] = 'success'
        handler.update_all_statuses(items)
        
        # Verify order preserved
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]['artist'] == 'Artist A'
            assert rows[1]['artist'] == 'Artist B'
            assert rows[2]['artist'] == 'Artist C'
    
    def test_update_all_statuses_with_empty_list(self, tmp_path):
        """Test update with empty item list."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("artist,album\nTaylor Swift,1989\n")
        
        handler = CSVHandler(str(csv_file))
        # Should not error with empty list
        handler.update_all_statuses([])
        
        # File should be unchanged
        with open(csv_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'Taylor Swift' in content
    
    def test_update_all_statuses_partial_update(self, tmp_path):
        """Test updating only some items."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            "Artist A,Album A\n"
            "Artist B,Album B\n"
            "Artist C,Album C\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Only update the first item
        items[0]['status'] = 'success'
        handler.update_all_statuses([items[0]])
        
        # Read back - first should have status, others empty
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]['status'] == 'success'
            assert rows[1]['status'] == ''
            assert rows[2]['status'] == ''


class TestCSVHandlerUpdateSingleStatus:
    """Test single item status updates."""
    
    def test_update_single_status_success(self, tmp_path):
        """Test updating single item status."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "artist,album\n"
            "Taylor Swift,1989\n"
            "The Beatles,Abbey Road\n"
        )
        
        handler = CSVHandler(str(csv_file))
        handler.read_items()  # Initialize
        
        # Update single item
        handler.update_single_status('Taylor Swift', '1989', 'success')
        
        # Verify only that item was updated
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]['status'] == 'success'
            assert rows[1]['status'] == ''
    
    def test_update_single_status_not_found(self, tmp_path, caplog):
        """Test updating non-existent item logs warning."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("artist,album\nTaylor Swift,1989\n")
        
        handler = CSVHandler(str(csv_file))
        handler.read_items()
        
        # Try to update non-existent item
        handler.update_single_status('Unknown Artist', 'Unknown Album', 'success')
        
        # Should log warning
        assert 'Could not find row' in caplog.text


class TestCSVHandlerFilterItems:
    """Test item filtering by status."""
    
    def test_filter_skip_completed(self):
        """Test filtering out completed items."""
        items = [
            {'artist': 'A', 'album': 'X', 'status': 'success'},
            {'artist': 'B', 'album': 'Y', 'status': 'pending_refresh'},
            {'artist': 'C', 'album': 'Z', 'status': 'already_monitored'},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)  # Create without init
        filtered = handler.filter_items_by_status(items, skip_completed=True)
        
        # Only pending should remain
        assert len(filtered) == 1
        assert filtered[0]['artist'] == 'B'
    
    def test_filter_skip_permanent_failures(self):
        """Test filtering out permanent failures."""
        items = [
            {'artist': 'A', 'album': 'X', 'status': 'skip_no_musicbrainz'},
            {'artist': 'B', 'album': 'Y', 'status': 'error_timeout'},
            {'artist': 'C', 'album': 'Z', 'status': 'skip_api_error'},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)
        filtered = handler.filter_items_by_status(items, skip_permanent_failures=True)
        
        # Only error (retryable) should remain
        assert len(filtered) == 1
        assert filtered[0]['artist'] == 'B'
    
    def test_filter_keep_empty_status(self):
        """Test that empty status items are kept."""
        items = [
            {'artist': 'A', 'album': 'X', 'status': ''},
            {'artist': 'B', 'album': 'Y', 'status': 'success'},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)
        filtered = handler.filter_items_by_status(items, skip_completed=True)
        
        # Empty status should be kept
        assert len(filtered) == 1
        assert filtered[0]['artist'] == 'A'
    
    def test_filter_no_filters(self):
        """Test filtering with all filters disabled."""
        items = [
            {'artist': 'A', 'album': 'X', 'status': 'success'},
            {'artist': 'B', 'album': 'Y', 'status': 'skip_no_musicbrainz'},
            {'artist': 'C', 'album': 'Z', 'status': 'error_timeout'},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)
        filtered = handler.filter_items_by_status(
            items, 
            skip_completed=False, 
            skip_permanent_failures=False
        )
        
        # All items should be kept
        assert len(filtered) == 3


class TestCSVHandlerGetStatusSummary:
    """Test status summary generation."""
    
    def test_get_status_summary_basic(self):
        """Test basic status summary."""
        items = [
            {'status': 'success'},
            {'status': 'success'},
            {'status': 'error_timeout'},
            {'status': 'pending_refresh'},
            {'status': 'success'},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)
        summary = handler.get_status_summary(items)
        
        assert summary['success'] == 3
        assert summary['error_timeout'] == 1
        assert summary['pending_refresh'] == 1
    
    def test_get_status_summary_empty(self):
        """Test summary with empty list."""
        handler = CSVHandler.__new__(CSVHandler)
        summary = handler.get_status_summary([])
        assert summary == {}
    
    def test_get_status_summary_with_empty_status(self):
        """Test summary with empty status values."""
        items = [
            {'status': ''},
            {'status': 'success'},
            {'status': ''},
        ]
        
        handler = CSVHandler.__new__(CSVHandler)
        summary = handler.get_status_summary(items)
        
        assert summary[''] == 2
        assert summary['success'] == 1


class TestCSVHandlerIntegration:
    """Integration tests for full CSV workflows."""
    
    def test_full_workflow_read_process_update(self, tmp_path):
        """Test complete workflow: read, process, update."""
        csv_file = tmp_path / "workflow.csv"
        csv_file.write_text(
            "artist,album\n"
            "Taylor Swift,1989\n"
            "The Beatles,Abbey Road\n"
            "Unknown,Bad Album\n"
        )
        
        # Read items
        handler = CSVHandler(str(csv_file))
        items, has_status = handler.read_items()
        assert len(items) == 3
        assert not has_status
        
        # Simulate processing
        items[0]['status'] = 'success'
        items[1]['status'] = 'already_monitored'
        items[2]['status'] = 'skip_no_musicbrainz'
        
        # Update CSV
        handler.update_all_statuses(items)
        
        # Read back and verify
        handler2 = CSVHandler(str(csv_file))
        items2, has_status2 = handler2.read_items()
        assert has_status2
        assert items2[0]['status'] == 'success'
        assert items2[1]['status'] == 'already_monitored'
        assert items2[2]['status'] == 'skip_no_musicbrainz'
    
    def test_resume_workflow(self, tmp_path):
        """Test resuming interrupted import."""
        csv_file = tmp_path / "resume.csv"
        csv_file.write_text(
            "artist,album,status\n"
            "Artist A,Album A,success\n"
            "Artist B,Album B,\n"
            "Artist C,Album C,error_timeout\n"
            "Artist D,Album D,skip_no_musicbrainz\n"
        )
        
        handler = CSVHandler(str(csv_file))
        items, _ = handler.read_items()
        
        # Filter for resume (skip completed and permanent failures)
        filtered = handler.filter_items_by_status(
            items,
            skip_completed=True,
            skip_permanent_failures=True
        )
        
        # Should only process items B and C (empty and error)
        assert len(filtered) == 2
        assert filtered[0]['artist'] == 'Artist B'
        assert filtered[1]['artist'] == 'Artist C'

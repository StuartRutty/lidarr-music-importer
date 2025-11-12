from pathlib import Path
import csv

from lib import parser_utils


def test_process_csv_dry_run(tmp_path: Path):
    p = tmp_path / 'albums.csv'
    rows = [
        {'artist': 'Artist A', 'album': 'Album (Deluxe)', 'status': 'pending'},
        {'artist': 'Artist B', 'album': 'Song', 'status': 'done'},
    ]
    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['artist', 'album', 'status'])
        writer.writeheader()
        writer.writerows(rows)

    stats = parser_utils.process_csv(p, status_filter=None, dry_run=True)
    assert stats['total_rows'] == 2
    assert stats['processed_rows'] == 2
    assert stats['changed_rows'] == 1
    # Ensure file unchanged
    with p.open('r', encoding='utf-8') as f:
        content = f.read()
    assert 'Album (Deluxe)' in content


def test_process_csv_apply_changes_and_backup(tmp_path: Path):
    p = tmp_path / 'albums.csv'
    rows = [
        {'artist': 'Artist A', 'album': 'Album (Deluxe)', 'status': 'pending'},
        {'artist': 'Artist B', 'album': 'Song', 'status': 'done'},
    ]
    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['artist', 'album', 'status'])
        writer.writeheader()
        writer.writerows(rows)

    stats = parser_utils.process_csv(p, status_filter=None, dry_run=False)
    assert stats['changed_rows'] == 1
    # Backup file should exist
    backups = list(tmp_path.glob('*_backup_*.csv'))
    assert backups, 'Expected backup file to exist'
    # Verify file was updated (normalized)
    with p.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    assert data[0]['album'] == 'Album'

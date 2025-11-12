from pathlib import Path
import csv

from lib import parser_utils


def test_read_and_write_rows(tmp_path: Path):
    p = tmp_path / 'data.csv'
    rows = [
        {'artist': 'A', 'album': 'X', 'status': 's1'},
        {'artist': 'B', 'album': 'Y', 'status': 's2'},
    ]
    fieldnames = ['artist', 'album', 'status']
    # write initial file
    parser_utils.write_rows_to_csv(p, rows, fieldnames, make_backup=False)
    assert p.exists()

    read_rows, read_fields = parser_utils.read_csv_to_rows(p)
    assert read_fields == fieldnames
    assert len(read_rows) == 2

    # modify and write with backup
    read_rows[0]['status'] = 'done'
    parser_utils.write_rows_to_csv(p, read_rows, read_fields, make_backup=True)
    # backup exists
    backups = list(p.parent.glob('*_backup_*.csv'))
    assert backups
    # new file contains change
    r2, _ = parser_utils.read_csv_to_rows(p)
    assert r2[0]['status'] == 'done'

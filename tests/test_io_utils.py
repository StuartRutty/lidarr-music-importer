from pathlib import Path
import csv

import pytest

from lib.io_utils import create_backup, read_csv_to_rows, write_rows_to_csv
from lib import parser_utils


def test_create_backup_creates_file(tmp_path):
    p = tmp_path / "sample.csv"
    content = "col1,col2\n1,2\n"
    p.write_text(content, encoding='utf-8')

    backup_path = create_backup(p)

    assert backup_path.exists()
    assert "_backup_" in backup_path.name
    assert backup_path.read_text(encoding='utf-8') == content


def test_read_csv_to_rows_reads_header_and_rows(tmp_path):
    p = tmp_path / "input.csv"
    p.write_text("a,b\n1,2\n3,4\n", encoding='utf-8')

    rows, fieldnames = read_csv_to_rows(p)

    assert fieldnames == ["a", "b"]
    assert isinstance(rows, list)
    assert rows[0]["a"] == "1"


def test_write_rows_to_csv_writes_and_backups(tmp_path):
    dest = tmp_path / "out.csv"

    # create an existing file so the backup path will be created
    dest.write_text("x,y\nold,entry\n", encoding='utf-8')

    rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    fieldnames = ["a", "b"]

    write_rows_to_csv(dest, rows, fieldnames, make_backup=True)

    # verify new file written
    text = dest.read_text(encoding='utf-8')
    assert "a,b" in text
    assert "1,2" in text

    # backup file should exist in the same directory
    backups = [p for p in tmp_path.iterdir() if "_backup_" in p.name]
    assert len(backups) >= 1


def test_write_rows_to_csv_no_backup(tmp_path):
    dest = tmp_path / "no_backup.csv"
    rows = [{"a": "1"}]
    fieldnames = ["a"]

    write_rows_to_csv(dest, rows, fieldnames, make_backup=False)

    assert dest.exists()
    text = dest.read_text(encoding='utf-8')
    assert "a" in text


def test_read_csv_to_rows_empty_file(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding='utf-8')

    rows, fieldnames = read_csv_to_rows(p)
    assert rows == []
    assert fieldnames == []


def test_read_and_write_rows_via_parser_utils(tmp_path: Path):
    p = tmp_path / 'data.csv'
    rows = [
        {'artist': 'A', 'album': 'X', 'status': 's1'},
        {'artist': 'B', 'album': 'Y', 'status': 's2'},
    ]
    fieldnames = ['artist', 'album', 'status']
    parser_utils.write_rows_to_csv(p, rows, fieldnames, make_backup=False)
    assert p.exists()

    read_rows, read_fields = parser_utils.read_csv_to_rows(p)
    assert read_fields == fieldnames
    assert len(read_rows) == 2

    read_rows[0]['status'] = 'done'
    parser_utils.write_rows_to_csv(p, read_rows, read_fields, make_backup=True)
    backups = list(p.parent.glob('*_backup_*.csv'))
    assert backups
    r2, _ = parser_utils.read_csv_to_rows(p)
    assert r2[0]['status'] == 'done'

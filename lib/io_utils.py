"""General I/O utilities for CSV read/write and backups.

This module centralizes filesystem I/O helpers so other libs can import them
without pulling in parsing logic.
"""
from pathlib import Path
from datetime import datetime
import csv
import logging
from typing import List, Dict, Tuple


def create_backup(csv_file: Path) -> Path:
    """Create a timestamped backup of the original CSV file and return the backup path."""
    p = Path(csv_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{p.stem}_backup_{timestamp}{p.suffix}"
    backup_path = p.parent / backup_name
    backup_path.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
    logging.info(f"Created backup: {backup_path}")
    return backup_path


def read_csv_to_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    """Read a CSV file into a list of dict rows and return (rows, fieldnames).

    Uses UTF-8 encoding and returns a copy of fieldnames as a list.
    """
    p = Path(path)
    with p.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, list(fieldnames)


def write_rows_to_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str], make_backup: bool = True) -> None:
    """Write rows (list of dicts) to CSV at `path` with given fieldnames.

    If make_backup is True and the destination exists, a timestamped backup will
    be created using `create_backup`.
    """
    p = Path(path)
    if make_backup and p.exists():
        create_backup(p)
    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

import json
import os
import tempfile
import time
from pathlib import Path

JOBS_DIR = Path(__file__).resolve().parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _job_path(task_id: str) -> Path:
    return JOBS_DIR / f"{task_id}.json"


def _atomic_write(path: Path, data: dict):
    # Write to a temp file and replace to ensure atomicity
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as wf:
            json.dump(data, wf, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def create_job(task_id: str, data: dict):
    now = time.time()
    data = dict(data)  # copy
    data.setdefault('created_at', now)
    data['updated_at'] = now
    p = _job_path(task_id)
    _atomic_write(p, data)


def update_job(task_id: str, updates: dict):
    p = _job_path(task_id)
    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as rf:
                cur = json.load(rf)
        except Exception:
            cur = {}
    else:
        cur = {}
    cur.update(updates)
    cur['updated_at'] = time.time()
    _atomic_write(p, cur)


def get_job(task_id: str):
    p = _job_path(task_id)
    if not p.exists():
        return None
    try:
        with open(p, 'r', encoding='utf-8') as rf:
            return json.load(rf)
    except Exception:
        return None


def list_jobs():
    for f in JOBS_DIR.glob('*.json'):
        yield f.stem


def remove_job(task_id: str):
    p = _job_path(task_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def cleanup_jobs(max_age_seconds: int = 7 * 24 * 3600, status_filter=('completed',)):
    """Remove job files matching the given status that haven't been updated
    within `max_age_seconds` seconds.

    Args:
        max_age_seconds: age threshold in seconds (default 7 days).
        status_filter: iterable of job statuses to consider for removal.
    """
    now = time.time()
    for jid in list(list_jobs()):
        job = get_job(jid)
        if not job:
            continue
        status = job.get('status')
        if status not in status_filter:
            continue
        updated = job.get('updated_at') or job.get('created_at') or 0
        try:
            if (now - float(updated)) > float(max_age_seconds):
                remove_job(jid)
        except Exception:
            # Best-effort; ignore problematic entries
            continue

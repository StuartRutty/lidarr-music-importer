import time
from pathlib import Path


def test_job_store_cleanup_removes_old_completed_job():
    import webui.job_store as job_store
    repo_root = Path(__file__).resolve().parent.parent
    jobs_dir = repo_root / 'webui' / 'jobs'
    jobs_dir.mkdir(parents=True, exist_ok=True)

    task_id = f'cleanup-test-{int(time.time())}'
    job_data = {
        'status': 'completed',
        'total': 1,
        'processed': 1,
        'current': '',
        'out_name': 'dummy.csv',
        'error': None,
    }
    job_store.create_job(task_id, job_data)

    # Make the job appear old by setting updated_at in the past
    old_ts = time.time() - (3600 * 24 * 10)  # 10 days ago
    # update_job overwrites updated_at; write file directly to simulate old timestamp
    job_path = jobs_dir / f"{task_id}.json"
    job_json = job_store.get_job(task_id)
    job_json['updated_at'] = old_ts
    # write atomically via job_store internal helpers if available, else simple write
    try:
        from webui.job_store import _atomic_write
        _atomic_write(job_path, job_json)
    except Exception:
        with open(job_path, 'w', encoding='utf-8') as wf:
            import json
            json.dump(job_json, wf)

    # Run cleanup with threshold 7 days -> should remove
    job_store.cleanup_jobs(max_age_seconds=7 * 24 * 3600)

    assert job_store.get_job(task_id) is None

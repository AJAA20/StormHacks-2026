"""Background jobs for region builds (in-memory; fine for a single-server hackathon app).

One build runs at a time: builds are network- and CPU-heavy, and queueing keeps the
server responsive for routing requests.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable

from backend.regions import builder
from backend.regions.store import region_exists

log = logging.getLogger(__name__)

# A task reports progress and returns details for the UI, including "region_id".
Task = Callable[[builder.Progress], dict]


@dataclass
class Job:
    id: str
    name: str
    region_id: str | None = None
    status: str = "queued"  # queued | running | done | error
    stage: str = "Waiting to start"
    progress: float = 0.0
    error: str | None = None
    # Per-request facts for the UI (mode, requested vs. observation date, notes).
    details: dict | None = None
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        return asdict(self)


_jobs: dict[str, Job] = {}
_active: dict[str, Job] = {}  # dedupe key -> queued/running job
_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="region-build")


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def submit_task(key: str, name: str, task: Task) -> Job:
    """Run `task` in the background; identical requests in flight share one job."""
    with _lock:
        running = _active.get(key)
        if running and running.status in ("queued", "running"):
            return running
        job = Job(_new_id(), name)
        _jobs[job.id] = job
        _active[key] = job

    def progress(stage: str, frac: float) -> None:
        job.stage, job.progress = stage, round(frac, 2)

    def run() -> None:
        job.status = "running"
        try:
            details = task(progress)
            job.details, job.region_id = details, details["region_id"]
            job.status, job.stage, job.progress = "done", "Done", 1.0
        except builder.RegionBuildError as exc:
            job.status, job.error = "error", str(exc)
        except Exception as exc:  # network hiccups, OSM timeouts, ...
            log.exception("job %s (%s) failed", job.id, name)
            job.status, job.error = "error", f"Analysis failed unexpectedly ({type(exc).__name__}). Please try again."

    _executor.submit(run)
    return job


def submit(region_id: str, name: str, bbox, flood_dates: str, preflood_dates: str | None) -> Job:
    """Analyse a bbox over a date range (POST /api/analyze). Cached regions finish immediately."""
    if region_exists(region_id):
        job = Job(_new_id(), name, region_id, "done", "Loaded from cache", 1.0, details={"region_id": region_id})
        _jobs[job.id] = job
        return job

    def task(progress: builder.Progress) -> dict:
        builder.build_region(region_id, name, bbox, flood_dates, preflood_dates, progress=progress)
        return {"region_id": region_id}

    return submit_task(region_id, name, task)

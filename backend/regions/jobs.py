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

from backend.regions import builder
from backend.regions.store import region_exists
from backend.api.ws import broadcast

log = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    region_id: str
    name: str
    status: str = "queued"  # queued | running | done | error
    stage: str = "Waiting to start"
    progress: float = 0.0
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        return asdict(self)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="region-build")


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def submit(region_id: str, name: str, bbox, flood_dates: str, preflood_dates: str | None) -> Job:
    """Start (or reuse) a build. Cached regions return an already-finished job."""
    with _lock:
        if region_exists(region_id):
            job = Job(uuid.uuid4().hex[:12], region_id, name, "done", "Loaded from cache", 1.0)
            _jobs[job.id] = job
            return job
        for job in _jobs.values():  # same area already building -> share that job
            if job.region_id == region_id and job.status in ("queued", "running"):
                return job
        job = Job(uuid.uuid4().hex[:12], region_id, name)
        _jobs[job.id] = job

    def progress(stage: str, frac: float) -> None:
        job.stage, job.progress = stage, round(frac, 2)

    def run() -> None:
        job.status = "running"
        try:
            builder.build_region(region_id, name, bbox, flood_dates, preflood_dates, progress=progress)
            job.status, job.stage, job.progress = "done", "Done", 1.0
            broadcast({"type": "flood_update", "region_id": region_id, "job_id": job.id})
        except builder.RegionBuildError as exc:
            job.status, job.error = "error", str(exc)
        except Exception as exc:  # network hiccups, OSM timeouts, ...
            log.exception("region build %s failed", region_id)
            job.status, job.error = "error", f"Analysis failed unexpectedly ({type(exc).__name__}). Please try again."

    _executor.submit(run)
    return job

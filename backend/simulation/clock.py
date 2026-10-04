"""Simulated disaster clock: maps wall-clock time to a historical event timeline.

Lets the demo "play back" a real flood event (e.g. Nov 2021 Abbotsford flood)
as if it were happening live, compressing days into minutes. Swappable later
for a real live feed without touching callers (they just read `sim_now()`).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

# Real event window we have satellite data for (Abbotsford / Sumas Prairie flood).
EVENT_START = datetime(2021, 11, 14)
EVENT_END = datetime(2021, 11, 30)

# Playback speed: how many simulated days pass per real second.
# 1.0 => 1 simulated day per real second (full event in ~16s). Tune for demo pacing.
PLAYBACK_DAYS_PER_SEC = 1.0 / 20.0  # ~20s of real time per simulated day

_sim_start_wallclock = time.time()
_sim_epoch_start = EVENT_START


def sim_now() -> datetime:
    """Current point in the simulated timeline (clamped to the event window)."""
    elapsed_sec = time.time() - _sim_start_wallclock
    simulated = _sim_epoch_start + timedelta(days=elapsed_sec * PLAYBACK_DAYS_PER_SEC)
    return min(simulated, EVENT_END)


def sim_today() -> date:
    return sim_now().date()


def reset(start: datetime = EVENT_START) -> None:
    """Restart the simulated clock from a given point (e.g. for demo replay)."""
    global _sim_start_wallclock, _sim_epoch_start
    _sim_epoch_start = start
    _sim_start_wallclock = time.time()


def is_finished() -> bool:
    return sim_now() >= EVENT_END

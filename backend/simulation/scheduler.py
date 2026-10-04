"""Background scheduler: drives the simulated clock and pushes periodic ticks
so the frontend can show a live "satellite pass" timestamp and (optionally)
trigger re-analysis as simulated time advances.

This is intentionally decoupled from where the data comes from: swapping the
simulated clock for a real live feed later only means changing what triggers
`broadcast(...)` here, not the frontend or the rest of the backend.
"""
from __future__ import annotations

import logging
import threading
import time

from backend.simulation.clock import sim_now, is_finished
from backend.api.ws import broadcast

log = logging.getLogger(__name__)

TICK_INTERVAL_SEC = 5
_last_day_broadcast: str | None = None


def _tick() -> None:
    global _last_day_broadcast
    now = sim_now()
    day_str = now.strftime("%Y-%m-%d")

    # Always push a lightweight clock tick so the frontend badge stays live.
    broadcast({"type": "sim_clock", "sim_time": now.isoformat(), "finished": is_finished()})

    # Only announce a "new day" once per simulated day (cheap signal for UI to
    # highlight that fresher imagery would be available in a real deployment).
    if day_str != _last_day_broadcast:
        _last_day_broadcast = day_str
        log.info("Simulated clock advanced to %s", day_str)
        broadcast({"type": "sim_day_advanced", "sim_date": day_str})


def start_background_scheduler() -> None:
    def loop():
        while True:
            try:
                _tick()
            except Exception:
                log.exception("scheduler tick failed")
            time.sleep(TICK_INTERVAL_SEC)

    threading.Thread(target=loop, daemon=True, name="sim-clock-scheduler").start()

"""Turn the saved MNDWI rasters into one flood-polygon GeoJSON per UI scenario (low / moderate / severe).

Each scenario is the SAME satellite observation thresholded at a different MNDWI
value: a lower threshold also counts shallower / muddier water, so more area floods.
Runs offline from the outputs of scripts/analyze_flood.py.

    python scripts/build_flood_scenarios.py
    python scripts/build_flood_scenarios.py --scenario low=0.3 --scenario severe=-0.05

Writes backend/data/regions/abbotsford-2021/flood/<scenario>.geojson (small, committed, read by the routing API).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.satellite.scenarios import SCENARIO_THRESHOLDS, build_flood_scenarios  # noqa: E402

DEFAULT_SCENARIOS = SCENARIO_THRESHOLDS


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mndwi", default="data/processed/mndwi.tif")
    p.add_argument("--preflood", default="data/processed/mndwi_preflood.tif")
    p.add_argument("--out-dir", default="backend/data/regions/abbotsford-2021/flood")
    p.add_argument("--work-dir", default="data/processed/scenarios")
    p.add_argument("--scenario", action="append", metavar="NAME=THRESHOLD",
                   help=f"Override scenarios (repeatable). Default: {DEFAULT_SCENARIOS}")
    p.add_argument("--min-area", type=float, default=5000.0)
    a = p.parse_args()

    scenarios = dict(DEFAULT_SCENARIOS)
    if a.scenario:
        scenarios = {k: float(v) for k, v in (s.split("=") for s in a.scenario)}

    if not Path(a.preflood).exists():
        print(f"WARNING: {a.preflood} not found - permanent rivers/lakes will count as flooded")
    stats = build_flood_scenarios(a.mndwi, a.out_dir, a.work_dir, a.preflood, scenarios, a.min_area)
    for name, st in stats.items():
        print(f"{name:9s} MNDWI > {st['threshold']:+.2f}: {st['polygons']:4d} polygons, "
              f"{st['area_km2']:6.2f} km^2 -> {st['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

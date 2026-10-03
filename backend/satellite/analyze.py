"""One call for "analyse this flood": search -> pick clearest scenes -> download -> MNDWI -> polygons.

This is the function the FastAPI backend (Person 4) can call when a user asks for a
new area/date. It is network-bound (~10-60 s), so the API should run it as a background
job and the demo should use a pre-computed (cached) result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.satellite.pipeline import generate_flood_mask
from backend.satellite.stac import BBox, DownloadedScene, SceneCandidate, download_scene, find_best_scene


@dataclass
class FloodAnalysis:
    bbox: BBox
    flood_scene: DownloadedScene
    preflood_scene: DownloadedScene | None
    flood_ranking: list[SceneCandidate]
    preflood_ranking: list[SceneCandidate]
    mask_path: Path
    mndwi_path: Path
    geojson_path: Path | None
    stats: dict = field(default_factory=dict)
    polygon_count: int = 0
    result: dict = field(default_factory=dict, repr=False)  # raw arrays, e.g. for previews


def analyze_flood_event(
    bbox: BBox,
    flood_dates: str,
    preflood_dates: str | None = None,
    threshold: float = 0.0,
    out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/raw/stac",
    min_clear_pct: float = 50.0,
    vectorize: bool = True,
    min_area: float = 5000.0,  # real imagery is noisy; 5000 m^2 = 50 pixels
    simplify: float = 5.0,
) -> FloodAnalysis:
    out_dir = Path(out_dir)

    flood_item, flood_rank = find_best_scene(bbox, flood_dates, min_clear_pct)
    flood = download_scene(flood_item, bbox, cache_dir)

    pre, pre_rank = None, []
    if preflood_dates:
        pre_item, pre_rank = find_best_scene(bbox, preflood_dates, min_clear_pct)
        pre = download_scene(pre_item, bbox, cache_dir)

    result = generate_flood_mask(
        flood.green, flood.swir,
        out_mask=out_dir / "flood_mask.tif", out_mndwi=out_dir / "mndwi.tif",
        out_preflood_mndwi=out_dir / "mndwi_preflood.tif",
        threshold=threshold, scl_path=flood.scl, bbox=bbox, boa_offset=flood.boa_offset,
        pre_green_path=pre.green if pre else None, pre_swir_path=pre.swir if pre else None,
        pre_scl_path=pre.scl if pre else None, pre_boa_offset=pre.boa_offset if pre else 0.0,
    )

    analysis = FloodAnalysis(
        bbox=bbox, flood_scene=flood, preflood_scene=pre,
        flood_ranking=flood_rank, preflood_ranking=pre_rank,
        mask_path=result["out_mask"], mndwi_path=result["out_mndwi"], geojson_path=None,
        stats=result["stats"], result=result,
    )

    if vectorize:  # hand straight to Person 2's module
        from backend.gis import export_geojson, vectorize_flood_mask

        gdf = vectorize_flood_mask(analysis.mask_path, min_area=min_area, merge=True,
                                   merge_gap=10, simplify_tolerance=simplify)
        analysis.geojson_path = export_geojson(gdf, out_dir / "flood_polygons.geojson")
        analysis.polygon_count = len(gdf)
    return analysis

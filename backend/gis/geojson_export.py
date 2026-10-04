"""Write flood polygons as an EPSG:4326 GeoJSON FeatureCollection, and check the result."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import shapely

from backend.gis.crs_utils import WGS84, ensure_crs

COORD_DECIMALS = 7  # ~1 cm at the equator; plenty for 10 m pixels


def export_geojson(
    gdf: gpd.GeoDataFrame, output_path: str | Path, source: str = "satellite"
) -> Path:
    """Reproject to EPSG:4326 and write a FeatureCollection.

    Each feature gets: {"flooded": true, "source": <source>, "area_m2": <float>}.
    area_m2 must already exist (computed in a metric CRS by vectorize_flood_mask);
    it is NOT recomputed here because area in degrees would be wrong.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    out = ensure_crs(gdf, WGS84)
    props = gpd.GeoDataFrame(
        {
            "flooded": True,
            "source": source,
            "area_m2": out["area_m2"] if "area_m2" in out else None,
        },
        geometry=out.geometry,
        crs=WGS84,
    )

    # RFC 7946 is the current GeoJSON standard: always lon/lat WGS84,
    # counter-clockwise outer rings, no legacy "crs" member.
    props["geometry"] = shapely.orient_polygons(
        shapely.set_precision(props.geometry.values, 10**-COORD_DECIMALS)
    )
    fc = json.loads(props.to_json(drop_id=True))
    with open(output_path, "w") as f:
        json.dump(fc, f)
    return output_path


def validate_geojson_file(path: str | Path) -> dict:
    """Re-read the written file and check what Person 3 relies on.

    Returns a dict of stats; raises ValueError on a hard failure.
    """
    path = Path(path)
    with open(path) as f:
        fc = json.load(f)
    if fc.get("type") != "FeatureCollection":
        raise ValueError(f"{path}: top-level type is {fc.get('type')!r}, expected FeatureCollection")

    gdf = gpd.read_file(path)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError(f"{path}: CRS is {gdf.crs}, expected EPSG:4326")

    bad_types = set(gdf.geom_type) - {"Polygon", "MultiPolygon"}
    if bad_types:
        raise ValueError(f"{path}: unexpected geometry types {bad_types}")

    stats = {
        "path": str(path),
        "features": len(gdf),
        "crs": "EPSG:4326",
        "all_valid": bool(gdf.geometry.is_valid.all()) if len(gdf) else True,
        "bounds_lonlat": None,
        "total_area_m2": float(gdf["area_m2"].sum()) if "area_m2" in gdf and len(gdf) else 0.0,
    }
    if len(gdf):
        minx, miny, maxx, maxy = gdf.total_bounds
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
            raise ValueError(
                f"{path}: bounds {gdf.total_bounds} are not valid lon/lat - "
                "coordinates were probably never reprojected from metres."
            )
        stats["bounds_lonlat"] = [round(float(v), 5) for v in (minx, miny, maxx, maxy)]
    return stats

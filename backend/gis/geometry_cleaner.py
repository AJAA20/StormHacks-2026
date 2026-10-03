"""Geometry cleanup: repair, merge, filter, simplify.

Every function takes and returns a GeoDataFrame with one Polygon per row,
so steps can be chained in any order and re-run safely.
"""

from __future__ import annotations

import geopandas as gpd
import shapely

from backend.gis.crs_utils import require_crs


def _polygon_rows(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Explode multi-part / collection geometries and keep only non-empty Polygons."""
    exploded = gdf.explode(index_parts=False)
    keep = (exploded.geom_type == "Polygon") & ~exploded.geometry.is_empty
    return exploded[keep].reset_index(drop=True)


def clean_flood_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Repair invalid geometries and normalise to one valid Polygon per row.

    Uses shapely.make_valid rather than buffer(0):
      * make_valid keeps all of the original area; it splits self-touching
        shapes into valid pieces. It may return a GeometryCollection that also
        contains stray lines/points, which we drop below.
      * buffer(0) is the old trick. It usually works, but on some
        self-intersecting "bow-tie" shapes it silently throws away half the
        polygon - not what you want for flood extents.
    """
    require_crs(gdf)
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return gdf.reset_index(drop=True)
    gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
    return _polygon_rows(gdf)


def merge_flood_polygons(gdf: gpd.GeoDataFrame, gap: float = 0.0) -> gpd.GeoDataFrame:
    """Dissolve polygons that overlap, share an edge, or are within `gap` of each other.

    Why `gap` matters: polygons traced from one raster never overlap, and
    patches touching only at a corner can't form one valid Polygon. So a plain
    union rarely changes raster output. With gap > 0 we do a morphological
    "closing" (grow by gap/2, union, shrink by gap/2), which joins flood patches
    separated by a dry strip narrower than `gap` (e.g. gap=10 bridges a
    1-pixel gap at 10 m resolution) without growing their outer edges.
    `gap` is in CRS units, so use a metric CRS. Attribute columns are dropped.
    """
    crs = require_crs(gdf)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gap and crs.is_geographic:
        raise ValueError("merge gap needs a projected CRS (gap in metres).")
    geoms = gdf.geometry.values
    if gap:
        half = gap / 2
        merged = shapely.union_all(shapely.buffer(geoms, half))
        merged = shapely.buffer(merged, -half)
    else:
        merged = shapely.union_all(geoms)
    out = gpd.GeoDataFrame(geometry=[merged], crs=crs)
    return clean_flood_geometries(out)


def filter_small_polygons(gdf: gpd.GeoDataFrame, min_area: float | None) -> gpd.GeoDataFrame:
    """Drop polygons smaller than `min_area`, in the CRS's units squared.

    Must be called on a projected CRS (metres -> m^2). In EPSG:4326, .area
    would return "square degrees", which is meaningless as a physical size.
    """
    crs = require_crs(gdf)
    if not min_area:
        return gdf
    if crs.is_geographic:
        raise ValueError(
            "filter_small_polygons() needs a projected CRS; area in degrees is meaningless. "
            "Reproject first (see choose_processing_crs)."
        )
    return gdf[gdf.geometry.area >= min_area].reset_index(drop=True)


def simplify_flood_polygons(gdf: gpd.GeoDataFrame, tolerance: float | None) -> gpd.GeoDataFrame:
    """Reduce vertex count with Douglas-Peucker.

    `tolerance` is a distance in the CRS's units: the simplified edge may move
    up to that far from the original. In a metre CRS, a good value is about
    half a pixel (5 m for 10 m Sentinel-2 pixels) - it removes the "staircase"
    pixel edges without visibly changing the flood extent.
    (In EPSG:4326, 1 degree of longitude is ~111 km at the equator but ~73 km
    in BC, so one degree value means different distances in different places.
    That is why we simplify before converting to 4326.)

    preserve_topology=True prevents a polygon from collapsing or crossing
    itself; we still re-run cleaning afterwards to be safe.
    """
    crs = require_crs(gdf)
    if not tolerance:
        return gdf
    if crs.is_geographic:
        raise ValueError("simplify_flood_polygons() needs a projected CRS (tolerance in metres).")
    out = gdf.copy()
    out["geometry"] = out.geometry.simplify(tolerance, preserve_topology=True)
    return clean_flood_geometries(out)

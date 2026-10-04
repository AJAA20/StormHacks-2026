"""CRS helpers.

Rule of thumb for this module:
  * Measure (area, simplify tolerance) in a PROJECTED CRS whose unit is metres.
  * Exchange data with the rest of the team in EPSG:4326 ([lon, lat]).
  * Never guess a missing CRS - fail loudly instead.
"""

from __future__ import annotations

import warnings

import geopandas as gpd
from pyproj import CRS

WGS84 = "EPSG:4326"


class MissingCRSError(ValueError):
    """Raised when data has no CRS, so we cannot know where it is on Earth."""


def require_crs(gdf: gpd.GeoDataFrame, what: str = "GeoDataFrame") -> CRS:
    """Return the CRS of `gdf`, or raise if it has none."""
    if gdf.crs is None:
        raise MissingCRSError(
            f"{what} has no CRS. Refusing to guess. Fix the source file "
            "(e.g. ask Person 1 to write the CRS into flood_mask.tif) or call "
            "gdf.set_crs(...) yourself if you are certain what it should be."
        )
    return CRS.from_user_input(gdf.crs)


def ensure_crs(gdf: gpd.GeoDataFrame, target_crs: str | CRS = WGS84) -> gpd.GeoDataFrame:
    """Reproject `gdf` to `target_crs` (no-op if it is already there).

    This *transforms* coordinates (to_crs), it never just relabels them (set_crs).
    """
    source = require_crs(gdf)
    target = CRS.from_user_input(target_crs)
    if source.equals(target):
        return gdf
    return gdf.to_crs(target)


def is_metric_projected(crs: CRS | str) -> bool:
    """True if `crs` is projected and its x axis is in metres."""
    crs = CRS.from_user_input(crs)
    if not crs.is_projected:
        return False
    unit = crs.axis_info[0].unit_name.lower() if crs.axis_info else ""
    return unit in ("metre", "meter")


def choose_processing_crs(
    gdf: gpd.GeoDataFrame, processing_crs: str | CRS | None = None
) -> CRS:
    """Pick the CRS used for area filtering and simplification.

    Priority:
      1. `processing_crs` if the caller gave one (e.g. "EPSG:32610").
      2. The data's own CRS, if it is already projected in metres
         (Sentinel-2 rasters are delivered in UTM, so this is the usual case).
      3. Otherwise (e.g. source is EPSG:4326 degrees), the local UTM zone
         estimated from the data's location.
    """
    source = require_crs(gdf)

    if processing_crs is not None:
        crs = CRS.from_user_input(processing_crs)
        if crs.is_geographic:
            raise ValueError(
                f"processing_crs {crs.to_string()} is geographic (degrees). "
                "Use a projected CRS in metres, e.g. the local UTM zone."
            )
        if not is_metric_projected(crs):
            warnings.warn(
                f"processing_crs {crs.to_string()} is not in metres; "
                "--min-area and --simplify will be interpreted in its units."
            )
        return crs

    if is_metric_projected(source):
        return source

    if gdf.empty:
        raise ValueError(
            "Cannot estimate a UTM zone for empty data in a geographic CRS. "
            "Pass processing_crs explicitly."
        )
    return CRS.from_user_input(gdf.estimate_utm_crs())


def describe_crs(crs: CRS | str | None) -> str:
    """Short human-readable CRS label, e.g. 'EPSG:32610 (WGS 84 / UTM zone 10N, metre)'."""
    if crs is None:
        return "None (MISSING!)"
    crs = CRS.from_user_input(crs)
    epsg = crs.to_epsg()
    code = f"EPSG:{epsg}" if epsg else "custom"
    unit = crs.axis_info[0].unit_name if crs.axis_info else "?"
    return f"{code} ({crs.name}, {unit})"

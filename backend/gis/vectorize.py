"""Read a binary flood raster and turn flooded pixels into polygons."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.features import shapes
from shapely.geometry import shape

from backend.gis.crs_utils import MissingCRSError, choose_processing_crs
from backend.gis.geometry_cleaner import (
    clean_flood_geometries,
    filter_small_polygons,
    merge_flood_polygons,
    simplify_flood_polygons,
)


@dataclass
class FloodMask:
    """A flood raster in memory: which pixels are flooded, and where they are on Earth."""

    flooded: np.ndarray  # bool (rows, cols): True = flooded
    valid: np.ndarray  # bool (rows, cols): False = nodata / NaN
    transform: Affine  # pixel (col, row) -> CRS (x, y)
    crs: CRS
    width: int
    height: int
    nodata: float | None

    @property
    def pixel_size(self) -> tuple[float, float]:
        return abs(self.transform.a), abs(self.transform.e)

    def summary(self) -> str:
        px_w, px_h = self.pixel_size
        n_valid = int(self.valid.sum())
        n_flood = int(self.flooded.sum())
        pct = 100 * n_flood / n_valid if n_valid else 0.0
        return (
            f"  size        : {self.width} x {self.height} px\n"
            f"  pixel size  : {px_w:g} x {px_h:g} (CRS units)\n"
            f"  CRS         : {self.crs.to_string()}\n"
            f"  transform   : {tuple(round(v, 6) for v in self.transform[:6])}\n"
            f"  nodata      : {self.nodata}\n"
            f"  valid px    : {n_valid}  (nodata px: {self.valid.size - n_valid})\n"
            f"  flooded px  : {n_flood}  ({pct:.1f}% of valid)"
        )


def load_flood_mask(path: str | Path, flood_value: int = 1) -> FloodMask:
    """Open a single-band flood raster.

    A pixel counts as flooded only if it is valid data AND equals `flood_value`.
    Nodata pixels and NaNs are never flooded, so a nodata border or a cloud
    mask from Person 1 can't turn into fake flood polygons.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Flood raster not found: {path}")

    with rasterio.open(path) as src:
        if src.crs is None:
            raise MissingCRSError(
                f"{path} has no CRS. Ask Person 1 to write it with crs=... "
                "(the Sentinel-2 band's CRS)."
            )
        if src.transform == Affine.identity():
            raise ValueError(
                f"{path} has an identity transform, i.e. no georeferencing. "
                "Ask Person 1 to write it with transform=<the band's transform>."
            )
        data = src.read(1, masked=True)  # masks pixels equal to src.nodata
        valid = ~np.ma.getmaskarray(data)
        values = data.filled(0)
        if np.issubdtype(values.dtype, np.floating):
            valid &= np.isfinite(values)
            values = np.nan_to_num(values, nan=0.0)

        return FloodMask(
            flooded=valid & (values == flood_value),
            valid=valid,
            transform=src.transform,
            crs=CRS.from_user_input(src.crs),
            width=src.width,
            height=src.height,
            nodata=src.nodata,
        )


def polygons_from_mask(mask: FloodMask) -> gpd.GeoDataFrame:
    """Trace connected flooded pixels into polygons, in the raster's own CRS.

    rasterio.features.shapes walks the pixel grid and returns polygon outlines
    in pixel (col, row) space; passing `transform` makes it convert every
    vertex to real CRS coordinates. `mask=` restricts output to flooded pixels.
    """
    image = mask.flooded.astype(np.uint8)
    geoms = [
        shape(geom)
        for geom, value in shapes(image, mask=mask.flooded, transform=mask.transform, connectivity=4)
        if value == 1
    ]
    return gpd.GeoDataFrame(geometry=geoms, crs=mask.crs)


def vectorize_flood_mask(
    raster_path: str | Path,
    min_area: float | None = None,
    processing_crs: str | CRS | None = None,
    merge: bool = False,
    merge_gap: float = 0.0,
    simplify_tolerance: float | None = None,
    flood_value: int = 1,
) -> gpd.GeoDataFrame:
    """Full Person 2 pipeline, raster -> clean polygons.

    Returns polygons in the *processing* CRS (metres) with an `area_m2` column.
    Use export_geojson() to write them out as EPSG:4326.

    min_area, merge_gap and simplify_tolerance are in processing-CRS units (m^2, m, m).
    """
    mask = load_flood_mask(raster_path, flood_value=flood_value)
    gdf = polygons_from_mask(mask)

    target = choose_processing_crs(gdf, processing_crs)
    gdf = gdf.to_crs(target)

    gdf = clean_flood_geometries(gdf)
    if merge:
        gdf = merge_flood_polygons(gdf, gap=merge_gap)  # before filtering, so pieces can combine
    gdf = filter_small_polygons(gdf, min_area)
    gdf = simplify_flood_polygons(gdf, simplify_tolerance)

    gdf["area_m2"] = gdf.geometry.area.round(1)
    return gdf

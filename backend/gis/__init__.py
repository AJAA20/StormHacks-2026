"""Person 2: flood raster -> clean EPSG:4326 flood polygons (GeoJSON)."""

from backend.gis.crs_utils import choose_processing_crs, ensure_crs, require_crs
from backend.gis.geojson_export import export_geojson, validate_geojson_file
from backend.gis.geometry_cleaner import (
    clean_flood_geometries,
    filter_small_polygons,
    merge_flood_polygons,
    simplify_flood_polygons,
)
from backend.gis.vectorize import (
    FloodMask,
    load_flood_mask,
    polygons_from_mask,
    vectorize_flood_mask,
)

__all__ = [
    "FloodMask",
    "choose_processing_crs",
    "clean_flood_geometries",
    "ensure_crs",
    "export_geojson",
    "filter_small_polygons",
    "load_flood_mask",
    "merge_flood_polygons",
    "polygons_from_mask",
    "require_crs",
    "simplify_flood_polygons",
    "validate_geojson_file",
    "vectorize_flood_mask",
]

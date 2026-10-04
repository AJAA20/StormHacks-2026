"""Small tests for Person 2's GIS module. Run: pytest -q"""

import importlib.util
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from backend.gis import (
    clean_flood_geometries,
    ensure_crs,
    export_geojson,
    filter_small_polygons,
    load_flood_mask,
    merge_flood_polygons,
    validate_geojson_file,
    vectorize_flood_mask,
)
from backend.gis.crs_utils import MissingCRSError

ROOT = Path(__file__).resolve().parents[1]
UTM10N = "EPSG:32610"


def write_raster(path, array, crs=UTM10N, transform=None, nodata=255):
    """Write a tiny single-band raster. Default: 10 m pixels near Abbotsford, BC."""
    transform = transform or from_origin(554_000, 5_436_000, 10, 10)
    with rasterio.open(
        path, "w", driver="GTiff", width=array.shape[1], height=array.shape[0], count=1,
        dtype=array.dtype, crs=crs, transform=transform, nodata=nodata,
    ) as dst:
        dst.write(array, 1)
    return path


@pytest.fixture
def simple_raster(tmp_path):
    """20x20 raster: one 5x5 block (2500 m^2), one single pixel (100 m^2), nodata column."""
    a = np.zeros((20, 20), dtype=np.uint8)
    a[2:7, 2:7] = 1
    a[15, 15] = 1
    a[:, 19] = 255
    return write_raster(tmp_path / "simple.tif", a)


# 1. mock raster can be loaded
def test_mock_raster_can_be_loaded(tmp_path):
    spec = importlib.util.spec_from_file_location("mock", ROOT / "scripts/create_mock_flood_raster.py")
    mock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock)
    path = mock.create_mock_flood_raster(tmp_path / "mock.tif")

    m = load_flood_mask(path)
    assert m.crs.to_epsg() == 32610
    assert (m.width, m.height) == (400, 300)
    assert m.flooded.any()
    assert not m.flooded[:, -20:].any(), "nodata strip must never count as flooded"


# 2. flooded pixels become polygons
def test_flooded_pixels_become_polygons(simple_raster):
    gdf = vectorize_flood_mask(simple_raster)
    assert len(gdf) == 2
    assert sorted(gdf["area_m2"]) == [100.0, 2500.0]


# 3. non-flooded pixels do not become polygons
def test_dry_raster_gives_no_polygons(tmp_path):
    path = write_raster(tmp_path / "dry.tif", np.zeros((10, 10), dtype=np.uint8))
    assert len(vectorize_flood_mask(path)) == 0


def test_nodata_is_not_flooded(tmp_path):
    a = np.full((10, 10), 255, dtype=np.uint8)  # all nodata
    path = write_raster(tmp_path / "nodata.tif", a, nodata=255)
    assert not load_flood_mask(path, flood_value=255).flooded.any()


# 4. small polygons can be filtered
def test_min_area_filters_small_polygons(simple_raster):
    gdf = vectorize_flood_mask(simple_raster, min_area=1000)
    assert len(gdf) == 1
    assert gdf["area_m2"].iloc[0] == 2500.0


def test_area_filter_refuses_degrees():
    gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy([0], [0]).buffer(1), crs="EPSG:4326")
    with pytest.raises(ValueError):
        filter_small_polygons(gdf, 100)


# 5. output GeoDataFrame has a CRS
def test_output_has_crs(simple_raster):
    gdf = vectorize_flood_mask(simple_raster)
    assert gdf.crs is not None and gdf.crs.is_projected


def test_missing_crs_raises(tmp_path):
    path = write_raster(tmp_path / "nocrs.tif", np.ones((5, 5), dtype=np.uint8), crs=None)
    with pytest.raises(MissingCRSError):
        load_flood_mask(path)


def test_geographic_raster_auto_picks_utm(tmp_path):
    a = np.zeros((10, 10), dtype=np.uint8)
    a[2:8, 2:8] = 1
    # ~0.0001 deg pixels near Abbotsford, in EPSG:4326
    path = write_raster(tmp_path / "geo.tif", a, crs="EPSG:4326",
                        transform=from_origin(-122.25, 49.06, 0.0001, 0.0001))
    gdf = vectorize_flood_mask(path)
    assert gdf.crs.to_epsg() == 32610  # estimated UTM zone 10N
    assert 200_000 > gdf["area_m2"].iloc[0] > 100  # metres^2, not degrees^2


# 6. output can be converted to EPSG:4326
def test_convert_to_wgs84(simple_raster):
    gdf = ensure_crs(vectorize_flood_mask(simple_raster), "EPSG:4326")
    assert gdf.crs.to_epsg() == 4326
    minx, miny, maxx, maxy = gdf.total_bounds
    # Abbotsford is around lon -122.2, lat 49.0  ->  x is longitude, y is latitude
    assert -123 < minx < maxx < -122
    assert 48.9 < miny < maxy < 49.2


# 7. GeoJSON file is successfully written
def test_geojson_written(simple_raster, tmp_path):
    out = export_geojson(vectorize_flood_mask(simple_raster), tmp_path / "out" / "flood.geojson")
    fc = json.loads(out.read_text())
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    props = fc["features"][0]["properties"]
    assert props["flooded"] is True and props["source"] == "satellite"
    lon, lat = fc["features"][0]["geometry"]["coordinates"][0][0]
    assert -123 < lon < -122 and 48.9 < lat < 49.2  # [lon, lat] order
    assert validate_geojson_file(out)["all_valid"]


# 8. output geometries are valid
def test_invalid_geometry_is_repaired():
    from shapely.geometry import Polygon

    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])  # self-intersecting
    assert not bowtie.is_valid
    gdf = clean_flood_geometries(gpd.GeoDataFrame(geometry=[bowtie], crs=UTM10N))
    assert gdf.geometry.is_valid.all()
    assert gdf.area.sum() == pytest.approx(50.0)  # both triangles kept


def test_merge_joins_diagonal_patches(tmp_path):
    a = np.zeros((10, 10), dtype=np.uint8)
    a[0:3, 0:3] = 1
    a[3:6, 3:6] = 1  # touches the first block only at a corner
    a[0:2, 8:10] = 1  # separate block
    gdf = vectorize_flood_mask(write_raster(tmp_path / "m.tif", a))
    assert len(gdf) == 3
    # gap=0: corner contact can't make one valid Polygon -> still 3 pieces
    assert len(merge_flood_polygons(gdf)) == 3
    # gap=10 m (one pixel): the diagonal pair joins, the far block stays separate
    merged = merge_flood_polygons(gdf, gap=10)
    assert len(merged) == 2
    assert merged.geometry.is_valid.all()


def test_full_pipeline_on_mock_is_valid(tmp_path):
    spec = importlib.util.spec_from_file_location("mock", ROOT / "scripts/create_mock_flood_raster.py")
    mock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock)
    path = mock.create_mock_flood_raster(tmp_path / "mock.tif")

    gdf = vectorize_flood_mask(path, min_area=1000, merge=True, merge_gap=10, simplify_tolerance=5)
    assert len(gdf) > 0
    assert gdf.geometry.is_valid.all()
    assert set(gdf.geom_type) == {"Polygon"}

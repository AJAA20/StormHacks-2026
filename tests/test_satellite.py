"""Tests for Person 1's satellite module, plus the Person 1 -> Person 2 integration. Run: pytest -q"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from backend.satellite import (
    build_flood_mask,
    cloud_mask_from_scl,
    compute_mndwi,
    load_bands_on_grid,
    reference_grid,
    threshold_mndwi,
    to_reflectance,
)
from backend.satellite.bands import boa_offset_from_name
from backend.satellite.pipeline import generate_flood_mask

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mock_bands(tmp_path_factory):
    root = tmp_path_factory.mktemp("sentinel")
    return load_script("create_mock_sentinel_bands").create_mock_sentinel_bands(root)


# --- MNDWI maths -------------------------------------------------------------

def test_mndwi_water_positive_land_negative():
    green = np.array([0.10, 0.08])
    swir = np.array([0.015, 0.20])
    m = compute_mndwi(green, swir)
    assert m[0] > 0.7  # water
    assert m[1] < -0.4  # land


def test_mndwi_division_by_zero_is_nan_without_warning():
    with np.errstate(all="raise"):  # any divide warning would raise here
        m = compute_mndwi(np.array([0.0, np.nan]), np.array([0.0, 0.1]))
    assert np.isnan(m).all()


def test_mndwi_range_and_shape_check():
    rng = np.random.default_rng(0)
    m = compute_mndwi(rng.uniform(-0.05, 1, 1000), rng.uniform(-0.05, 1, 1000))
    assert np.nanmin(m) >= -1 and np.nanmax(m) <= 1
    with pytest.raises(ValueError):
        compute_mndwi(np.zeros((2, 2)), np.zeros((4, 4)))


def test_reflectance_offset_and_nodata():
    r = to_reflectance(np.array([0, 1000, 3000], dtype=np.uint16), boa_offset=-1000)
    assert np.isnan(r[0])  # 0 DN = nodata
    assert r[1] == pytest.approx(0.0) and r[2] == pytest.approx(0.2)
    assert boa_offset_from_name("S2B_MSIL2A_20230520T190919_N0509_R056_T10UEV.SAFE") == -1000
    assert boa_offset_from_name("S2A_MSIL2A_20211121T191621_N0301_R056_T10UEV.SAFE") == 0


# --- thresholding & masks ----------------------------------------------------

def test_threshold_is_adjustable():
    m = np.array([-0.3, 0.05, 0.4, np.nan])
    assert threshold_mndwi(m, 0.0).tolist() == [False, True, True, False]
    assert threshold_mndwi(m, 0.2).tolist() == [False, False, True, False]


def test_scl_cloud_mask():
    scl = np.array([4, 6, 8, 9, 10, 3, 0, 11, np.nan])
    assert cloud_mask_from_scl(scl).tolist() == [False, False, True, True, True, True, True, True, True]


def test_cloud_buffer_grows_mask():
    scl = np.full((7, 7), 4.0)
    scl[3, 3] = 9  # one cloud pixel
    assert cloud_mask_from_scl(scl).sum() == 1
    assert cloud_mask_from_scl(scl, buffer_px=1).sum() == 9  # 3x3 block


def test_build_flood_mask_codes_and_change_detection():
    flood = np.array([0.5, 0.5, -0.5, np.nan, 0.5])
    before = np.array([0.6, -0.4, -0.4, -0.4, np.nan])  # pixel 0 = permanent river
    invalid = np.array([False, False, False, False, True])  # pixel 4 = cloud
    mask = build_flood_mask(flood, 0.0, invalid=invalid, preflood_mndwi=before)
    assert mask.tolist() == [0, 1, 0, 255, 255]
    assert mask.dtype == np.uint8


# --- alignment / georeferencing ----------------------------------------------

def test_bands_aligned_to_10m_grid_after_crop(mock_bands):
    p = mock_bands["flood"]
    grid = reference_grid(p["green"], (-122.26, 49.045, -122.20, 49.08))
    bands = load_bands_on_grid(p["green"], p["swir"], grid, p["scl"])
    assert abs(grid.transform.a) == 10.0
    assert {b.shape for b in bands.values()} == {grid.shape}  # 20 m bands now 10 m, same shape
    with rasterio.open(p["green"]) as src:
        assert grid.width < src.width and grid.height < src.height  # actually cropped


def test_output_preserves_crs_and_transform(mock_bands, tmp_path):
    p = mock_bands["flood"]
    r = generate_flood_mask(p["green"], p["swir"], out_mask=tmp_path / "m.tif", scl_path=p["scl"], out_mndwi=None)
    with rasterio.open(p["green"]) as src_in, rasterio.open(r["out_mask"]) as out:
        assert out.crs == src_in.crs
        assert out.transform == src_in.transform  # no bbox -> identical grid
        assert (out.width, out.height) == (src_in.width, src_in.height)
        assert out.nodata == 255 and out.dtypes[0] == "uint8"
        assert set(np.unique(out.read(1))) <= {0, 1, 255}


def test_cloud_pixels_are_not_flooded(mock_bands, tmp_path):
    p = mock_bands["flood"]
    without_scl = generate_flood_mask(p["green"], p["swir"], out_mask=tmp_path / "a.tif", out_mndwi=None)
    with_scl = generate_flood_mask(p["green"], p["swir"], out_mask=tmp_path / "b.tif", scl_path=p["scl"], out_mndwi=None)
    # The mock cloud has MNDWI ~ +0.07, so without SCL it is wrongly "flooded".
    assert with_scl["stats"]["flooded_pixels"] < without_scl["stats"]["flooded_pixels"]
    assert with_scl["stats"]["invalid_pixels"] > without_scl["stats"]["invalid_pixels"]


def test_preflood_removes_permanent_river(mock_bands, tmp_path):
    f, pre = mock_bands["flood"], mock_bands["preflood"]
    a = generate_flood_mask(f["green"], f["swir"], out_mask=tmp_path / "a.tif", scl_path=f["scl"], out_mndwi=None)
    b = generate_flood_mask(
        f["green"], f["swir"], out_mask=tmp_path / "b.tif", scl_path=f["scl"], out_mndwi=None,
        pre_green_path=pre["green"], pre_swir_path=pre["swir"], pre_scl_path=pre["scl"],
    )
    assert 0 < b["stats"]["flooded_pixels"] < a["stats"]["flooded_pixels"]


def test_rejects_raster_without_crs(tmp_path):
    path = tmp_path / "nocrs.tif"
    with rasterio.open(path, "w", driver="GTiff", width=4, height=4, count=1, dtype="uint16",
                       transform=from_origin(0, 4, 1, 1)) as dst:
        dst.write(np.ones((4, 4), dtype=np.uint16), 1)
    with pytest.raises(ValueError, match="no CRS"):
        reference_grid(path, None)


# --- Person 1 -> Person 2 integration ----------------------------------------

def test_end_to_end_satellite_to_geojson(mock_bands, tmp_path):
    from backend.gis import export_geojson, validate_geojson_file, vectorize_flood_mask

    f, pre = mock_bands["flood"], mock_bands["preflood"]
    r = generate_flood_mask(
        f["green"], f["swir"], out_mask=tmp_path / "flood_mask.tif", scl_path=f["scl"],
        pre_green_path=pre["green"], pre_swir_path=pre["swir"], pre_scl_path=pre["scl"],
        bbox=(-122.26, 49.045, -122.20, 49.08), out_mndwi=None,
    )
    gdf = vectorize_flood_mask(r["out_mask"], min_area=1000, merge=True, merge_gap=10, simplify_tolerance=5)
    assert 1 <= len(gdf) <= 5  # lake + field, not hundreds of noise specks
    assert gdf.geometry.is_valid.all()

    out = export_geojson(gdf, tmp_path / "flood_polygons.geojson")
    stats = validate_geojson_file(out)
    assert stats["all_valid"]
    minx, miny, maxx, maxy = stats["bounds_lonlat"]
    assert -122.27 < minx < maxx < -122.19 and 49.04 < miny < maxy < 49.09  # inside the bbox, [lon, lat]
    assert json.loads(out.read_text())["type"] == "FeatureCollection"

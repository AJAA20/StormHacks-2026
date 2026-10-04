"""Create fake-but-realistic Sentinel-2 L2A band files so Person 1 can work without downloading.

Writes two "scenes" over the same 6 x 5 km area near Sumas Prairie (EPSG:32610):

  data/mock/sentinel/flood/    B03.tif (10 m)  B11.tif (20 m)  SCL.tif (20 m)
  data/mock/sentinel/preflood/ B03.tif (10 m)  B11.tif (20 m)  SCL.tif (20 m)

Values are uint16 digital numbers (reflectance x 10000, 0 = nodata), like real L2A.
Like the real product, B11/SCL are 20 m, so the pipeline must resample them.

Flood scene contents:
  * a permanent river (also in the pre-flood scene -> removed by change detection)
  * a large flood lake and a flooded field (only in the flood scene)
  * a cloud (bright in both bands, MNDWI ~ +0.07, i.e. looks like water!
    -> must be removed using SCL)
  * a no-data strip on the west edge (swath edge)

Usage:
    python scripts/create_mock_sentinel_bands.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

CRS = "EPSG:32610"
W10, H10 = 600, 500  # 10 m grid -> 6 km x 5 km
ORIGIN_X, ORIGIN_Y = 553_000.0, 5_437_000.0

# Typical L2A reflectances (x 10000) for Green (B03) and SWIR (B11)
LAND = (800, 2000)  # MNDWI ~ -0.43
WATER = (1000, 150)  # MNDWI ~ +0.74
TURBID_FLOOD = (1200, 700)  # MNDWI ~ +0.26 (muddy flood water)
CLOUD = (4000, 3500)  # MNDWI ~ +0.07
SCL_VEG, SCL_WATER, SCL_CLOUD_HIGH, SCL_NODATA = 4, 6, 9, 0


def _features():
    rows, cols = np.mgrid[0:H10, 0:W10]
    river = np.abs(rows - (0.5 * cols + 60)) <= 3
    lake = ((cols - 230) / 90) ** 2 + ((rows - 260) / 70) ** 2 <= 1
    field = (rows >= 80) & (rows < 120) & (cols >= 400) & (cols < 460)
    cloud = ((cols - 470) / 40) ** 2 + ((rows - 380) / 30) ** 2 <= 1
    edge = cols < 30
    return river, lake & ~river, field, cloud, edge


def build_scene(flooded: bool, seed: int):
    """Return (green10, swir10, scl10) uint16 arrays on the 10 m grid."""
    rng = np.random.default_rng(seed)
    river, lake, field, cloud, edge = _features()
    green = np.full((H10, W10), LAND[0], dtype=float)
    swir = np.full((H10, W10), LAND[1], dtype=float)
    scl = np.full((H10, W10), SCL_VEG, dtype=np.uint16)

    def paint(where, values, scl_code):
        green[where], swir[where] = values
        scl[where] = scl_code

    paint(river, WATER, SCL_WATER)
    if flooded:
        paint(lake, TURBID_FLOOD, SCL_WATER)
        paint(field, TURBID_FLOOD, SCL_WATER)
        paint(cloud, CLOUD, SCL_CLOUD_HIGH)

    green += rng.normal(0, 40, green.shape)  # sensor noise / surface variation
    swir += rng.normal(0, 60, swir.shape)
    green = np.clip(green, 1, 10000).astype(np.uint16)
    swir = np.clip(swir, 1, 10000).astype(np.uint16)
    green[edge] = swir[edge] = 0
    scl[edge] = SCL_NODATA
    return green, swir, scl


def to_20m(a: np.ndarray, mode: str) -> np.ndarray:
    """Downsample 10 m -> 20 m: mean for reflectance, top-left sample for class codes."""
    if mode == "mean":
        blocks = a.reshape(H10 // 2, 2, W10 // 2, 2).astype(float)
        has_zero = (blocks == 0).any(axis=(1, 3))
        out = blocks.mean(axis=(1, 3)).round().astype(np.uint16)
        out[has_zero] = 0
        return out
    return a[::2, ::2]


def write(path: Path, data: np.ndarray, pixel: float, nodata):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
        dtype=data.dtype, crs=CRS, transform=from_origin(ORIGIN_X, ORIGIN_Y, pixel, pixel),
        nodata=nodata, compress="deflate",
    ) as dst:
        dst.write(data, 1)


def create_mock_sentinel_bands(root: str | Path = "data/mock/sentinel") -> dict[str, dict[str, Path]]:
    root = Path(root)
    out = {}
    for name, flooded, seed in (("flood", True, 1), ("preflood", False, 2)):
        green, swir, scl = build_scene(flooded, seed)
        d = root / name
        paths = {"green": d / "B03.tif", "swir": d / "B11.tif", "scl": d / "SCL.tif"}
        write(paths["green"], green, 10.0, 0)
        write(paths["swir"], to_20m(swir, "mean"), 20.0, 0)
        write(paths["scl"], to_20m(scl, "sample"), 20.0, None)
        out[name] = paths
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default="data/mock/sentinel")
    args = p.parse_args()
    for scene, paths in create_mock_sentinel_bands(args.root).items():
        print(f"{scene:9s}: " + ", ".join(str(v) for v in paths.values()))
    print(f"CRS {CRS}; B03 {W10}x{H10} @ 10 m, B11/SCL {W10 // 2}x{H10 // 2} @ 20 m")


if __name__ == "__main__":
    main()

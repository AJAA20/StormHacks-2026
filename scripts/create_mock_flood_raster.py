"""Create a small, fake-but-georeferenced flood mask so Person 2 can work without Person 1.

The raster mimics Person 1's real output:
  * single band, uint8, 1 = flooded, 0 = dry, 255 = nodata
  * 10 m pixels (Sentinel-2 B03 resolution)
  * EPSG:32610 (WGS 84 / UTM zone 10N), which is the CRS Sentinel-2 uses for the
    Abbotsford / Sumas Prairie area. The extent sits near lon -122.24, lat 49.06.

Contents: a large flood "lake" with a dry island inside it, a river-like strip,
a medium patch, a pair of diagonally-touching patches and a patch
separated by a 1-pixel dry gap (to test --merge),
scattered 1-pixel noise (to test --min-area) and a nodata strip on the right.

Usage:
    python scripts/create_mock_flood_raster.py [--output data/mock/mock_flood_mask.tif]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

CRS = "EPSG:32610"
PIXEL_SIZE = 10.0  # metres
WIDTH, HEIGHT = 400, 300  # 4 km x 3 km
# Upper-left corner in UTM metres (easting, northing). Row 0 is the NORTH edge.
ORIGIN_X, ORIGIN_Y = 554_000.0, 5_436_000.0
NODATA = 255


def build_mask_array(seed: int = 42) -> np.ndarray:
    rows, cols = np.mgrid[0:HEIGHT, 0:WIDTH]
    mask = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)

    # 1. Big flood lake (ellipse) with a dry island inside it.
    lake = ((cols - 120) / 80) ** 2 + ((rows - 150) / 60) ** 2 <= 1
    island = ((cols - 130) / 15) ** 2 + ((rows - 145) / 10) ** 2 <= 1
    mask[lake & ~island] = 1

    # 2. River-like diagonal strip, ~60 m wide.
    river = np.abs(rows - (0.6 * cols - 40)) <= 3
    mask[river & (cols > 200) & (cols < 360)] = 1

    # 3. Medium rectangular patch (e.g. a flooded field): 30 x 20 px = 6 ha.
    mask[30:50, 250:280] = 1

    # 4. Two patches touching only at a corner, plus one 1 px (10 m) away.
    #    Separate polygons by default; one polygon with --merge (gap 10 m).
    mask[230:250, 260:280] = 1
    mask[250:270, 280:300] = 1
    mask[250:270, 301:320] = 1

    # 5. Salt-and-pepper noise: isolated single flooded pixels (100 m^2 each).
    rng = np.random.default_rng(seed)
    noise_r = rng.integers(0, HEIGHT, 40)
    noise_c = rng.integers(0, WIDTH, 40)
    mask[noise_r, noise_c] = 1

    # 6. Nodata strip on the right edge (like a scene edge or cloud mask).
    mask[:, WIDTH - 20 :] = NODATA
    return mask


def create_mock_flood_raster(output: str | Path = "data/mock/mock_flood_mask.tif") -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # from_origin(west, north, xsize, ysize) builds the affine transform:
    #   x = ORIGIN_X + col * 10,   y = ORIGIN_Y - row * 10
    transform = from_origin(ORIGIN_X, ORIGIN_Y, PIXEL_SIZE, PIXEL_SIZE)
    data = build_mask_array()

    with rasterio.open(
        output, "w", driver="GTiff", width=WIDTH, height=HEIGHT, count=1,
        dtype="uint8", crs=CRS, transform=transform, nodata=NODATA, compress="deflate",
    ) as dst:
        dst.write(data, 1)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="data/mock/mock_flood_mask.tif")
    args = parser.parse_args()

    path = create_mock_flood_raster(args.output)
    data = build_mask_array()
    print(f"Wrote mock flood raster: {path}")
    print(f"  CRS {CRS}, {WIDTH}x{HEIGHT} px @ {PIXEL_SIZE:g} m, "
          f"origin (UL) = ({ORIGIN_X:.0f}, {ORIGIN_Y:.0f})")
    print(f"  flooded px: {(data == 1).sum()}, dry px: {(data == 0).sum()}, nodata px: {(data == NODATA).sum()}")


if __name__ == "__main__":
    main()

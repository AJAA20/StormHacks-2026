"""Export the Sentinel-2 true-colour image as an image the web map can drape over the basemap.

MapLibre places an image by its four corner coordinates and stretches it linearly in
Web Mercator, so we first warp the image to EPSG:3857 (Web Mercator) and then report
the corners in lon/lat.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds

WEB_MERCATOR = "EPSG:3857"


def export_overlay(tif_path: str | Path, out_path: str | Path, max_size: int = 1400) -> list[list[float]]:
    """Write an RGBA image, transparent where there is no data. WebP (~0.2 MB) if out_path ends
    in .webp, else PNG (~3 MB).

    Returns the corners [[lon, lat] top-left, top-right, bottom-right, bottom-left],
    the order MapLibre's image source expects.
    """
    with rasterio.open(tif_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, WEB_MERCATOR, src.width, src.height, *src.bounds
        )
        scale = max(width, height) / max_size
        if scale > 1:  # downsample so the image stays small enough for the browser
            transform = transform * transform.scale(scale, scale)
            width, height = int(round(width / scale)), int(round(height / scale))

        rgb = np.zeros((3, height, width), dtype=np.uint8)
        for band in range(3):
            reproject(
                source=rasterio.band(src, band + 1),
                destination=rgb[band],
                dst_transform=transform,
                dst_crs=WEB_MERCATOR,
                src_nodata=0,
                dst_nodata=0,
                resampling=Resampling.bilinear,
            )

    alpha = np.where(rgb.max(axis=0) > 0, 255, 0).astype(np.uint8)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(np.dstack([*rgb, alpha]), mode="RGBA")
    if out_path.suffix == ".webp":
        image.save(out_path, quality=82, method=6)
    else:
        image.save(out_path, optimize=True)

    left, top = transform.c, transform.f
    right, bottom = transform.c + transform.a * width, transform.f + transform.e * height
    w, s, e, n = transform_bounds(WEB_MERCATOR, "EPSG:4326", left, bottom, right, top)
    return [[w, n], [e, n], [e, s], [w, s]]

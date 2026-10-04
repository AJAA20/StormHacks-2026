"""Turn an MNDWI array into a binary flood mask: 1 = flooded, 0 = dry, 255 = nodata."""

from __future__ import annotations

import numpy as np

FLOODED, DRY, NODATA = 1, 0, 255

# Sentinel-2 L2A Scene Classification (SCL) codes we cannot trust:
#   0 no data, 1 saturated/defective, 3 cloud shadow,
#   8 cloud medium prob., 9 cloud high prob., 10 thin cirrus.
# (6 = water, 4 = vegetation, 5 = bare soil, 7 = unclassified, 11 = snow are kept.)
# Cloud shadows are dark in SWIR and can look like water, so they are masked too.
SCL_INVALID_CLASSES = (0, 1, 3, 8, 9, 10)


def dilate(mask: np.ndarray, pixels: int) -> np.ndarray:
    """Grow True regions by `pixels` in every direction (square neighbourhood), numpy only."""
    if pixels <= 0:
        return mask
    padded = np.pad(mask, pixels, mode="edge")
    out = np.zeros_like(mask)
    h, w = mask.shape
    for dr in range(2 * pixels + 1):
        for dc in range(2 * pixels + 1):
            out |= padded[dr : dr + h, dc : dc + w]
    return out


def cloud_mask_from_scl(
    scl: np.ndarray, invalid_classes=SCL_INVALID_CLASSES, buffer_px: int = 0
) -> np.ndarray:
    """True where the pixel is cloud/shadow/nodata according to SCL (or SCL itself is NaN).

    buffer_px grows the mask: cloud edges are hazy and SCL is only 20 m, so the
    1-2 pixels around a cloud often have water-like MNDWI. A 2 px buffer is common.
    """
    return dilate(~np.isfinite(scl) | np.isin(scl, invalid_classes), buffer_px)


def threshold_mndwi(mndwi: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """Boolean water map: True where MNDWI > threshold. NaN is never water.

    Lower threshold -> more pixels count as water (wet soil, turbid flood water).
    0.0 is the textbook starting point; flood water full of sediment often needs
    ~-0.05..0.05, while clean lakes are well above 0.3. Tune it visually.
    """
    with np.errstate(invalid="ignore"):
        return np.isfinite(mndwi) & (mndwi > threshold)


def build_flood_mask(
    mndwi: np.ndarray,
    threshold: float = 0.0,
    invalid: np.ndarray | None = None,
    preflood_mndwi: np.ndarray | None = None,
    preflood_threshold: float | None = None,
) -> np.ndarray:
    """Combine thresholding, nodata/cloud masking and optional change detection.

    invalid         : bool array, True = don't trust this pixel (clouds, nodata).
    preflood_mndwi  : MNDWI from a dry-weather scene on the same grid. If given,
                      pixels that were ALREADY water before (rivers, lakes) are
                      set to 0, so the output contains only *new* flood water.
                      Without this, every river would count as a "flooded road"
                      wherever a bridge crosses it.

    Returns uint8 array: 1 flooded, 0 dry, 255 nodata.
    """
    water = threshold_mndwi(mndwi, threshold)
    if preflood_mndwi is not None:
        if preflood_mndwi.shape != mndwi.shape:
            raise ValueError("preflood_mndwi must be on the same grid as mndwi.")
        before = threshold_mndwi(preflood_mndwi, threshold if preflood_threshold is None else preflood_threshold)
        water &= ~before  # where the pre-flood scene is NaN, `before` is False -> keep the water

    out = np.where(water, FLOODED, DRY).astype("uint8")
    nodata = ~np.isfinite(mndwi)
    if invalid is not None:
        nodata |= invalid
    out[nodata] = NODATA
    return out

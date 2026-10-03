"""MNDWI: Modified Normalized Difference Water Index (Xu, 2006).

    MNDWI = (Green - SWIR) / (Green + SWIR)

Why it finds water: water reflects some green light but absorbs almost all
short-wave infrared (SWIR), so Green > SWIR and MNDWI is positive (typically
+0.2 to +0.8). Soil, vegetation and buildings reflect much more SWIR than
green, so MNDWI is negative. The result is always in [-1, +1].

For Sentinel-2: Green = B03 (560 nm, 10 m), SWIR = B11 (1610 nm, 20 m).
"""

from __future__ import annotations

import numpy as np

L2A_SCALE = 10_000.0  # Sentinel-2 L2A stores reflectance x 10000 as integers


def to_reflectance(dn: np.ndarray, boa_offset: float = 0.0) -> np.ndarray:
    """Convert L2A digital numbers to surface reflectance (0..1).

    The offset matters for MNDWI: a ratio is unaffected by *scaling* both bands,
    but NOT by *adding* a constant, so skipping the -1000 offset on newer
    products would bias every MNDWI value. 0 DN is nodata and becomes NaN.
    """
    dn = dn.astype("float32")
    out = (dn + boa_offset) / L2A_SCALE
    out[~np.isfinite(dn) | (dn == 0)] = np.nan
    return out


def compute_mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Pixel-wise MNDWI with division-by-zero protection.

    Pixels where Green + SWIR == 0 (or either input is NaN) become NaN instead
    of raising a warning or producing inf. Output is float32 in [-1, 1].
    """
    if green.shape != swir.shape:
        raise ValueError(f"Band shapes differ: green {green.shape} vs swir {swir.shape}. Align them first.")
    green = green.astype("float32")
    swir = swir.astype("float32")
    num = green - swir
    den = green + swir
    valid = np.isfinite(num) & np.isfinite(den) & (den != 0)
    out = np.full(green.shape, np.nan, dtype="float32")
    np.divide(num, den, out=out, where=valid)
    # Negative reflectances (possible after offset correction) can push |MNDWI| > 1.
    return np.clip(out, -1.0, 1.0, where=valid, out=out)

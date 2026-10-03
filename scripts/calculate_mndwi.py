"""Sentinel-2 B03 + B11 -> MNDWI -> data/processed/flood_mask.tif (Person 2's input).

Mock data:
    python scripts/calculate_mndwi.py \\
        --green data/mock/sentinel/flood/B03.tif --swir data/mock/sentinel/flood/B11.tif \\
        --scl data/mock/sentinel/flood/SCL.tif \\
        --pre-green data/mock/sentinel/preflood/B03.tif --pre-swir data/mock/sentinel/preflood/B11.tif \\
        --bbox -122.26 49.045 -122.20 49.08 --preview data/processed/mndwi_preview.png

Real unzipped L2A products:
    python scripts/calculate_mndwi.py --safe-dir data/raw/S2B_MSIL2A_..._N0301_....SAFE \\
        --pre-safe-dir data/raw/S2A_MSIL2A_....SAFE --bbox -122.32 49.00 -122.10 49.12
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from backend.satellite.bands import boa_offset_from_name, find_safe_bands  # noqa: E402
from backend.satellite.pipeline import generate_flood_mask  # noqa: E402


def resolve_scene(safe_dir, green, swir, scl, label):
    """Return (green, swir, scl) paths from either --safe-dir or explicit band paths."""
    if safe_dir:
        bands = find_safe_bands(safe_dir)
        return bands["green"], bands["swir"], bands.get("scl")
    if bool(green) != bool(swir):
        sys.exit(f"error: {label} needs both green and swir band paths")
    return green, swir, scl


def save_preview(result: dict, png_path: Path, threshold: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    panels = [("Flood-date MNDWI", result["mndwi"], "RdBu", (-1, 1))]
    if result["preflood_mndwi"] is not None:
        panels.append(("Pre-flood MNDWI", result["preflood_mndwi"], "RdBu", (-1, 1)))
    mask = np.where(result["mask"] == 255, np.nan, result["mask"].astype(float))
    panels.append((f"Flood mask (MNDWI > {threshold:g})", mask, ListedColormap(["#e8e4d8", "#1f6fd1"]), (0, 1)))

    fig, axes = plt.subplots(1, len(panels), figsize=(5 * len(panels), 4.4))
    for ax, (title, arr, cmap, (vmin, vmax)) in zip(np.atleast_1d(axes), panels):
        im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        ax.set_title(title)
        ax.set_axis_off()
        if "MNDWI" in title and "mask" not in title:
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("grey/white = nodata or cloud (masked)", fontsize=9)
    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def parse_args():
    p = argparse.ArgumentParser(description="Compute MNDWI and a binary flood mask from Sentinel-2 L2A bands.")
    g = p.add_argument_group("flood-date scene (use --safe-dir OR --green/--swir)")
    g.add_argument("--safe-dir", help="Unzipped L2A .SAFE folder")
    g.add_argument("--green", help="B03 (Green, 10 m) GeoTIFF/JP2")
    g.add_argument("--swir", help="B11 (SWIR, 20 m) GeoTIFF/JP2")
    g.add_argument("--scl", help="SCL (scene classification, 20 m) for cloud masking - strongly recommended")
    pg = p.add_argument_group("optional pre-flood scene (removes permanent rivers/lakes)")
    pg.add_argument("--pre-safe-dir")
    pg.add_argument("--pre-green")
    pg.add_argument("--pre-swir")
    pg.add_argument("--pre-scl")
    p.add_argument("--bbox", type=float, nargs=4, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                   help="Crop to this lon/lat box (EPSG:4326). Default: whole image")
    p.add_argument("--threshold", type=float, default=0.0, help="MNDWI > threshold = water (default 0.0)")
    p.add_argument("--boa-offset", type=float, default=None,
                   help="Added to DN before /10000. Default: auto from product name (-1000 for baseline >= N0400, else 0)")
    p.add_argument("--cloud-buffer", type=int, default=2,
                   help="Grow the SCL cloud mask by this many pixels (default 2)")
    p.add_argument("--out-mask", default="data/processed/flood_mask.tif")
    p.add_argument("--out-mndwi", default="data/processed/mndwi.tif")
    p.add_argument("--preview", default=None, help="Optional PNG with MNDWI + mask panels")
    return p.parse_args()


def main() -> int:
    a = parse_args()
    green, swir, scl = resolve_scene(a.safe_dir, a.green, a.swir, a.scl, "flood scene")
    if not green:
        sys.exit("error: give --safe-dir or --green and --swir")
    pre_green, pre_swir, pre_scl = resolve_scene(a.pre_safe_dir, a.pre_green, a.pre_swir, a.pre_scl, "pre-flood scene")

    offset = a.boa_offset if a.boa_offset is not None else boa_offset_from_name(a.safe_dir or green)
    pre_offset = a.boa_offset if a.boa_offset is not None else boa_offset_from_name(a.pre_safe_dir or pre_green or "")

    print("[1/3] Inputs")
    print(f"  green (B03)  : {green}")
    print(f"  swir  (B11)  : {swir}")
    print(f"  scl          : {scl or '- (no cloud masking!)'}")
    print(f"  pre-flood    : {pre_green or '-'}{'  +  ' + str(pre_swir) if pre_swir else ''}")
    print(f"  bbox         : {a.bbox or 'whole image'}")
    print(f"  BOA offset   : {offset:g} (pre-flood {pre_offset:g})")

    print("[2/3] Aligning bands, computing MNDWI, thresholding")
    r = generate_flood_mask(
        green, swir, out_mask=a.out_mask, threshold=a.threshold, scl_path=scl,
        bbox=tuple(a.bbox) if a.bbox else None, boa_offset=offset,
        pre_green_path=pre_green, pre_swir_path=pre_swir, pre_scl_path=pre_scl, pre_boa_offset=pre_offset,
        out_mndwi=a.out_mndwi, cloud_buffer_px=a.cloud_buffer,
    )
    g, s = r["grid"], r["stats"]
    print(f"  grid         : {g.width} x {g.height} px @ {abs(g.transform.a):g} m, {g.crs.to_string()}")
    print(f"  transform    : {tuple(round(v, 3) for v in g.transform[:6])}")
    print(f"  MNDWI range  : {s['mndwi_min']:.3f} .. {s['mndwi_max']:.3f}")
    print(f"  threshold    : MNDWI > {a.threshold:g}" + ("  (minus pre-flood water)" if pre_green else ""))
    print(f"  masked px    : {s['invalid_pixels']} (cloud / shadow / nodata)")
    print(f"  flooded px   : {s['flooded_pixels']} ({s['flooded_pct_of_valid']:.1f}% of valid) = {s['flooded_area_km2']:.3f} km^2")
    if s["flooded_pixels"] == 0:
        print("  WARNING: nothing flooded. Try a lower --threshold, check the bbox and the BOA offset.")

    print("[3/3] Outputs")
    print(f"  flood mask   : {r['out_mask']}  (uint8: 1 flooded, 0 dry, 255 nodata)")
    if r["out_mndwi"]:
        print(f"  MNDWI        : {r['out_mndwi']}  (float32, NaN nodata)")
    if a.preview:
        save_preview(r, Path(a.preview), a.threshold)
        print(f"  preview      : {a.preview}")
    print("Next: python scripts/run_vectorization.py --input " + str(r["out_mask"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

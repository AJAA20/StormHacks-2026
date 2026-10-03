"""Flood raster -> EPSG:4326 flood polygon GeoJSON.

Example:
    python scripts/run_vectorization.py \\
        --input data/mock/mock_flood_mask.tif \\
        --output data/processed/flood_polygons.geojson \\
        --min-area 1000 --simplify 5 --merge --plot data/processed/debug.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/run_vectorization.py` from the repo root without installing anything.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gis.crs_utils import describe_crs  # noqa: E402
from backend.gis.geojson_export import export_geojson, validate_geojson_file  # noqa: E402
from backend.gis.vectorize import load_flood_mask, vectorize_flood_mask  # noqa: E402


def save_debug_plot(geojson_path: Path, png_path: Path) -> None:
    """Development-only: draw the exported polygons so you can eyeball them."""
    import geopandas as gpd
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gdf = gpd.read_file(geojson_path)
    fig, ax = plt.subplots(figsize=(8, 6))
    if len(gdf):
        gdf.plot(ax=ax, facecolor="#4a90d9", edgecolor="#0b3d91", linewidth=0.6, alpha=0.7)
    ax.set_title(f"{geojson_path.name}: {len(gdf)} flood polygons (EPSG:4326)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=120)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vectorize a binary flood raster into GeoJSON polygons.")
    p.add_argument("--input", required=True, help="Flood mask GeoTIFF (1 = flooded)")
    p.add_argument("--output", default="data/processed/flood_polygons.geojson")
    p.add_argument("--min-area", type=float, default=1000.0,
                   help="Drop polygons smaller than this, in m^2 (default 1000 = 10 Sentinel-2 pixels; 0 disables)")
    p.add_argument("--simplify", type=float, default=5.0,
                   help="Simplification tolerance in metres (default 5 = half a 10 m pixel; 0 disables)")
    p.add_argument("--processing-crs", default=None,
                   help="Projected CRS for area/simplify, e.g. EPSG:32610. Default: raster CRS if metric, else auto UTM")
    p.add_argument("--merge", action="store_true", help="Dissolve polygons that touch or are within --merge-gap")
    p.add_argument("--merge-gap", type=float, default=10.0,
                   help="With --merge: join patches closer than this many metres (default 10 = one 10 m pixel)")
    p.add_argument("--flood-value", type=int, default=1, help="Pixel value that means flooded (default 1)")
    p.add_argument("--source", default="satellite", help='Value of the "source" property (default satellite)')
    p.add_argument("--plot", default=None, help="Optional PNG path for a debug plot")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path, out_path = Path(args.input), Path(args.output)

    print(f"[1/4] Loading raster: {in_path}")
    mask = load_flood_mask(in_path, flood_value=args.flood_value)
    print(mask.summary())
    if not mask.flooded.any():
        print(f"  WARNING: no pixels equal {args.flood_value}. Check --flood-value / Person 1's encoding.")

    print("[2/4] Vectorizing + cleaning")
    gdf = vectorize_flood_mask(
        in_path,
        min_area=args.min_area,
        processing_crs=args.processing_crs,
        merge=args.merge,
        merge_gap=args.merge_gap if args.merge else 0.0,
        simplify_tolerance=args.simplify,
        flood_value=args.flood_value,
    )
    print(f"  processing CRS : {describe_crs(gdf.crs)}")
    print(f"  settings       : min_area={args.min_area:g} m^2, simplify={args.simplify:g} m, merge={args.merge} (gap {args.merge_gap:g} m)")
    print(f"  polygons kept  : {len(gdf)}")
    print(f"  total area     : {gdf['area_m2'].sum() / 1e6:.3f} km^2")
    print(f"  all valid      : {bool(gdf.geometry.is_valid.all()) if len(gdf) else 'n/a (empty)'}")
    if gdf.empty:
        print("  WARNING: 0 polygons. Try --min-area 0 to see if filtering removed everything.")

    print(f"[3/4] Exporting EPSG:4326 GeoJSON: {out_path}")
    export_geojson(gdf, out_path, source=args.source)

    print("[4/4] Validating output")
    stats = validate_geojson_file(out_path)
    print(f"  type           : FeatureCollection")
    print(f"  features       : {stats['features']}")
    print(f"  CRS            : {stats['crs']}  (coordinates are [lon, lat])")
    print(f"  bounds lon/lat : {stats['bounds_lonlat']}")
    print(f"  all valid      : {stats['all_valid']}")

    if args.plot:
        save_debug_plot(out_path, Path(args.plot))
        print(f"  debug plot     : {args.plot}")

    print(f"Done -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

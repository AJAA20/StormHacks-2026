"""Find and download Sentinel-2 L2A data from Earth Search (AWS), no account or API key needed.

How it works:
  1. STAC search: ask the public catalogue for every Sentinel-2 scene that
     touches our bbox in a date range. Each result ("item") lists links to
     its bands as Cloud-Optimized GeoTIFFs (COGs) on Amazon S3.
  2. Rank: tile-level cloud % describes a ~110 km tile and is misleading for a
     small area, so we read just the AOI pixels of each scene's SCL (scene
     classification) band and measure how much of OUR area is cloud-free.
  3. Download: read only the AOI window of B03, B11, SCL (and true colour)
     over HTTP and save them as small local GeoTIFFs. COGs make this possible:
     GDAL fetches just the bytes for the pixels we ask for, not the 1 GB product.

Results are cached in data/raw/stac/<scene>_<bbox-hash>/ so re-runs are offline.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from backend.satellite.mask import SCL_INVALID_CLASSES

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
# Collection 1 = ESA's consistent reprocessing of the whole archive (baseline 05.00).
COLLECTION = "sentinel-2-c1-l2a"
BANDS = {"green": "B03", "swir16": "B11", "scl": "SCL"}
TRUE_COLOUR = "visual"  # 8-bit RGB preview, handy as a map overlay for the frontend
SCL_WATER = 6

# GDAL settings for fast, anonymous reads of public S3 COGs.
GDAL_ENV = dict(
    AWS_NO_SIGN_REQUEST="YES",
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
)

BBox = tuple[float, float, float, float]


@dataclass
class SceneCandidate:
    id: str
    date: str
    tile_cloud_pct: float  # whole-tile cloud cover from metadata
    aoi_clear_pct: float  # % of OUR bbox that is valid and cloud-free (from SCL)
    aoi_water_pct: float  # % of OUR bbox classified as water by ESA's SCL


@dataclass
class DownloadedScene:
    id: str
    date: str
    dir: Path
    green: Path
    swir: Path
    scl: Path
    true_colour: Path | None
    boa_offset: float  # add to DN before /10000 (e.g. -1000)
    aoi_clear_pct: float


def search_scenes(bbox: BBox, date_range: str, limit: int = 200) -> list:
    """STAC search. date_range like '2021-11-14/2021-12-10'. Returns pystac Items, newest first."""
    from pystac_client import Client  # imported lazily so offline code paths don't need it

    with warnings.catch_warnings():
        # Harmless pystac notice about Earth Search's S3 URL format; hide it to keep output readable.
        warnings.filterwarnings("ignore", message="Could not parse bucket/account", category=UserWarning)
        client = Client.open(EARTH_SEARCH_URL)
        search = client.search(collections=[COLLECTION], bbox=list(bbox), datetime=date_range, max_items=limit)
        return list(search.items())


def _read_window(href: str, bbox: BBox):
    """Read the bbox window of a remote COG. Returns (array, profile) in the file's own CRS."""
    with rasterio.open(href) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=window, boundless=True, fill_value=src.nodata or 0)
        profile = src.profile.copy()
    for key in ("blockxsize", "blockysize", "tiled", "photometric", "interleave"):
        profile.pop(key, None)  # drop COG/JPEG layout options; we write a plain small GeoTIFF
    profile.update(
        driver="GTiff", width=data.shape[2], height=data.shape[1],
        transform=src.window_transform(window), compress="deflate",
    )
    if data.shape[0] == 3:
        profile["photometric"] = "RGB"
    return data, profile


def score_scene(item, bbox: BBox) -> SceneCandidate:
    """Measure cloud-free and water fraction of the AOI using the scene's SCL band."""
    with rasterio.Env(**GDAL_ENV):
        scl, _ = _read_window(item.assets["scl"].href, bbox)
    scl = scl[0]
    clear = ~np.isin(scl, SCL_INVALID_CLASSES)  # also excludes 0 = nodata / outside the tile
    return SceneCandidate(
        id=item.id,
        date=item.datetime.date().isoformat(),
        tile_cloud_pct=round(float(item.properties.get("eo:cloud_cover", float("nan"))), 1),
        aoi_clear_pct=round(100 * float(clear.mean()), 1),
        aoi_water_pct=round(100 * float((scl == SCL_WATER).mean()), 1),
    )


def rank_scenes(items: list, bbox: BBox, workers: int = 8) -> list[SceneCandidate]:
    """Score every item in parallel and sort clearest-first."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        scored = list(pool.map(lambda it: score_scene(it, bbox), items))
    return sorted(scored, key=lambda s: (-s.aoi_clear_pct, s.date))


def boa_offset_from_item(item) -> float:
    """Reflectance offset in DN units from STAC raster metadata (offset / scale).

    Collection 1 lists scale 0.0001 and offset -0.1, i.e. reflectance = DN * 0.0001 - 0.1,
    which is the same as (DN - 1000) / 10000 -> boa_offset = -1000.
    """
    bands = item.assets["green"].extra_fields.get("raster:bands") or [{}]
    scale = bands[0].get("scale", 0.0001)
    offset = bands[0].get("offset", 0.0)
    return round(offset / scale, 6) if scale else 0.0


def _bbox_key(bbox: BBox) -> str:
    return hashlib.sha1(json.dumps([round(v, 5) for v in bbox]).encode()).hexdigest()[:8]


def download_scene(item, bbox: BBox, root: str | Path = "data/raw/stac", true_colour: bool = True) -> DownloadedScene:
    """Download the AOI window of B03, B11, SCL (+ true colour) for one item. Cached."""
    out_dir = Path(root) / f"{item.id}_{_bbox_key(bbox)}"
    meta_path = out_dir / "scene.json"
    if meta_path.exists():
        return _load_cached(meta_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    assets = dict(BANDS)
    if true_colour and TRUE_COLOUR in item.assets:
        assets[TRUE_COLOUR] = "TCI"
    paths: dict[str, Path] = {}
    with rasterio.Env(**GDAL_ENV):
        for key, name in assets.items():
            data, profile = _read_window(item.assets[key].href, bbox)
            path = out_dir / f"{name}.tif"
            with rasterio.open(path, "w", **profile) as dst:
                dst.write(data)
            paths[key] = path

    scene = DownloadedScene(
        id=item.id, date=item.datetime.date().isoformat(), dir=out_dir,
        green=paths["green"], swir=paths["swir16"], scl=paths["scl"],
        true_colour=paths.get(TRUE_COLOUR), boa_offset=boa_offset_from_item(item),
        aoi_clear_pct=score_scene(item, bbox).aoi_clear_pct,
    )
    meta = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(scene).items()}
    meta.update(bbox=list(bbox), collection=COLLECTION, source=EARTH_SEARCH_URL)
    meta_path.write_text(json.dumps(meta, indent=2))
    return scene


def _load_cached(meta_path: Path) -> DownloadedScene:
    m = json.loads(meta_path.read_text())
    p = lambda k: Path(m[k]) if m.get(k) else None  # noqa: E731
    return DownloadedScene(
        id=m["id"], date=m["date"], dir=Path(m["dir"]), green=p("green"), swir=p("swir"),
        scl=p("scl"), true_colour=p("true_colour"), boa_offset=m["boa_offset"],
        aoi_clear_pct=m["aoi_clear_pct"],
    )


def find_best_scene(bbox: BBox, date_range: str, min_clear_pct: float = 50.0):
    """Search + rank. Returns (best_item, ranking). Raises if nothing is clear enough."""
    items = search_scenes(bbox, date_range)
    if not items:
        raise LookupError(f"No Sentinel-2 scenes found for bbox {bbox} in {date_range}.")
    ranking = rank_scenes(items, bbox)
    best = ranking[0]
    if best.aoi_clear_pct < min_clear_pct:
        raise LookupError(
            f"Clearest scene in {date_range} is only {best.aoi_clear_pct}% cloud-free over the AOI "
            f"({best.date}). Widen the date range or lower min_clear_pct."
        )
    item = next(it for it in items if it.id == best.id)
    return item, ranking

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.regions.store import PRESET_ID, RegionNotFound
from backend.routing.routes import PointOutsideRegion, compute_route

router = APIRouter()

class RouteRequest(BaseModel):
    start_coords: list[float]  # [lng, lat]
    end_coords: list[float]    # [lng, lat]
    # Water-detection level. The app uses the default (MNDWI > 0.0, the standard threshold);
    # "low"/"moderate" read the same image more strictly and are kept for comparisons.
    scenario: Literal["low", "moderate", "severe"] = "severe"
    # Which analysed area to route in (GET /api/regions); default = Abbotsford preset
    region_id: str = PRESET_ID
    flood_level: float = 0.5
    custom_polygon_overrides: list = []


@router.post("/api/route")
def get_route(req: RouteRequest):
    try:
        return compute_route(tuple(req.start_coords), tuple(req.end_coords), req.scenario, req.region_id)
    except RegionNotFound:
        raise HTTPException(404, f"Unknown region '{req.region_id}'.") from None
    except PointOutsideRegion as exc:
        raise HTTPException(400, str(exc)) from None

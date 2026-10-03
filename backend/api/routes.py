from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from backend.routing.routes import compute_route

router = APIRouter()

class RouteRequest(BaseModel):
    start_coords: list[float]  # [lng, lat]
    end_coords: list[float]    # [lng, lat]
    # Flood scenario from the UI; each maps to a satellite flood layer (backend/data/flood/)
    scenario: Literal["low", "moderate", "severe"] = "severe"
    flood_level: float = 0.5
    custom_polygon_overrides: list = []


@router.post("/api/route")
def get_route(req: RouteRequest):
    return compute_route(tuple(req.start_coords), tuple(req.end_coords), req.scenario)
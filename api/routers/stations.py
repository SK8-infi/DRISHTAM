"""Stations & Divisions API — /api/stations, /api/station/{name}, /api/optimize/station."""

from fastapi import APIRouter, HTTPException

from api.engine_loader import engines
from api.models import StationOptimizeRequest

router = APIRouter(prefix="/api", tags=["stations"])


@router.get("/stations")
async def list_stations(division: str | None = None) -> list[dict]:
    """Return all 54 traffic police stations with summary stats.

    Optional ?division=East filter.
    """
    return engines.get_stations(division)


@router.get("/station/{station_name}")
async def station_detail(station_name: str) -> dict:
    """Full drill-down for a single station."""
    result = engines.get_station_detail(station_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Station '{station_name}' not found")
    return result


@router.post("/optimize/station")
async def optimize_by_station(req: StationOptimizeRequest) -> dict:
    """Division/station-constrained patrol optimization.

    Unlike the global optimizer, this ensures officers are allocated
    within their administrative boundaries.
    """
    result = engines.run_optimize_by_station(
        n_officers=req.n_officers,
        shifts=req.shifts,
        hours_per_shift=req.hours_per_shift,
        station=req.station,
        division=req.division,
        proportional=req.proportional,
        custom_allocation=req.custom_allocation,
        min_officer_spacing_m=req.min_officer_spacing_m,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

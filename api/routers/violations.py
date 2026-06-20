"""GET /api/violations — Search individual violations."""

from fastapi import APIRouter, Query

from api.engine_loader import engines

router = APIRouter(prefix="/api", tags=["violations"])


@router.get("/violations")
async def search_violations(
    road_name: str | None = Query(None, description="Filter by road name (partial match)"),
    hour: int | None = Query(None, ge=0, le=23, description="Filter by hour"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
):
    """Search violations by road, hour, and severity."""
    df = engines.search_violations(road_name, hour, limit)
    cols = [
        "id", "latitude", "longitude", "road_name", "violation_type",
        "vehicle_type_clean", "hour_ist", "pis", "capacity_blocked_pct",
        "violation_severity",
    ]
    available_cols = [c for c in cols if c in df.columns]
    records = df[available_cols].to_dict("records")
    return {"count": len(records), "violations": records}

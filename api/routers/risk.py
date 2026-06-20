"""GET /api/risk — Live risk forecast using Engine 3."""

from fastapi import APIRouter, Query

from api.engine_loader import engines
from api.models import RiskResponse, RiskSegment

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk", response_model=RiskResponse)
async def get_risk(
    hour: int = Query(9, ge=0, le=23, description="Hour of day (0-23)"),
    top_n: int = Query(50, ge=1, le=200, description="Number of top-risk segments"),
) -> RiskResponse:
    """Predict risk for a given hour. Returns top-N risky segments."""
    segments = engines.get_risk(hour, top_n)
    return RiskResponse(
        hour=hour,
        count=len(segments),
        segments=[RiskSegment(**s) for s in segments],
    )


@router.get("/risk/animation")
async def get_risk_animation(
    hour_start: int = Query(0, ge=0, le=23),
    hour_end: int = Query(23, ge=0, le=23),
    top_n: int = Query(30, ge=1, le=100),
) -> dict:
    """Get risk data for all hours in range — for 24-hour animation."""
    data = engines.get_risk_range(hour_start, hour_end, top_n)
    return {"hour_start": hour_start, "hour_end": hour_end, "hourly_data": data}

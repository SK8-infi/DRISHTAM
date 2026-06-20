"""GET /api/insights — Live data-driven insights."""

from fastapi import APIRouter

from api.engine_loader import engines
from api.models import InsightsResponse

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/insights", response_model=InsightsResponse)
async def get_insights():
    """Return dynamically computed insights from live engine data.

    Includes:
    - 8 data-driven findings with hero values and evidence links
    - Data quality scorecard
    - Experiment log (model comparisons)
    - Methodology summaries per engine
    """
    return InsightsResponse(**engines.compute_insights())

"""GET /api/overview — Dashboard KPIs."""

from fastapi import APIRouter

from api.engine_loader import engines
from api.models import OverviewResponse

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview() -> OverviewResponse:
    """Return top-level dashboard KPIs."""
    return engines.overview

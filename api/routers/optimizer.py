"""POST /api/optimize — Live patrol optimization."""

from fastapi import APIRouter

from api.engine_loader import engines
from api.models import OptimizeRequest

router = APIRouter(prefix="/api", tags=["optimizer"])


@router.post("/optimize")
async def run_optimize(req: OptimizeRequest):
    """Run patrol optimization for a custom fleet configuration."""
    result = engines.run_optimize(req.n_officers, req.shifts, req.hours_per_shift)
    return result

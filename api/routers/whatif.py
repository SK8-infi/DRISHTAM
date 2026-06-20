"""POST /api/whatif — Live what-if computation using Engine 2."""

from fastapi import APIRouter

from api.engine_loader import engines
from api.models import WhatIfRequest, WhatIfResponse

router = APIRouter(prefix="/api", tags=["whatif"])


@router.post("/whatif", response_model=WhatIfResponse)
async def run_whatif(req: WhatIfRequest) -> WhatIfResponse:
    """Run live what-if scenario.

    Loads GBM → zeros violation features on target roads → re-predicts → returns delta.
    """
    result = engines.run_whatif(req.road_names, req.seg_indices if req.seg_indices else None)
    return WhatIfResponse(**result)


@router.get("/whatif/scenarios")
async def get_predefined_scenarios() -> dict:
    """Return the 12 predefined scenario results."""
    return engines.scenarios


@router.get("/whatif/roads")
async def get_available_roads(q: str = "", limit: int = 20) -> dict:
    """Search available road names for the road selector."""
    roads = engines.segments["road_name"].unique()
    if q:
        roads = [r for r in roads if q.lower() in str(r).lower() and r != "Unnamed"]
    else:
        # Return top roads by violation count
        top = (
            engines.violations[engines.violations["road_name"] != "Unnamed"].groupby("road_name").size().nlargest(limit)
        )
        roads = top.index.tolist()
    return {"roads": list(roads[:limit])}

"""GET /api/clusters — Cluster explorer data."""

from fastapi import APIRouter, HTTPException, Query

from api.engine_loader import engines
from api.models import ClusterDetail, ClusterSummary

router = APIRouter(prefix="/api", tags=["clusters"])


@router.get("/clusters")
async def get_clusters(
    top_n: int = Query(50, ge=1, le=200, description="Number of top clusters"),
):
    """Return top-N clusters ranked by total PIS impact, with spatial extent."""
    clusters = engines.get_clusters(top_n)
    return {"count": len(clusters), "clusters": clusters}


@router.get("/cluster/{cluster_id}", response_model=ClusterDetail)
async def get_cluster_detail(cluster_id: int):
    """Full drill-down for a single cluster — road breakdown, hourly profile, vehicle types."""
    detail = engines.get_cluster_detail(cluster_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")
    return ClusterDetail(**detail)


@router.get("/clusters/{cluster_id}/violations")
async def get_cluster_violations(cluster_id: int, limit: int = Query(50, ge=1, le=200)):
    """Return violations belonging to a specific cluster."""
    if "cluster_id" not in engines.violations.columns:
        return {"count": 0, "violations": []}

    df = engines.violations[engines.violations["cluster_id"] == cluster_id].head(limit)
    records = df[
        ["id", "latitude", "longitude", "road_name", "violation_type",
         "vehicle_type_clean", "hour_ist", "pis", "capacity_blocked_pct"]
    ].to_dict("records")
    return {"count": len(records), "violations": records}


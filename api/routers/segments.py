"""GET /api/segments — Bbox-filtered segment data.

GET /api/segment/{seg_idx} — Deep segment inspection.
"""

from fastapi import APIRouter, HTTPException, Query

from api.engine_loader import engines
from api.models import SegmentDetail, SegmentLight, SegmentsResponse

router = APIRouter(prefix="/api", tags=["segments"])


@router.get("/segments", response_model=SegmentsResponse)
async def get_segments(
    lat_min: float = Query(12.85, description="South bound"),
    lat_max: float = Query(13.10, description="North bound"),
    lon_min: float = Query(77.45, description="West bound"),
    lon_max: float = Query(77.75, description="East bound"),
    min_impact: float = Query(0.0, ge=0, description="Minimum impact threshold"),
    max_impact: float = Query(1.0, le=1.0, description="Maximum impact threshold"),
    tier: int | None = Query(None, ge=0, le=8, description="Road tier filter"),
    limit: int = Query(5000, ge=1, le=20000, description="Max segments returned"),
) -> SegmentsResponse:
    """Return lightweight segment data within bounding box."""
    df = engines.query_bbox(lat_min, lat_max, lon_min, lon_max, min_impact, max_impact, tier, limit)

    # Vectorized serialization — 10-50× faster than df.iterrows()
    cols = [
        "seg_idx",
        "lat",
        "lon",
        "lat_u",
        "lon_u",
        "lat_v",
        "lon_v",
        "road_name",
        "highway",
        "tier",
        "lanes",
        "impact_gbm",
        "violation_count",
    ]
    # Fill missing geometry columns with centroid
    for col in ("lat_u", "lon_u", "lat_v", "lon_v"):
        if col not in df.columns:
            base = "lat" if col.startswith("lat") else "lon"
            df = df.assign(**{col: df[base]})

    records = df[cols].fillna({"road_name": "", "highway": "", "tier": 0, "lanes": 1}).to_dict("records")
    segments = [SegmentLight(**r) for r in records]

    return SegmentsResponse(
        count=len(segments),
        bbox={"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        segments=segments,
    )


@router.get("/segment/{seg_idx}", response_model=SegmentDetail)
async def get_segment_detail(seg_idx: int) -> SegmentDetail:
    """Deep inspection of a single segment — the microscopic view."""
    data = engines.get_segment(seg_idx)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Segment {seg_idx} not found")

    # Clean numpy types for JSON
    cleaned = {}
    for k, v in data.items():
        if k in ("neighbors", "hourly_profile", "pis_breakdown"):
            cleaned[k] = v
        elif hasattr(v, "item"):
            cleaned[k] = v.item()
        else:
            cleaned[k] = v

    return SegmentDetail(**cleaned)

"""DRISHTAM API — Main application.

Loads all trained models at startup. Serves live model inference.

Run:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.engine_loader import engines
from api.routers import clusters, insights, optimizer, overview, risk, segments, stations, violations, whatif

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all engines at startup."""
    engines.load_all()
    yield
    logger.info("Shutting down DRISHTAM API.")


app = FastAPI(
    title="DRISHTAM API",
    description="Predictive Enforcement Intelligence for Urban Parking-Induced Congestion",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(overview.router)
app.include_router(segments.router)
app.include_router(whatif.router)
app.include_router(risk.router)
app.include_router(optimizer.router)
app.include_router(clusters.router)
app.include_router(violations.router)
app.include_router(insights.router)
app.include_router(stations.router)


@app.get("/health")
async def health():
    return {"status": "ok", "engines_loaded": engines.ready}

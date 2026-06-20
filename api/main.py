"""DRISHTAM API — Main application.

Loads all trained models at startup. Serves live model inference.

Run:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from api.engine_loader import engines
from api.routers import clusters, insights, optimizer, overview, risk, segments, stations, violations, whatif

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Environment-driven configuration ─────────────────────────
# DRISHTAM_ENV: "development" | "production" (default: development)
ENV = os.environ.get("DRISHTAM_ENV", "development").lower()
IS_PROD = ENV == "production"

# Allowed origins for CORS (comma-separated in env, defaults for dev)
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = os.environ.get("DRISHTAM_ALLOWED_ORIGINS", _default_origins).split(",")


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
    # Disable interactive docs in production to reduce attack surface
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

# ── Maximum request body size (10 MB) ────────────────────────
MAX_BODY_SIZE = int(os.environ.get("DRISHTAM_MAX_BODY_SIZE", str(10 * 1024 * 1024)))


# ── Global Exception Handlers ────────────────────────────────
# Prevent stack traces from leaking to clients in production.

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions — log full trace, return safe message."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        f"Unhandled exception [request_id={request_id}]: {exc}"
    )
    if not IS_PROD:
        # In development, include traceback for debugging
        tb = traceback.format_exc()
        logger.error(tb)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "traceback": tb},
        )
    # In production, return generic message (no internal details)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return clean validation errors without internal details."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": [
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", "Invalid value"),
                    "type": err.get("type", "value_error"),
                }
                for err in exc.errors()
            ],
        },
    )


# ── Security Middleware Stack ────────────────────────────────
# Order matters: outermost middleware runs first on request.

# 1. Trusted Host — reject requests with forged Host headers
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.environ.get("DRISHTAM_ALLOWED_HOSTS", "*").split(","),
)

# 2. CORS — restrict to known origins (no wildcard + credentials combo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # No cookies/auth tokens needed
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    max_age=600,  # Cache preflight for 10 minutes
)


# 3. Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    """Add security headers to every response."""
    # Generate request ID for tracing
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    start = time.time()
    response: Response = await call_next(request)
    elapsed = time.time() - start

    # ── Security Headers ──
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # XSS protection (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions policy — disable unnecessary browser features
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    # Content Security Policy for API responses
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # HSTS (only in production behind TLS)
    if IS_PROD:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    # Request tracing
    response.headers["X-Request-ID"] = request_id
    # Server timing (non-sensitive)
    response.headers["Server-Timing"] = f"total;dur={elapsed*1000:.1f}"
    # Remove server identity header
    if "server" in response.headers:
        del response.headers["server"]

    return response


# 4. Simple rate limiter middleware (in-memory, per-IP)
_rate_store: dict[str, list[float]] = {}
_rate_store_cleanup_counter = 0
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = int(os.environ.get("DRISHTAM_RATE_LIMIT", "120"))  # requests per window
RATE_STORE_MAX_IPS = 10_000  # Max tracked IPs to prevent memory exhaustion


@app.middleware("http")
async def rate_limiter(request: Request, call_next) -> Response:
    """Sliding-window rate limiter per client IP with memory bounds."""
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)

    # Enforce request body size limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return Response(
            content='{"detail":"Request body too large"}',
            status_code=413,
            media_type="application/json",
        )

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW

    # Periodic cleanup: evict stale IPs every 100 requests to bound memory
    global _rate_store_cleanup_counter
    _rate_store_cleanup_counter += 1
    if _rate_store_cleanup_counter >= 100:
        _rate_store_cleanup_counter = 0
        stale_ips = [ip for ip, ts in _rate_store.items() if not ts or ts[-1] < cutoff]
        for ip in stale_ips:
            del _rate_store[ip]
        # Hard cap: if still too many IPs, drop oldest half
        if len(_rate_store) > RATE_STORE_MAX_IPS:
            sorted_ips = sorted(_rate_store.keys(), key=lambda ip: _rate_store[ip][-1] if _rate_store[ip] else 0)
            for ip in sorted_ips[:len(sorted_ips) // 2]:
                del _rate_store[ip]

    # Clean old entries for this IP and check count
    if client_ip not in _rate_store:
        _rate_store[client_ip] = []
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > cutoff]

    if len(_rate_store[client_ip]) >= RATE_LIMIT_MAX:
        return Response(
            content='{"detail":"Rate limit exceeded. Try again later."}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)


# ── Register Routers ─────────────────────────────────────────
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

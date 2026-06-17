"""DRISHTAM shared utility functions.

Common helpers used across multiple modules — coordinate conversions,
timer decorators, safe file I/O, and data validation utilities.

This module contains no domain-specific logic; only generic helpers.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

from drishtam.config import LAT_TO_METERS, LON_TO_METERS

logger = logging.getLogger(__name__)


# =============================================================================
# COORDINATE HELPERS
# =============================================================================


def latlon_to_meters(
    lat: np.ndarray | float,
    lon: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert lat/lon to approximate meter coordinates.

    Uses simple equirectangular projection, accurate enough for
    city-scale analysis at Bengaluru's latitude (~13°N).

    Args:
        lat: Latitude value(s) in degrees.
        lon: Longitude value(s) in degrees.

    Returns:
        Tuple of (y_meters, x_meters) arrays.
    """
    return np.asarray(lat) * LAT_TO_METERS, np.asarray(lon) * LON_TO_METERS


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Compute haversine (great-circle) distance between two points.

    Args:
        lat1: Latitude of point 1 (degrees).
        lon1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lon2: Longitude of point 2 (degrees).

    Returns:
        Distance in meters.
    """
    r = 6_371_000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return float(r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))


# =============================================================================
# TIMING / PROFILING
# =============================================================================


def log_timer(func: Callable) -> Callable:
    """Decorator to log function execution time.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function that logs elapsed time at INFO level.

    Example:
        >>> @log_timer
        ... def heavy_computation():
        ...     time.sleep(1)
        >>> heavy_computation()
        heavy_computation completed in 1.00s
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("%s completed in %.2fs", func.__name__, elapsed)
        return result

    return wrapper


# =============================================================================
# SAFE FILE I/O
# =============================================================================


def safe_load_parquet(path: Path) -> pd.DataFrame:
    """Load a parquet file with validation.

    Args:
        path: Path to the .parquet file.

    Returns:
        Loaded DataFrame.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not a parquet file.
    """
    import pandas as pd

    path = Path(path).resolve()
    if not path.exists():
        msg = f"Parquet file not found: {path}"
        raise FileNotFoundError(msg)
    if path.suffix != ".parquet":
        msg = f"Expected .parquet file, got: {path.suffix}"
        raise ValueError(msg)

    df = pd.read_parquet(path)
    logger.info("Loaded %s: %d rows × %d cols", path.name, len(df), len(df.columns))
    return df


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist.

    Args:
        path: Directory path to ensure.

    Returns:
        The resolved path.
    """
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# DATA VALIDATION HELPERS
# =============================================================================


def check_required_columns(
    df: pd.DataFrame,
    required: list[str],
    context: str = "",
) -> None:
    """Validate that a DataFrame has all required columns.

    Args:
        df: DataFrame to validate.
        required: List of column names that must be present.
        context: Optional context string for error messages.

    Raises:
        ValueError: If any required columns are missing.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        ctx = f" ({context})" if context else ""
        msg = f"Missing required columns{ctx}: {', '.join(missing)}"
        raise ValueError(msg)


def clip_outliers(
    series: pd.Series,
    lower_pct: float = 1.0,
    upper_pct: float = 99.0,
) -> pd.Series:
    """Clip values to percentile range for outlier removal.

    Args:
        series: Numeric pandas Series.
        lower_pct: Lower percentile (default 1%).
        upper_pct: Upper percentile (default 99%).

    Returns:
        Clipped Series.
    """
    lower = series.quantile(lower_pct / 100)
    upper = series.quantile(upper_pct / 100)
    return series.clip(lower=lower, upper=upper)

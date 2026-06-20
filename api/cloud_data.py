"""DRISHTAM — Cloud Data Fetcher.

Downloads required data and model files from a public GCS bucket
to a local cache directory. Uses stdlib only (no google-cloud-storage).

Environment variables:
    DRISHTAM_DATA_DIR  — If set, skip download and use this directory as
                         the data root. Useful for local development where
                         data/ and models/ sit next to the project.
    DRISHTAM_CACHE_DIR — Override the default cache location
                         (default: ~/.cache/drishtam).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# ── GCS public bucket ────────────────────────────────────────────
GCS_BUCKET = "drishtam-data"
GCS_BASE_URL = f"https://storage.googleapis.com/{GCS_BUCKET}"

# ── Manifest: every file the backend needs ───────────────────────
# Format: (relative_path, expected_size_bytes)
# Sizes are used to verify complete downloads.
REQUIRED_FILES: list[tuple[str, int]] = [
    # data/
    ("data/bengaluru_roads.graphml", 150_669_155),
    ("data/violations_enriched.parquet", 50_456_475),
    ("data/propagated_impact.parquet", 7_225_026),
    ("data/risk_predictions.parquet", 2_741_193),
    ("data/counterfactual_scenarios.json", 75_821),
    ("data/enforcement_schedule.json", 44_652),
    ("data/risk_alerts.json", 99_778),
    ("data/risk_summary.json", 1_353),
    ("data/fleet_comparison.json", 1_477),
    ("data/simulation/baseline_flows.parquet", 15_313_484),
    ("data/simulation/delay_metrics.parquet", 7_821_729),
    # models/
    ("models/features_36d.npy", 56_695_376),
    ("models/segment_predictions.parquet", 34_467_725),
    ("models/edge_list.npz", 9_051_393),
    ("models/gbm_36d_best.pkl", 5_676_602),
    ("models/seg_betweenness.npy", 1_574_996),
    ("models/risk_forecaster_best.pkl", 521_120),
    ("models/mlp_36d_best.pt", 382_501),
    ("models/feature_scaler.pkl", 1_479),
    ("models/ml_summary.json", 637),
]


def _default_cache_dir() -> Path:
    """Return the default cache directory."""
    return Path(os.environ.get("DRISHTAM_CACHE_DIR", Path.home() / ".cache" / "drishtam"))


def _download_file(url: str, dest: Path, expected_size: int) -> None:
    """Download a single file with progress logging."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Download to a temp file first, then atomic rename
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".download")
    os.close(tmp_fd)

    try:
        logger.info("  \u2193 %s (%.1f MB)", dest.name, expected_size / 1_000_000)
        urllib.request.urlretrieve(url, tmp_path)  # noqa: S310

        # Verify size
        actual_size = Path(tmp_path).stat().st_size
        if actual_size != expected_size:
            logger.warning(
                "  \u26a0 Size mismatch for %s: expected %d, got %d",
                dest.name,
                expected_size,
                actual_size,
            )

        # Atomic move
        shutil.move(tmp_path, dest)
    except Exception:
        # Clean up temp file on failure
        tmp = Path(tmp_path)
        if tmp.exists():
            tmp.unlink()
        raise


def _file_ok(path: Path, expected_size: int) -> bool:
    """Check if a cached file exists and matches expected size."""
    if not path.exists():
        return False
    return path.stat().st_size == expected_size


def ensure_data_downloaded() -> tuple[Path, Path]:
    """Ensure all required data files are available locally.

    Returns:
        (data_dir, models_dir) — absolute paths to the local
        data/ and models/ directories.
    """
    # ── Check for local override ──
    local_override = os.environ.get("DRISHTAM_DATA_DIR")
    if local_override:
        root = Path(local_override)
        logger.info("Using local data dir: %s", root)
        return root / "data", root / "models"

    # ── Download from GCS ──
    cache_root = _default_cache_dir()
    logger.info("Cache directory: %s", cache_root)

    files_to_download: list[tuple[str, int]] = []
    for rel_path, expected_size in REQUIRED_FILES:
        local_path = cache_root / rel_path
        if not _file_ok(local_path, expected_size):
            files_to_download.append((rel_path, expected_size))

    if not files_to_download:
        logger.info("All %d files cached \u2705", len(REQUIRED_FILES))
    else:
        logger.info(
            "Downloading %d/%d files from gs://%s...",
            len(files_to_download),
            len(REQUIRED_FILES),
            GCS_BUCKET,
        )
        for rel_path, expected_size in files_to_download:
            url = f"{GCS_BASE_URL}/{rel_path}"
            dest = cache_root / rel_path
            _download_file(url, dest, expected_size)
        logger.info("Download complete \u2705")

    return cache_root / "data", cache_root / "models"

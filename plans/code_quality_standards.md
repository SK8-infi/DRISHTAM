# Code Quality & Security Standards — ParkImpact

> Every line of code in this project must meet these standards before merge.

---

## 1. Toolchain

All tools are configured in [`pyproject.toml`](../pyproject.toml).

| Tool | Purpose | Config Section | Run Command |
|---|---|---|---|
| **Ruff** | Linting + Formatting + Import sorting | `[tool.ruff]` | `ruff check . --fix` / `ruff format .` |
| **Mypy** | Static type checking | `[tool.mypy]` | `mypy parkimpact/` |
| **Bandit** | Security vulnerability scanning | `[tool.bandit]` | `bandit -r parkimpact/ -c pyproject.toml` |
| **Pytest** | Unit + integration testing | `[tool.pytest]` | `pytest` |
| **Coverage** | Code coverage (minimum 60%) | `[tool.coverage]` | `pytest --cov` |

### Quick Command: Run All Checks

```bash
# From project root, with venv activated:
python scripts/quality_check.py
```

This runs all checks in sequence and reports pass/fail.

---

## 2. Code Style Rules

### 2.1 Formatting
- **Line length**: 120 characters max
- **Quotes**: Double quotes (`"`) for strings
- **Indentation**: 4 spaces (never tabs)
- **Trailing commas**: Always on multi-line structures
- **Imports**: Sorted by isort rules (stdlib → third-party → first-party)

### 2.2 Naming Conventions
```python
# Modules: snake_case
import impact_scorer

# Classes: PascalCase
class ParkImpactGAT:
    pass

# Functions/methods: snake_case
def compute_capacity_factor(viol_df: pd.DataFrame) -> pd.Series:
    pass

# Constants: UPPER_SNAKE_CASE
ROAD_HIERARCHY = {...}
MAX_PIS_SCORE = 100
DEFAULT_DECAY_RATE = 0.5

# Private: leading underscore
def _normalize_features(features: np.ndarray) -> np.ndarray:
    pass

# Variables: snake_case, descriptive
violation_count = len(df)  # ✅ Good
vc = len(df)               # ❌ Bad — cryptic abbreviation
```

### 2.3 Docstrings (Google Style)
Every public function and class MUST have a docstring:

```python
def compute_pis(
    viol_df: pd.DataFrame,
    nodes_gdf: gpd.GeoDataFrame,
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """Compute Parking Impact Score (0-100) for each violation.

    Combines six components (capacity, road importance, junction proximity,
    temporal, density, severity) into a weighted composite score.

    Args:
        viol_df: Enriched violation DataFrame with road attributes.
            Must contain columns: vehicle_width_m, road_width, road_tier, etc.
        nodes_gdf: OSM graph nodes GeoDataFrame (intersections).
        weights: Optional weight overrides. Keys must be component names.
            Defaults to {capacity: 0.30, importance: 0.20, junction: 0.15,
            temporal: 0.15, density: 0.10, severity: 0.10}.

    Returns:
        pd.Series of PIS values (float, 0-100 scale), indexed like viol_df.

    Raises:
        ValueError: If required columns are missing from viol_df.
        ValueError: If weights don't sum to 1.0 (within tolerance).

    Example:
        >>> pis = compute_pis(violations, nodes)
        >>> pis.describe()
        count    298445.0
        mean         34.2
        std          18.7
    """
```

### 2.4 Type Annotations
All function signatures MUST have type annotations:

```python
# ✅ Good
def load_violations(path: Path, bbox: tuple[float, ...] | None = None) -> pd.DataFrame:
    ...

# ✅ Good — complex types
def build_node_features(
    edges: gpd.GeoDataFrame,
    viol_df: pd.DataFrame,
    normalize: bool = True,
) -> tuple[torch.Tensor, dict[str, Any]]:
    ...

# ❌ Bad — no annotations
def load_violations(path, bbox=None):
    ...
```

---

## 3. Security Rules

### 3.1 Never Hardcode Secrets or Paths

```python
# ❌ NEVER
API_KEY = "sk-abc123..."
DB_PASSWORD = "hunter2"
DATA_PATH = "C:\\Users\\shiva\\Github\\..."

# ✅ ALWAYS use config/environment
API_KEY = os.environ.get("MAPPLS_API_KEY", "")
DATA_PATH = config.DATA_DIR / "violations.csv"
```

### 3.2 Input Validation
All API endpoints and data processing functions must validate inputs:

```python
# ✅ FastAPI endpoint with validation
@router.get("/api/impact/road/{road_name}")
async def get_road_impact(
    road_name: str = Path(..., min_length=1, max_length=200),
    pis_min: float = Query(0, ge=0, le=100),
    pis_max: float = Query(100, ge=0, le=100),
) -> RoadImpactResponse:
    # Sanitize road_name — no SQL/path injection
    road_name = road_name.strip()
    if not re.match(r'^[\w\s\.\-\/]+$', road_name):
        raise HTTPException(status_code=400, detail="Invalid road name")
    ...
```

### 3.3 Data Sanitization
- Never use `eval()` or `exec()` on user input
- Never use `pickle.load()` on untrusted data — use `parquet` or `json`
- Sanitize all strings before using in file paths or queries
- Use `pathlib.Path` instead of string concatenation for paths

### 3.4 Dependency Safety
- Pin major versions in `pyproject.toml`
- No `*` imports (`from module import *`)
- Review any new dependency before adding

### 3.5 File I/O Safety

```python
# ✅ Safe file reading with pathlib
from pathlib import Path

def load_data(path: Path) -> pd.DataFrame:
    """Load data with path validation."""
    path = Path(path).resolve()
    if not path.exists():
        msg = f"Data file not found: {path}"
        raise FileNotFoundError(msg)
    if not path.suffix in {".csv", ".parquet", ".json"}:
        msg = f"Unsupported file type: {path.suffix}"
        raise ValueError(msg)
    ...
```

---

## 4. Error Handling

### 4.1 Custom Exceptions

```python
# parkimpact/exceptions.py
class ParkImpactError(Exception):
    """Base exception for ParkImpact."""

class DataValidationError(ParkImpactError):
    """Raised when data fails validation checks."""

class ModelNotTrainedError(ParkImpactError):
    """Raised when trying to use an untrained model."""

class InsufficientDataError(ParkImpactError):
    """Raised when data is too sparse for reliable computation."""
```

### 4.2 Error Message Standards

```python
# ❌ Bad — generic, unhelpful
raise ValueError("Invalid data")

# ✅ Good — specific, actionable
msg = (
    f"Column 'road_width' has {null_count} null values ({null_pct:.1f}%). "
    f"Expected 0 nulls. Run data_pipeline.enrich_violations() first."
)
raise DataValidationError(msg)
```

### 4.3 Logging (not print)

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Use logging levels appropriately
logger.info("Loading %d violations from %s", count, path)
logger.warning("Column 'width' has %d nulls, using estimates", null_count)
logger.error("Failed to load road network: %s", exc)
logger.debug("KDTree built in %.2f seconds", elapsed)

# ❌ Never use print() in library code
print("Loading data...")  # Only allowed in scripts/
```

---

## 5. Testing Standards

### 5.1 Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_data_pipeline.py    # Phase 1 tests
├── test_impact_scorer.py    # Phase 2 tests
├── test_graph_builder.py    # Phase 3 tests
├── test_propagation.py      # Phase 3 tests
├── test_counterfactual.py   # Phase 4 tests
├── test_risk_forecaster.py  # Phase 4 tests
├── test_api/                # Phase 5 tests
│   ├── test_impact_routes.py
│   ├── test_whatif_routes.py
│   └── test_forecast_routes.py
└── fixtures/                # Small test data files
    ├── sample_violations.csv (100 rows)
    └── sample_roads.graphml (50 segments)
```

### 5.2 Test Requirements
- **Every public function** must have at least 1 test
- **Every PIS component** must have edge-case tests (zero, max, typical)
- **Every API endpoint** must have happy-path + error-path tests
- **Coverage minimum**: 60% overall, 80% for `impact_scorer.py`

### 5.3 Test Patterns

```python
# ✅ Good test — descriptive name, clear assertion
def test_capacity_factor_car_on_narrow_road():
    """Car (2.0m) on 6m residential road should block ~33%."""
    df = pd.DataFrame({
        "vehicle_width_m": [2.0],
        "road_width": [6.0],
    })
    result = compute_capacity_factor(df)
    assert abs(result.iloc[0] - 0.333) < 0.01

def test_capacity_factor_never_exceeds_one():
    """Capacity factor must be clipped to [0, 1]."""
    df = pd.DataFrame({
        "vehicle_width_m": [2.5],  # HGV
        "road_width": [4.0],      # Living street — wider than road!
    })
    result = compute_capacity_factor(df)
    assert result.iloc[0] <= 1.0

def test_pis_requires_enriched_data():
    """PIS should raise if required columns are missing."""
    df = pd.DataFrame({"latitude": [12.97]})  # Missing required columns
    with pytest.raises(DataValidationError, match="road_width"):
        compute_pis(df, mock_nodes)
```

### 5.4 Fixtures

```python
# tests/conftest.py
import pytest
import pandas as pd

@pytest.fixture
def sample_violations() -> pd.DataFrame:
    """100-row sample of enriched violation data for testing."""
    return pd.read_parquet(Path(__file__).parent / "fixtures" / "sample_violations.parquet")

@pytest.fixture
def sample_edges() -> gpd.GeoDataFrame:
    """50-segment sample of road network for testing."""
    ...
```

---

## 6. Verification Checks (Data Quality Gates)

Every phase has verification checks. These are implemented as runnable functions:

```python
# parkimpact/verification.py

def verify_enriched_data(df: pd.DataFrame) -> dict[str, bool]:
    """Run all Phase 1 data quality checks.

    Returns:
        Dict of check_name → passed (bool).
        Raises DataValidationError if any critical check fails.
    """
    checks = {}

    # Check 1: Record count
    checks["record_count"] = 290_000 < len(df) < 310_000

    # Check 2: No NaN in core columns
    core_cols = ["latitude", "longitude", "vehicle_width_m", "road_width", "road_tier"]
    checks["no_core_nulls"] = df[core_cols].isna().sum().sum() == 0

    # Check 3: Capacity blocked range
    checks["capacity_range"] = (
        df["capacity_blocked_pct"].min() >= 0
        and df["capacity_blocked_pct"].max() <= 100
    )

    # Check 4: Median distance to road
    median_dist = df["dist_to_road_m"].median()
    checks["median_dist_reasonable"] = 10 < median_dist < 30

    # ... more checks ...

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        msg = f"Data verification FAILED on: {', '.join(failed)}"
        raise DataValidationError(msg)

    return checks
```

---

## 7. Git Hygiene

### 7.1 .gitignore

Key entries (already handled, but verify):
```
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.egg-info/
data/*.parquet          # Large data files
data/*.pt               # Model files
data/*.graphml          # OSM cache
data/models/            # Trained models
node_modules/           # Dashboard deps
dashboard/.next/        # Next.js build
.env                    # Environment variables
```

### 7.2 Commit Messages
```
feat: add PIS capacity factor computation
fix: handle NaN in road width parsing
refactor: extract road hierarchy to config
test: add edge cases for junction proximity
docs: update Phase 2 research report
perf: vectorize KDTree distance computation
security: sanitize road name input in API
```

---

## 8. Quick Reference: Quality Check Commands

```bash
# Activate venv
& ".venv\Scripts\Activate.ps1"

# Format code
ruff format .

# Lint (with auto-fix where safe)
ruff check . --fix

# Security scan
bandit -r parkimpact/ -c pyproject.toml

# Type checking
mypy parkimpact/

# Run tests
pytest

# Run tests with coverage report
pytest --cov --cov-report=html

# Run ALL checks (use the quality script)
python scripts/quality_check.py
```

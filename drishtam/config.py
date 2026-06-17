"""DRISHTAM central configuration.

All paths, constants, hyperparameters, and lookup tables live here.
No other module should hardcode paths or magic numbers.

References:
    - Road hierarchy: OSM wiki + EDA #4 findings
    - Vehicle widths: IRC (Indian Roads Congress) standards
    - Peak hours: EDA #1 temporal analysis (IST converted)
    - Violation severity: Expert judgment + EDA #1 congestion-relevant types
"""

from __future__ import annotations

import logging
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
VIOLATION_PATH = PROJECT_ROOT / "jan to may police violation_anonymized791b166.csv"
EVENT_PATH = PROJECT_ROOT / "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
OSM_CACHE_PATH = DATA_DIR / "bengaluru_roads.graphml"
ENRICHED_DATA_PATH = DATA_DIR / "violations_enriched.parquet"

# Output paths
RESEARCH_DIR = PROJECT_ROOT / "research"
MODELS_DIR = DATA_DIR / "models"
EXPORT_DIR = DATA_DIR / "export"

# =============================================================================
# BENGALURU BOUNDING BOX
# =============================================================================
BBOX = {
    "lat_min": 12.7,
    "lat_max": 13.4,
    "lon_min": 77.3,
    "lon_max": 77.9,
}

# Tighter bbox for core violation area (used in some visualizations)
CORE_BBOX = {
    "lat_min": 12.85,
    "lat_max": 13.10,
    "lon_min": 77.45,
    "lon_max": 77.75,
}

# Coordinate conversion factors (approximate at Bengaluru's latitude)
LAT_TO_METERS = 111_000  # 1 degree latitude ≈ 111 km
LON_TO_METERS = 108_000  # 1 degree longitude ≈ 108 km at ~13°N

# =============================================================================
# ROAD HIERARCHY (from EDA #4 + OSM wiki)
# =============================================================================
ROAD_HIERARCHY: dict[str, dict] = {
    "motorway": {"tier": 1, "name": "Expressway", "est_lanes": 6, "est_width_m": 25, "importance": 1.0},
    "motorway_link": {"tier": 1, "name": "Expressway Ramp", "est_lanes": 2, "est_width_m": 8, "importance": 1.0},
    "trunk": {"tier": 2, "name": "Arterial", "est_lanes": 4, "est_width_m": 18, "importance": 0.9},
    "trunk_link": {"tier": 2, "name": "Arterial Ramp", "est_lanes": 2, "est_width_m": 8, "importance": 0.9},
    "primary": {"tier": 3, "name": "Primary", "est_lanes": 4, "est_width_m": 14, "importance": 0.8},
    "primary_link": {"tier": 3, "name": "Primary Ramp", "est_lanes": 2, "est_width_m": 7, "importance": 0.8},
    "secondary": {"tier": 4, "name": "Secondary", "est_lanes": 2, "est_width_m": 10, "importance": 0.6},
    "secondary_link": {"tier": 4, "name": "Secondary Ramp", "est_lanes": 2, "est_width_m": 7, "importance": 0.6},
    "tertiary": {"tier": 5, "name": "Tertiary", "est_lanes": 2, "est_width_m": 8, "importance": 0.4},
    "tertiary_link": {"tier": 5, "name": "Tertiary Ramp", "est_lanes": 1, "est_width_m": 5, "importance": 0.4},
    "residential": {"tier": 6, "name": "Residential", "est_lanes": 2, "est_width_m": 6, "importance": 0.2},
    "living_street": {"tier": 7, "name": "Living Street", "est_lanes": 1, "est_width_m": 4, "importance": 0.1},
    "unclassified": {"tier": 6, "name": "Unclassified", "est_lanes": 2, "est_width_m": 6, "importance": 0.2},
    "service": {"tier": 8, "name": "Service", "est_lanes": 1, "est_width_m": 4, "importance": 0.05},
}

DEFAULT_ROAD_INFO: dict = {"tier": 6, "name": "Other", "est_lanes": 2, "est_width_m": 6, "importance": 0.2}

# =============================================================================
# VEHICLE WIDTHS (IRC standards, meters)
# =============================================================================
VEHICLE_WIDTH_M: dict[str, float] = {
    "CAR": 2.0,
    "SCOOTER": 0.7,
    "MOTOR CYCLE": 0.7,
    "MOPED": 0.6,
    "PASSENGER AUTO": 1.5,
    "MAXI-CAB": 2.3,
    "LGV": 2.5,
    "HGV": 2.5,
    "TRACTOR": 2.5,
    "AMBULANCE": 2.0,
    "OMNI BUS": 2.5,
}
DEFAULT_VEHICLE_WIDTH_M = 1.5

# =============================================================================
# VIOLATION SEVERITY WEIGHTS (expert judgment + EDA #1 findings)
# Reference: Congestion-relevant violations from EDA #1 (Section 2)
# =============================================================================
VIOLATION_SEVERITY: dict[str, float] = {
    "DOUBLE PARKING": 1.0,
    "PARKING IN A MAIN ROAD": 0.9,
    "PARKING NEAR ROAD CROSSING": 0.85,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL": 0.8,
    "PARKING ON FOOTPATH": 0.6,
    "NO PARKING": 0.5,
    "WRONG PARKING": 0.4,
}
DEFAULT_VIOLATION_SEVERITY = 0.4

# =============================================================================
# TEMPORAL DEFINITIONS (IST — from EDA #1 temporal analysis)
# =============================================================================
# Peak hour definitions (IST)
PEAK_MORNING_START = 8  # 8:00 AM IST
PEAK_MORNING_END = 10  # 10:00 AM IST
PEAK_EVENING_START = 17  # 5:00 PM IST
PEAK_EVENING_END = 20  # 8:00 PM IST

# Temporal factor lookup (IST hour → multiplier)
# From EDA #1: enforcement gap is 3:30-8:30 PM IST
TEMPORAL_FACTORS: dict[int, float] = {
    0: 0.2,
    1: 0.2,
    2: 0.2,
    3: 0.2,
    4: 0.2,
    5: 0.2,  # overnight
    6: 0.7,
    7: 0.7,  # early morning
    8: 1.0,
    9: 1.0,  # morning peak
    10: 0.8,
    11: 0.8,  # late morning
    12: 0.6,
    13: 0.6,
    14: 0.6,
    15: 0.6,
    16: 0.6,  # midday
    17: 1.0,
    18: 1.0,
    19: 1.0,  # evening peak
    20: 0.4,
    21: 0.4,
    22: 0.4,
    23: 0.2,  # evening wind-down
}
WEEKEND_MULTIPLIER = 0.7

# UTC to IST offset (5 hours 30 minutes)
IST_OFFSET_HOURS = 5
IST_OFFSET_MINUTES = 30

# =============================================================================
# SPATIAL PARAMETERS
# =============================================================================
NEIGHBORHOOD_RADIUS_M = 300  # Radius for violation density computation
NEIGHBORHOOD_RADIUS_500M = 500  # Larger radius for cross-reference with grid EDA
JUNCTION_PROXIMITY_DECAY_M = 100  # Exponential decay constant for junction factor
BUS_STOP_RADIUS_M = 50  # Radius to consider "near bus stop"
METRO_STATION_RADIUS_M = 200  # Radius to consider "near metro station"
GRID_CELL_SIZE_M = 500  # Grid size for cross-dataset analysis

# =============================================================================
# PIS WEIGHTS (default — may be updated after weight sensitivity analysis)
# =============================================================================
PIS_WEIGHTS: dict[str, float] = {
    "capacity": 0.30,
    "importance": 0.20,
    "junction": 0.15,
    "temporal": 0.15,
    "density": 0.10,
    "severity": 0.10,
}
PIS_MAX_SCORE = 100

# =============================================================================
# ECONOMIC COST PARAMETERS
# Reference: Economic Survey 2025-26, TomTom Traffic Index
# =============================================================================
# Bengaluru annual congestion cost: ₹1.47 lakh crore
ANNUAL_CONGESTION_COST_INR = 1_47_00_000_00_000  # ₹1.47 lakh crore
ESTIMATED_DAILY_COMMUTERS = 5_000_000
WORKING_DAYS_PER_YEAR = 250
PEAK_HOURS_PER_DAY = 4  # 2 morning + 2 evening
COST_PER_VEHICLE_HOUR_INR = ANNUAL_CONGESTION_COST_INR / (
    ESTIMATED_DAILY_COMMUTERS * WORKING_DAYS_PER_YEAR * PEAK_HOURS_PER_DAY
)  # ≈ ₹29.4/vehicle-hour

# =============================================================================
# CARBON IMPACT PARAMETERS
# Reference: IPCC emission factors, MoRTH India fuel data
# =============================================================================
IDLE_FUEL_CONSUMPTION_L_PER_HOUR = 0.8  # Average car (petrol)
CO2_PER_LITER_PETROL_KG = 2.31
CO2_PER_LITER_DIESEL_KG = 2.68
CO2_PER_IDLE_HOUR_KG = IDLE_FUEL_CONSUMPTION_L_PER_HOUR * CO2_PER_LITER_PETROL_KG  # ≈ 1.85 kg
CO2_ABSORBED_PER_TREE_PER_YEAR_KG = 22.0  # Average mature tree

# =============================================================================
# TRAFFIC FLOW ESTIMATES (vehicles/hour by road tier)
# Reference: IRC SP:41-1994 guidelines + Bengaluru BTP estimates
# =============================================================================
TRAFFIC_FLOW_ESTIMATES: dict[str, dict[str, int]] = {
    # tier_name: {peak_vph, offpeak_vph}
    "Expressway": {"peak": 2000, "offpeak": 800},
    "Expressway Ramp": {"peak": 600, "offpeak": 250},
    "Arterial": {"peak": 1200, "offpeak": 500},
    "Arterial Ramp": {"peak": 400, "offpeak": 150},
    "Primary": {"peak": 800, "offpeak": 350},
    "Primary Ramp": {"peak": 300, "offpeak": 120},
    "Secondary": {"peak": 500, "offpeak": 200},
    "Secondary Ramp": {"peak": 200, "offpeak": 80},
    "Tertiary": {"peak": 300, "offpeak": 120},
    "Tertiary Ramp": {"peak": 150, "offpeak": 60},
    "Residential": {"peak": 100, "offpeak": 40},
    "Living Street": {"peak": 30, "offpeak": 15},
    "Unclassified": {"peak": 100, "offpeak": 40},
    "Service": {"peak": 20, "offpeak": 10},
    "Other": {"peak": 100, "offpeak": 40},
}
DELAY_FACTOR_PER_PIS = 0.003  # Each PIS point → 0.3% effective capacity reduction

# =============================================================================
# HDBSCAN CLUSTERING PARAMETERS
# =============================================================================
HDBSCAN_MIN_CLUSTER_SIZE = 50
HDBSCAN_MIN_SAMPLES = 10

# =============================================================================
# WEIGHT SENSITIVITY CONFIGURATIONS
# =============================================================================
WEIGHT_CONFIGS: dict[str, dict[str, float]] = {
    "default": {
        "capacity": 0.30,
        "importance": 0.20,
        "junction": 0.15,
        "temporal": 0.15,
        "density": 0.10,
        "severity": 0.10,
    },
    "capacity_heavy": {
        "capacity": 0.50,
        "importance": 0.15,
        "junction": 0.10,
        "temporal": 0.10,
        "density": 0.10,
        "severity": 0.05,
    },
    "location_heavy": {
        "capacity": 0.20,
        "importance": 0.30,
        "junction": 0.25,
        "temporal": 0.10,
        "density": 0.10,
        "severity": 0.05,
    },
    "temporal_heavy": {
        "capacity": 0.20,
        "importance": 0.15,
        "junction": 0.10,
        "temporal": 0.35,
        "density": 0.10,
        "severity": 0.10,
    },
    "equal": {
        "capacity": 1 / 6,
        "importance": 1 / 6,
        "junction": 1 / 6,
        "temporal": 1 / 6,
        "density": 1 / 6,
        "severity": 1 / 6,
    },
}

# =============================================================================
# VISUALIZATION
# =============================================================================
PLOT_DPI = 150
PLOT_STYLE = "seaborn-v0_8-darkgrid"

PIS_BAND_COLORS: dict[str, str] = {
    "LOW": "#00ff88",  # Green
    "MODERATE": "#ffaa00",  # Amber
    "HIGH": "#ff6600",  # Orange
    "SEVERE": "#ff0000",  # Red
    "CRITICAL": "#cc00ff",  # Purple
}

PIS_BANDS: list[tuple[float, float, str]] = [
    (0, 20, "LOW"),
    (20, 40, "MODERATE"),
    (40, 60, "HIGH"),
    (60, 80, "SEVERE"),
    (80, 100, "CRITICAL"),
]

# =============================================================================
# LOGGING
# =============================================================================
LOG_FORMAT = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for DRISHTAM.

    Args:
        level: Logging level (default: INFO).
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )

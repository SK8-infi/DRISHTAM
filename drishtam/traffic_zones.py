"""DRISHTAM traffic zones — real Bangalore landmarks for digital twin.

Defines ~80 traffic activity zones across Bengaluru, each with:
- Location (lat/lon for snapping to OSM network)
- Type (tech_park, commercial, residential, hospital, etc.)
- Trip generation rates (production/attraction in PCU/hr at peak)
- Temporal demand profile (24-hour curve)

Zone data sourced from:
- OpenStreetMap POI data
- IRC trip generation guidelines
- BMRCL/RITES Bangalore traffic studies
- Google Maps landmark coordinates

Reference: plans/phase3_gnn_propagation.md (digital twin section)
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 1. TEMPORAL DEMAND PROFILES (24-hour multipliers, 0.0–1.0)
# =============================================================================

# Hour indices: 0=midnight, 8=8AM, 17=5PM, 23=11PM
TEMPORAL_PROFILES: dict[str, list[float]] = {
    # Office/IT parks: sharp AM peak (8-10), sharp PM peak (17-19)
    "office": [
        0.05,
        0.03,
        0.02,
        0.02,
        0.03,
        0.05,
        0.10,
        0.30,  # 0-7
        0.80,
        1.00,
        0.85,
        0.60,
        0.50,
        0.50,
        0.55,
        0.60,  # 8-15
        0.75,
        0.95,
        1.00,
        0.70,
        0.40,
        0.20,
        0.10,
        0.07,  # 16-23
    ],
    # Commercial markets: late morning + evening peak
    "commercial": [
        0.05,
        0.03,
        0.02,
        0.02,
        0.03,
        0.05,
        0.08,
        0.15,  # 0-7
        0.30,
        0.50,
        0.70,
        0.85,
        1.00,
        0.95,
        0.80,
        0.75,  # 8-15
        0.80,
        0.90,
        1.00,
        0.85,
        0.60,
        0.35,
        0.15,
        0.08,  # 16-23
    ],
    # Residential: produces in AM, attracts in PM (inverse of office)
    "residential": [
        0.10,
        0.08,
        0.05,
        0.05,
        0.08,
        0.15,
        0.40,
        0.70,  # 0-7
        1.00,
        0.90,
        0.50,
        0.35,
        0.30,
        0.30,
        0.35,
        0.45,  # 8-15
        0.60,
        0.80,
        1.00,
        0.85,
        0.55,
        0.30,
        0.15,
        0.10,  # 16-23
    ],
    # Hospital: steady daytime with slight AM peak
    "hospital": [
        0.15,
        0.10,
        0.08,
        0.08,
        0.10,
        0.15,
        0.25,
        0.50,  # 0-7
        0.80,
        1.00,
        1.00,
        0.95,
        0.85,
        0.80,
        0.80,
        0.85,  # 8-15
        0.90,
        0.85,
        0.70,
        0.50,
        0.35,
        0.25,
        0.20,
        0.15,  # 16-23
    ],
    # Education: sharp AM arrival, PM departure
    "education": [
        0.03,
        0.02,
        0.02,
        0.02,
        0.03,
        0.05,
        0.15,
        0.50,  # 0-7
        0.90,
        1.00,
        0.60,
        0.40,
        0.50,
        0.60,
        0.70,
        0.90,  # 8-15
        1.00,
        0.70,
        0.30,
        0.15,
        0.08,
        0.05,
        0.03,
        0.03,  # 16-23
    ],
    # Transport hub: early morning + evening peaks, moderate all day
    "transport": [
        0.15,
        0.10,
        0.08,
        0.08,
        0.15,
        0.30,
        0.60,
        0.85,  # 0-7
        1.00,
        0.90,
        0.70,
        0.60,
        0.55,
        0.55,
        0.60,
        0.70,  # 8-15
        0.80,
        0.90,
        1.00,
        0.85,
        0.60,
        0.40,
        0.25,
        0.20,  # 16-23
    ],
    # Mall/Entertainment: afternoon + evening heavy
    "entertainment": [
        0.05,
        0.03,
        0.02,
        0.02,
        0.02,
        0.03,
        0.05,
        0.08,  # 0-7
        0.15,
        0.25,
        0.40,
        0.60,
        0.80,
        0.85,
        0.90,
        0.95,  # 8-15
        1.00,
        1.00,
        0.95,
        0.85,
        0.70,
        0.50,
        0.25,
        0.10,  # 16-23
    ],
    # Industrial: early start, steady daytime
    "industrial": [
        0.05,
        0.03,
        0.03,
        0.03,
        0.05,
        0.15,
        0.40,
        0.70,  # 0-7
        0.90,
        1.00,
        0.95,
        0.85,
        0.75,
        0.75,
        0.80,
        0.85,  # 8-15
        0.90,
        0.80,
        0.50,
        0.25,
        0.15,
        0.10,
        0.08,
        0.05,  # 16-23
    ],
}


# =============================================================================
# 2. ZONE DEFINITIONS — REAL BANGALORE LANDMARKS
# =============================================================================

TRAFFIC_ZONES: list[dict] = [
    # =========================================================================
    # IT / TECH PARKS (15 zones) — High attraction during work hours
    # =========================================================================
    {
        "name": "Electronics City Phase 1",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.845,
        "lon": 77.660,
        "peak_attraction": 8000,
        "peak_production": 1000,
    },
    {
        "name": "Electronics City Phase 2",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.835,
        "lon": 77.668,
        "peak_attraction": 5000,
        "peak_production": 600,
    },
    {
        "name": "Manyata Tech Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 13.047,
        "lon": 77.621,
        "peak_attraction": 6000,
        "peak_production": 800,
    },
    {
        "name": "ITPL Whitefield",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.985,
        "lon": 77.730,
        "peak_attraction": 7000,
        "peak_production": 900,
    },
    {
        "name": "Bagmane Tech Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.963,
        "lon": 77.668,
        "peak_attraction": 3500,
        "peak_production": 500,
    },
    {
        "name": "Embassy Golf Links",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.961,
        "lon": 77.648,
        "peak_attraction": 3000,
        "peak_production": 400,
    },
    {
        "name": "RMZ Ecospace (ORR Marathahalli)",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.955,
        "lon": 77.698,
        "peak_attraction": 4000,
        "peak_production": 500,
    },
    {
        "name": "Prestige Tech Park (ORR Sarjapur)",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.916,
        "lon": 77.682,
        "peak_attraction": 3500,
        "peak_production": 450,
    },
    {
        "name": "EcoWorld (Bellandur)",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.926,
        "lon": 77.680,
        "peak_attraction": 4000,
        "peak_production": 500,
    },
    {
        "name": "Brigade Gateway (Rajajinagar)",
        "type": "tech_park",
        "profile": "office",
        "lat": 13.008,
        "lon": 77.555,
        "peak_attraction": 2500,
        "peak_production": 350,
    },
    {
        "name": "Global Village Tech Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.890,
        "lon": 77.640,
        "peak_attraction": 2000,
        "peak_production": 300,
    },
    {
        "name": "Cessna Business Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.920,
        "lon": 77.685,
        "peak_attraction": 2500,
        "peak_production": 350,
    },
    {
        "name": "Pritech Park (ORR)",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.933,
        "lon": 77.690,
        "peak_attraction": 2000,
        "peak_production": 300,
    },
    {
        "name": "Divyashree Tech Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.971,
        "lon": 77.714,
        "peak_attraction": 1800,
        "peak_production": 250,
    },
    {
        "name": "Kirloskar Business Park",
        "type": "tech_park",
        "profile": "office",
        "lat": 12.965,
        "lon": 77.600,
        "peak_attraction": 1500,
        "peak_production": 200,
    },
    # =========================================================================
    # COMMERCIAL / MARKETS (10 zones) — High attraction during business hours
    # =========================================================================
    {
        "name": "KR Market (City Market)",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.962,
        "lon": 77.577,
        "peak_attraction": 4000,
        "peak_production": 2000,
    },
    {
        "name": "Commercial Street",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.981,
        "lon": 77.608,
        "peak_attraction": 3500,
        "peak_production": 1500,
    },
    {
        "name": "Chickpet",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.967,
        "lon": 77.578,
        "peak_attraction": 3000,
        "peak_production": 1200,
    },
    {
        "name": "Gandhi Bazaar (Basavanagudi)",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.944,
        "lon": 77.575,
        "peak_attraction": 2000,
        "peak_production": 1000,
    },
    {
        "name": "Malleswaram Market",
        "type": "commercial",
        "profile": "commercial",
        "lat": 13.003,
        "lon": 77.571,
        "peak_attraction": 2000,
        "peak_production": 1000,
    },
    {
        "name": "Jayanagar 4th Block",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.926,
        "lon": 77.583,
        "peak_attraction": 2500,
        "peak_production": 1200,
    },
    {
        "name": "Koramangala 80ft Road",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.935,
        "lon": 77.620,
        "peak_attraction": 2000,
        "peak_production": 1000,
    },
    {
        "name": "Indiranagar 100ft Road",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.978,
        "lon": 77.640,
        "peak_attraction": 2000,
        "peak_production": 1000,
    },
    {
        "name": "MG Road / Brigade Road",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.975,
        "lon": 77.607,
        "peak_attraction": 3000,
        "peak_production": 1500,
    },
    {
        "name": "Shivajinagar Market",
        "type": "commercial",
        "profile": "commercial",
        "lat": 12.985,
        "lon": 77.600,
        "peak_attraction": 2500,
        "peak_production": 1200,
    },
    # =========================================================================
    # TRANSPORT HUBS (8 zones) — Bidirectional, high throughput
    # =========================================================================
    {
        "name": "Majestic (KSR Station + Bus)",
        "type": "transport",
        "profile": "transport",
        "lat": 12.977,
        "lon": 77.572,
        "peak_attraction": 5000,
        "peak_production": 5000,
    },
    {
        "name": "Yeshwantpur Railway Station",
        "type": "transport",
        "profile": "transport",
        "lat": 13.023,
        "lon": 77.546,
        "peak_attraction": 2500,
        "peak_production": 2500,
    },
    {
        "name": "KR Puram Railway Station",
        "type": "transport",
        "profile": "transport",
        "lat": 13.001,
        "lon": 77.697,
        "peak_attraction": 2000,
        "peak_production": 2000,
    },
    {
        "name": "Bangalore Cantonment Station",
        "type": "transport",
        "profile": "transport",
        "lat": 12.992,
        "lon": 77.596,
        "peak_attraction": 1500,
        "peak_production": 1500,
    },
    {
        "name": "Kempegowda Bus Station",
        "type": "transport",
        "profile": "transport",
        "lat": 12.978,
        "lon": 77.571,
        "peak_attraction": 3000,
        "peak_production": 3000,
    },
    {
        "name": "Shivajinagar Bus Station",
        "type": "transport",
        "profile": "transport",
        "lat": 12.988,
        "lon": 77.598,
        "peak_attraction": 2000,
        "peak_production": 2000,
    },
    {
        "name": "Whitefield Railway Station",
        "type": "transport",
        "profile": "transport",
        "lat": 12.977,
        "lon": 77.750,
        "peak_attraction": 1500,
        "peak_production": 1500,
    },
    {
        "name": "Kempegowda International Airport",
        "type": "transport",
        "profile": "transport",
        "lat": 13.199,
        "lon": 77.706,
        "peak_attraction": 3000,
        "peak_production": 3000,
    },
    # =========================================================================
    # HOSPITALS (6 zones) — Steady daytime demand
    # =========================================================================
    {
        "name": "Manipal Hospital (HAL)",
        "type": "hospital",
        "profile": "hospital",
        "lat": 12.959,
        "lon": 77.648,
        "peak_attraction": 1500,
        "peak_production": 500,
    },
    {
        "name": "NIMHANS",
        "type": "hospital",
        "profile": "hospital",
        "lat": 12.943,
        "lon": 77.593,
        "peak_attraction": 2000,
        "peak_production": 600,
    },
    {
        "name": "St Johns Medical College",
        "type": "hospital",
        "profile": "hospital",
        "lat": 12.930,
        "lon": 77.621,
        "peak_attraction": 1500,
        "peak_production": 500,
    },
    {
        "name": "Bangalore Medical College (Victoria)",
        "type": "hospital",
        "profile": "hospital",
        "lat": 12.965,
        "lon": 77.583,
        "peak_attraction": 1800,
        "peak_production": 500,
    },
    {
        "name": "MS Ramaiah Hospital",
        "type": "hospital",
        "profile": "hospital",
        "lat": 13.031,
        "lon": 77.564,
        "peak_attraction": 1200,
        "peak_production": 400,
    },
    {
        "name": "Columbia Asia (Hebbal)",
        "type": "hospital",
        "profile": "hospital",
        "lat": 13.040,
        "lon": 77.588,
        "peak_attraction": 1000,
        "peak_production": 300,
    },
    # =========================================================================
    # RESIDENTIAL CLUSTERS (20 zones) — High production AM, high attraction PM
    # =========================================================================
    {
        "name": "BTM Layout",
        "type": "residential",
        "profile": "residential",
        "lat": 12.916,
        "lon": 77.610,
        "peak_attraction": 1500,
        "peak_production": 4000,
    },
    {
        "name": "HSR Layout",
        "type": "residential",
        "profile": "residential",
        "lat": 12.908,
        "lon": 77.635,
        "peak_attraction": 1200,
        "peak_production": 3500,
    },
    {
        "name": "Koramangala",
        "type": "residential",
        "profile": "residential",
        "lat": 12.934,
        "lon": 77.626,
        "peak_attraction": 1500,
        "peak_production": 3000,
    },
    {
        "name": "Indiranagar",
        "type": "residential",
        "profile": "residential",
        "lat": 12.972,
        "lon": 77.641,
        "peak_attraction": 1200,
        "peak_production": 2800,
    },
    {
        "name": "Jayanagar",
        "type": "residential",
        "profile": "residential",
        "lat": 12.925,
        "lon": 77.582,
        "peak_attraction": 1000,
        "peak_production": 3000,
    },
    {
        "name": "JP Nagar",
        "type": "residential",
        "profile": "residential",
        "lat": 12.907,
        "lon": 77.585,
        "peak_attraction": 1000,
        "peak_production": 3500,
    },
    {
        "name": "Banashankari",
        "type": "residential",
        "profile": "residential",
        "lat": 12.920,
        "lon": 77.560,
        "peak_attraction": 1000,
        "peak_production": 3000,
    },
    {
        "name": "RT Nagar",
        "type": "residential",
        "profile": "residential",
        "lat": 13.021,
        "lon": 77.591,
        "peak_attraction": 800,
        "peak_production": 2500,
    },
    {
        "name": "Yelahanka",
        "type": "residential",
        "profile": "residential",
        "lat": 13.101,
        "lon": 77.595,
        "peak_attraction": 800,
        "peak_production": 2500,
    },
    {
        "name": "Whitefield Residential",
        "type": "residential",
        "profile": "residential",
        "lat": 12.970,
        "lon": 77.745,
        "peak_attraction": 1200,
        "peak_production": 3500,
    },
    {
        "name": "Sarjapur Road",
        "type": "residential",
        "profile": "residential",
        "lat": 12.895,
        "lon": 77.670,
        "peak_attraction": 1000,
        "peak_production": 3000,
    },
    {
        "name": "Bellandur",
        "type": "residential",
        "profile": "residential",
        "lat": 12.926,
        "lon": 77.672,
        "peak_attraction": 1000,
        "peak_production": 2800,
    },
    {
        "name": "Marathahalli",
        "type": "residential",
        "profile": "residential",
        "lat": 12.957,
        "lon": 77.700,
        "peak_attraction": 1000,
        "peak_production": 2500,
    },
    {
        "name": "Hebbal",
        "type": "residential",
        "profile": "residential",
        "lat": 13.043,
        "lon": 77.590,
        "peak_attraction": 800,
        "peak_production": 2000,
    },
    {
        "name": "Rajajinagar",
        "type": "residential",
        "profile": "residential",
        "lat": 13.001,
        "lon": 77.553,
        "peak_attraction": 800,
        "peak_production": 2500,
    },
    {
        "name": "Vijayanagar",
        "type": "residential",
        "profile": "residential",
        "lat": 12.971,
        "lon": 77.536,
        "peak_attraction": 700,
        "peak_production": 2000,
    },
    {
        "name": "Basavanagudi",
        "type": "residential",
        "profile": "residential",
        "lat": 12.943,
        "lon": 77.573,
        "peak_attraction": 700,
        "peak_production": 2000,
    },
    {
        "name": "Padmanabhanagar",
        "type": "residential",
        "profile": "residential",
        "lat": 12.912,
        "lon": 77.558,
        "peak_attraction": 600,
        "peak_production": 2000,
    },
    {
        "name": "Electronic City Residential",
        "type": "residential",
        "profile": "residential",
        "lat": 12.855,
        "lon": 77.650,
        "peak_attraction": 800,
        "peak_production": 2500,
    },
    {
        "name": "Hennur / Kalyan Nagar",
        "type": "residential",
        "profile": "residential",
        "lat": 13.030,
        "lon": 77.640,
        "peak_attraction": 800,
        "peak_production": 2500,
    },
    # =========================================================================
    # EDUCATIONAL INSTITUTIONS (8 zones)
    # =========================================================================
    {
        "name": "IISc Bangalore",
        "type": "education",
        "profile": "education",
        "lat": 13.021,
        "lon": 77.567,
        "peak_attraction": 2000,
        "peak_production": 500,
    },
    {
        "name": "Christ University",
        "type": "education",
        "profile": "education",
        "lat": 12.935,
        "lon": 77.605,
        "peak_attraction": 2500,
        "peak_production": 600,
    },
    {
        "name": "RV College of Engineering",
        "type": "education",
        "profile": "education",
        "lat": 12.924,
        "lon": 77.499,
        "peak_attraction": 1500,
        "peak_production": 400,
    },
    {
        "name": "BMS College of Engineering",
        "type": "education",
        "profile": "education",
        "lat": 12.941,
        "lon": 77.565,
        "peak_attraction": 1500,
        "peak_production": 400,
    },
    {
        "name": "PES University",
        "type": "education",
        "profile": "education",
        "lat": 12.934,
        "lon": 77.535,
        "peak_attraction": 1800,
        "peak_production": 450,
    },
    {
        "name": "Jain University (JC Road)",
        "type": "education",
        "profile": "education",
        "lat": 12.956,
        "lon": 77.583,
        "peak_attraction": 1200,
        "peak_production": 300,
    },
    {
        "name": "Bangalore University",
        "type": "education",
        "profile": "education",
        "lat": 12.938,
        "lon": 77.508,
        "peak_attraction": 1500,
        "peak_production": 400,
    },
    {
        "name": "Indian Institute of Management",
        "type": "education",
        "profile": "education",
        "lat": 12.913,
        "lon": 77.593,
        "peak_attraction": 1000,
        "peak_production": 250,
    },
    # =========================================================================
    # MALLS / ENTERTAINMENT (5 zones)
    # =========================================================================
    {
        "name": "Phoenix Marketcity (Whitefield)",
        "type": "entertainment",
        "profile": "entertainment",
        "lat": 12.997,
        "lon": 77.697,
        "peak_attraction": 2500,
        "peak_production": 500,
    },
    {
        "name": "Forum Mall (Koramangala)",
        "type": "entertainment",
        "profile": "entertainment",
        "lat": 12.935,
        "lon": 77.612,
        "peak_attraction": 2000,
        "peak_production": 400,
    },
    {
        "name": "Orion Mall (Rajajinagar)",
        "type": "entertainment",
        "profile": "entertainment",
        "lat": 13.010,
        "lon": 77.555,
        "peak_attraction": 2000,
        "peak_production": 400,
    },
    {
        "name": "Mantri Square (Malleswaram)",
        "type": "entertainment",
        "profile": "entertainment",
        "lat": 12.993,
        "lon": 77.570,
        "peak_attraction": 1800,
        "peak_production": 350,
    },
    {
        "name": "VR Bengaluru (Whitefield)",
        "type": "entertainment",
        "profile": "entertainment",
        "lat": 12.993,
        "lon": 77.709,
        "peak_attraction": 1500,
        "peak_production": 300,
    },
    # =========================================================================
    # INDUSTRIAL AREAS (8 zones) — Early morning shift patterns
    # =========================================================================
    {
        "name": "Peenya Industrial Area",
        "type": "industrial",
        "profile": "industrial",
        "lat": 13.032,
        "lon": 77.520,
        "peak_attraction": 3000,
        "peak_production": 800,
    },
    {
        "name": "Bommasandra Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 12.815,
        "lon": 77.695,
        "peak_attraction": 2000,
        "peak_production": 500,
    },
    {
        "name": "Jigani Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 12.788,
        "lon": 77.650,
        "peak_attraction": 1500,
        "peak_production": 400,
    },
    {
        "name": "Bidadi Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 12.800,
        "lon": 77.385,
        "peak_attraction": 1200,
        "peak_production": 300,
    },
    {
        "name": "Hoskote Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 13.070,
        "lon": 77.795,
        "peak_attraction": 1000,
        "peak_production": 250,
    },
    {
        "name": "Nelamangala Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 13.098,
        "lon": 77.393,
        "peak_attraction": 800,
        "peak_production": 200,
    },
    {
        "name": "Dobaspet Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 13.158,
        "lon": 77.340,
        "peak_attraction": 600,
        "peak_production": 150,
    },
    {
        "name": "Whitefield Industrial",
        "type": "industrial",
        "profile": "industrial",
        "lat": 12.980,
        "lon": 77.760,
        "peak_attraction": 1500,
        "peak_production": 400,
    },
]


# =============================================================================
# 3. ZONE UTILITIES
# =============================================================================


def get_zone_count() -> int:
    """Return the total number of traffic zones."""
    return len(TRAFFIC_ZONES)


def get_demand_at_hour(zone: dict, hour: int, direction: str = "attraction") -> float:
    """Get the demand (PCU/hr) for a zone at a specific hour.

    Args:
        zone: Zone dict from TRAFFIC_ZONES.
        hour: Hour of day (0-23).
        direction: 'attraction' or 'production'.

    Returns:
        Demand in PCU/hr at the specified hour.
    """
    profile = TEMPORAL_PROFILES[zone["profile"]]
    multiplier = profile[hour]
    peak = zone[f"peak_{direction}"]
    return peak * multiplier


def get_all_demands_at_hour(hour: int) -> tuple[np.ndarray, np.ndarray]:
    """Get production and attraction arrays for all zones at a given hour.

    Args:
        hour: Hour of day (0-23).

    Returns:
        Tuple of (productions, attractions) arrays, shape (N_zones,).
    """
    n = len(TRAFFIC_ZONES)
    productions = np.zeros(n, dtype=np.float64)
    attractions = np.zeros(n, dtype=np.float64)

    for i, zone in enumerate(TRAFFIC_ZONES):
        productions[i] = get_demand_at_hour(zone, hour, "production")
        attractions[i] = get_demand_at_hour(zone, hour, "attraction")

    return productions, attractions


def snap_zones_to_network(
    zones: list[dict],
    osm_graph: object,
) -> list[int]:
    """Snap each zone to the nearest OSM node in the road graph.

    Args:
        zones: List of zone dicts with lat/lon.
        osm_graph: NetworkX graph with node positions.

    Returns:
        List of OSM node IDs, one per zone.
    """
    # Build KD-tree of OSM node positions
    node_ids = list(osm_graph.nodes())
    positions = np.array(
        [
            [
                float(osm_graph.nodes[n].get("y", osm_graph.nodes[n].get("lat", 0))),
                float(osm_graph.nodes[n].get("x", osm_graph.nodes[n].get("lon", 0))),
            ]
            for n in node_ids
        ]
    )

    # Snap each zone to nearest node
    from scipy.spatial import cKDTree

    tree = cKDTree(positions)
    zone_nodes = []

    for zone in zones:
        query_point = [zone["lat"], zone["lon"]]
        _, idx = tree.query(query_point)
        zone_nodes.append(node_ids[idx])

    logger.info(
        "Snapped %d zones to OSM nodes (max dist check in degrees)",
        len(zone_nodes),
    )

    return zone_nodes


def summarize_zones() -> dict:
    """Return a summary of traffic zone statistics.

    Returns:
        Dict with zone counts, total demand, etc.
    """
    by_type: dict[str, int] = {}
    total_peak_attraction = 0
    total_peak_production = 0

    for zone in TRAFFIC_ZONES:
        t = zone["type"]
        by_type[t] = by_type.get(t, 0) + 1
        total_peak_attraction += zone["peak_attraction"]
        total_peak_production += zone["peak_production"]

    return {
        "total_zones": len(TRAFFIC_ZONES),
        "by_type": by_type,
        "total_peak_attraction": total_peak_attraction,
        "total_peak_production": total_peak_production,
    }


def generate_auto_zones(
    osm_graph: object,
    grid_size: float | None = None,
    min_nodes: int | None = None,
) -> tuple[list[dict], list[int]]:
    """Auto-generate traffic zones from OSM network density.

    Divides the city into a grid. Each cell with enough OSM nodes becomes
    a zone with trip generation proportional to node density (proxy for
    development intensity).

    This produces 300-500 zones, spreading demand across the network
    instead of funneling through 80 landmark corridors.

    Args:
        osm_graph: NetworkX graph with node positions (y=lat, x=lon).
        grid_size: Grid cell size in degrees (~0.008 = 0.9 km).
        min_nodes: Minimum nodes in a cell to create a zone.

    Returns:
        Tuple of (auto_zones list of dicts, snapped node IDs).
    """
    from drishtam.config import (
        AUTO_ZONE_BASE_ATTRACTION,
        AUTO_ZONE_BASE_PRODUCTION,
        AUTO_ZONE_DENSITY_SCALE,
        AUTO_ZONE_GRID_SIZE,
        AUTO_ZONE_MIN_NODES,
    )

    if grid_size is None:
        grid_size = AUTO_ZONE_GRID_SIZE
    if min_nodes is None:
        min_nodes = AUTO_ZONE_MIN_NODES

    # Extract node positions
    node_ids = list(osm_graph.nodes())
    lats = np.array(
        [float(osm_graph.nodes[n].get("y", osm_graph.nodes[n].get("lat", 0)))
         for n in node_ids]
    )
    lons = np.array(
        [float(osm_graph.nodes[n].get("x", osm_graph.nodes[n].get("lon", 0)))
         for n in node_ids]
    )

    # Compute grid bounds
    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()

    # Assign each node to a grid cell
    lat_bins = np.arange(lat_min, lat_max + grid_size, grid_size)
    lon_bins = np.arange(lon_min, lon_max + grid_size, grid_size)

    lat_idx = np.digitize(lats, lat_bins) - 1
    lon_idx = np.digitize(lons, lon_bins) - 1

    # Count nodes per cell and find centroid
    from collections import defaultdict
    cell_nodes: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (li, lo) in enumerate(zip(lat_idx, lon_idx)):
        cell_nodes[(li, lo)].append(i)

    # Create zones for cells with enough nodes
    auto_zones: list[dict] = []
    zone_node_ids: list[int] = []

    from scipy.spatial import cKDTree
    positions = np.column_stack([lats, lons])
    tree = cKDTree(positions)

    for (li, lo), indices in cell_nodes.items():
        if len(indices) < min_nodes:
            continue

        # Cell centroid
        cell_lats = lats[indices]
        cell_lons = lons[indices]
        centroid_lat = float(cell_lats.mean())
        centroid_lon = float(cell_lons.mean())

        # Snap to nearest actual node
        _, nearest_idx = tree.query([centroid_lat, centroid_lon])
        osm_node_id = node_ids[nearest_idx]

        # Skip if this node is already used
        if osm_node_id in zone_node_ids:
            continue

        # Demand proportional to density
        n_nodes = len(indices)
        density_bonus = (n_nodes / 100.0) * AUTO_ZONE_DENSITY_SCALE

        # Classify as residential vs commercial based on density
        # High density = more commercial-like (attraction), low = residential (production)
        median_density = 150  # rough median for Bangalore
        if n_nodes > median_density:
            # Dense area = commercial/office (high attraction)
            profile = "commercial"
            zone_type = "auto_commercial"
            attraction = AUTO_ZONE_BASE_ATTRACTION + density_bonus * 1.5
            production = AUTO_ZONE_BASE_PRODUCTION + density_bonus * 0.5
        else:
            # Sparse area = residential (high production)
            profile = "residential"
            zone_type = "auto_residential"
            attraction = AUTO_ZONE_BASE_ATTRACTION + density_bonus * 0.5
            production = AUTO_ZONE_BASE_PRODUCTION + density_bonus * 1.5

        auto_zones.append({
            "name": f"Grid_{li}_{lo}",
            "type": zone_type,
            "profile": profile,
            "lat": centroid_lat,
            "lon": centroid_lon,
            "peak_attraction": int(attraction),
            "peak_production": int(production),
            "node_count": n_nodes,
        })
        zone_node_ids.append(osm_node_id)

    logger.info(
        "Auto-generated %d grid zones (grid=%.4f°, min_nodes=%d)",
        len(auto_zones),
        grid_size,
        min_nodes,
    )
    logger.info(
        "  Total peak attraction: %d, production: %d",
        sum(z["peak_attraction"] for z in auto_zones),
        sum(z["peak_production"] for z in auto_zones),
    )

    return auto_zones, zone_node_ids


def get_combined_zones(
    osm_graph: object,
) -> tuple[list[dict], list[int]]:
    """Get combined landmark + auto-generated zones.

    Merges the 80 curated landmark zones with 300+ auto-generated
    grid zones for comprehensive demand coverage.

    Args:
        osm_graph: NetworkX graph.

    Returns:
        Tuple of (all_zones, all_node_ids).
    """
    # 1. Landmark zones
    landmark_nodes = snap_zones_to_network(TRAFFIC_ZONES, osm_graph)

    # 2. Auto zones
    auto_zones, auto_node_ids = generate_auto_zones(osm_graph)

    # 3. Remove auto zones that overlap with landmarks (within ~200m)
    from scipy.spatial import cKDTree

    landmark_positions = np.array([
        [z["lat"], z["lon"]] for z in TRAFFIC_ZONES
    ])
    landmark_tree = cKDTree(landmark_positions)

    filtered_auto_zones = []
    filtered_auto_nodes = []
    overlap_count = 0

    for zone, node_id in zip(auto_zones, auto_node_ids):
        dist, _ = landmark_tree.query([zone["lat"], zone["lon"]])
        if dist > 0.002:  # ~200m in degrees
            filtered_auto_zones.append(zone)
            filtered_auto_nodes.append(node_id)
        else:
            overlap_count += 1

    # Combine
    all_zones = list(TRAFFIC_ZONES) + filtered_auto_zones
    all_nodes = landmark_nodes + filtered_auto_nodes

    logger.info(
        "Combined zones: %d landmark + %d auto = %d total (%d overlaps removed)",
        len(TRAFFIC_ZONES),
        len(filtered_auto_zones),
        len(all_zones),
        overlap_count,
    )

    return all_zones, all_nodes

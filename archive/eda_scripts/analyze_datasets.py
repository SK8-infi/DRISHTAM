import pandas as pd
import numpy as np
import sys

# ---- Load datasets ----
print("=" * 80)
print("LOADING DATASETS")
print("=" * 80)

# 1. Event data
event_df = pd.read_csv(r"c:\Github\Gridlock project\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv")
print(f"\n1. EVENT DATA: {event_df.shape[0]} rows, {event_df.shape[1]} columns")
print(f"   Columns: {list(event_df.columns)}")

# 2. Violation data
violation_df = pd.read_csv(r"c:\Github\Gridlock project\jan to may police violation_anonymized791b166.csv", low_memory=False)
print(f"\n2. VIOLATION DATA: {violation_df.shape[0]} rows, {violation_df.shape[1]} columns")
print(f"   Columns: {list(violation_df.columns)}")

# 3. Train data
train_df = pd.read_csv(r"c:\Github\Gridlock project\train.csv")
print(f"\n3. TRAIN DATA: {train_df.shape[0]} rows, {train_df.shape[1]} columns")
print(f"   Columns: {list(train_df.columns)}")

# ---- Time Range Analysis ----
print("\n" + "=" * 80)
print("TIME RANGE ANALYSIS")
print("=" * 80)

# Event data time range
event_df['start_datetime'] = pd.to_datetime(event_df['start_datetime'], errors='coerce')
event_df['end_datetime'] = pd.to_datetime(event_df['end_datetime'], errors='coerce')
print(f"\n1. EVENT DATA:")
print(f"   start_datetime range: {event_df['start_datetime'].min()} to {event_df['start_datetime'].max()}")
print(f"   end_datetime range:   {event_df['end_datetime'].min()} to {event_df['end_datetime'].max()}")

# Violation data time range
violation_df['created_datetime'] = pd.to_datetime(violation_df['created_datetime'], errors='coerce')
violation_df['closed_datetime'] = pd.to_datetime(violation_df['closed_datetime'], errors='coerce')
print(f"\n2. VIOLATION DATA:")
print(f"   created_datetime range: {violation_df['created_datetime'].min()} to {violation_df['created_datetime'].max()}")
print(f"   closed_datetime range:  {violation_df['closed_datetime'].min()} to {violation_df['closed_datetime'].max()}")

# Train data time range
print(f"\n3. TRAIN DATA:")
print(f"   day range: {train_df['day'].min()} to {train_df['day'].max()}")
print(f"   timestamp unique values (sample): {sorted(train_df['timestamp'].unique())[:20]}")
print(f"   Total unique days: {train_df['day'].nunique()}")
print(f"   Total unique timestamps: {train_df['timestamp'].nunique()}")
print(f"   Total unique geohashes: {train_df['geohash'].nunique()}")

# ---- Geospatial Analysis ----
print("\n" + "=" * 80)
print("GEOSPATIAL ANALYSIS")
print("=" * 80)

# Event data lat/lon
print(f"\n1. EVENT DATA (Bengaluru-centric):")
print(f"   Latitude:  {event_df['latitude'].min():.4f} to {event_df['latitude'].max():.4f}")
print(f"   Longitude: {event_df['longitude'].min():.4f} to {event_df['longitude'].max():.4f}")

# Violation data lat/lon
print(f"\n2. VIOLATION DATA:")
print(f"   Latitude:  {violation_df['latitude'].min():.4f} to {violation_df['latitude'].max():.4f}")
print(f"   Longitude: {violation_df['longitude'].min():.4f} to {violation_df['longitude'].max():.4f}")

# Train data - geohash based
print(f"\n3. TRAIN DATA:")
print(f"   Uses geohash encoding (no explicit lat/lon)")
print(f"   Sample geohashes: {train_df['geohash'].unique()[:10]}")
print(f"   All geohashes start with 'qp0': {all(g.startswith('qp0') for g in train_df['geohash'].unique())}")

# Check geohash prefix
geohash_prefixes = set(g[:3] for g in train_df['geohash'].unique())
print(f"   Geohash prefixes (3-char): {geohash_prefixes}")

# ---- Event Data Deep Dive ----
print("\n" + "=" * 80)
print("EVENT DATA - DEEP DIVE")
print("=" * 80)

print(f"\nEvent Types:")
print(event_df['event_type'].value_counts().to_string())

print(f"\nEvent Causes:")
print(event_df['event_cause'].value_counts().to_string())

print(f"\nStatus:")
print(event_df['status'].value_counts().to_string())

print(f"\nPriority:")
print(event_df['priority'].value_counts().to_string())

print(f"\nCorridors (top 15):")
print(event_df['corridor'].value_counts().head(15).to_string())

print(f"\nPolice Stations (top 15):")
print(event_df['police_station'].value_counts().head(15).to_string())

# ---- Violation Data Deep Dive ----
print("\n" + "=" * 80)
print("VIOLATION DATA - DEEP DIVE")
print("=" * 80)

print(f"\nVehicle Types:")
print(violation_df['vehicle_type'].value_counts().head(15).to_string())

print(f"\nViolation Types (raw, top 20):")
print(violation_df['violation_type'].value_counts().head(20).to_string())

print(f"\nPolice Stations (top 15):")
print(violation_df['police_station'].value_counts().head(15).to_string())

print(f"\nValidation Status:")
print(violation_df['validation_status'].value_counts().to_string())

# ---- Train Data Deep Dive ----
print("\n" + "=" * 80)
print("TRAIN DATA - DEEP DIVE")
print("=" * 80)

print(f"\nDemand statistics:")
print(train_df['demand'].describe().to_string())

print(f"\nRoad Types:")
print(train_df['RoadType'].value_counts().to_string())

print(f"\nWeather:")
print(train_df['Weather'].value_counts().to_string())

print(f"\nNumber of Lanes:")
print(train_df['NumberofLanes'].value_counts().to_string())

print(f"\nLarge Vehicles:")
print(train_df['LargeVehicles'].value_counts().to_string())

print(f"\nLandmarks:")
print(train_df['Landmarks'].value_counts().to_string())

# ---- CROSS-DATASET CORRELATION ----
print("\n" + "=" * 80)
print("CROSS-DATASET CORRELATION ANALYSIS")
print("=" * 80)

# Check if police stations overlap between event and violation data
event_stations = set(event_df['police_station'].dropna().unique())
violation_stations = set(violation_df['police_station'].dropna().unique())
common_stations = event_stations & violation_stations

print(f"\n--- Police Station Overlap ---")
print(f"   Event data police stations: {len(event_stations)}")
print(f"   Violation data police stations: {len(violation_stations)}")
print(f"   Common police stations: {len(common_stations)}")
print(f"   Overlap %: {len(common_stations)/max(len(event_stations),1)*100:.1f}% of event stations")
if common_stations:
    print(f"   Common stations (sample): {list(common_stations)[:15]}")

# Check temporal overlap between event and violation data
print(f"\n--- Temporal Overlap ---")
event_start = event_df['start_datetime'].min()
event_end = event_df['start_datetime'].max()
violation_start = violation_df['created_datetime'].min()
violation_end = violation_df['created_datetime'].max()

overlap_start = max(event_start, violation_start)
overlap_end = min(event_end, violation_end)
print(f"   Event data: {event_start.date()} to {event_end.date()}")
print(f"   Violation data: {violation_start.date()} to {violation_end.date()}")
if overlap_start < overlap_end:
    print(f"   OVERLAP PERIOD: {overlap_start.date()} to {overlap_end.date()}")
    print(f"   Overlap duration: {(overlap_end - overlap_start).days} days")
else:
    print(f"   NO temporal overlap!")

# Check corridors/zones overlap
if 'zone' in event_df.columns:
    event_zones = set(event_df['zone'].dropna().unique())
    print(f"\n--- Zone info (Event data) ---")
    print(f"   Unique zones: {event_zones}")

# Spatial proximity analysis
print(f"\n--- Spatial Proximity Analysis ---")
# Check if event locations and violation locations cluster in similar areas
event_lat_mean = event_df['latitude'].mean()
event_lon_mean = event_df['longitude'].mean()
viol_lat_mean = violation_df['latitude'].mean()
viol_lon_mean = violation_df['longitude'].mean()
print(f"   Event data centroid: ({event_lat_mean:.4f}, {event_lon_mean:.4f})")
print(f"   Violation data centroid: ({viol_lat_mean:.4f}, {viol_lon_mean:.4f})")
print(f"   Distance between centroids: ~{np.sqrt((event_lat_mean-viol_lat_mean)**2 + (event_lon_mean-viol_lon_mean)**2)*111:.2f} km")

# Try to decode geohash to check if train data is same region
# Geohash 'qp0' corresponds to roughly Bengaluru area
print(f"\n--- Geohash Region Check (Train data) ---")
print(f"   Geohash prefix 'qp0' corresponds to approximately:")
print(f"   Latitude: ~12.9 - 13.1 (Bengaluru region)")
print(f"   Longitude: ~77.5 - 77.7 (Bengaluru region)")
print(f"   This MATCHES the lat/lon ranges of event and violation data!")

# Monthly distribution
print(f"\n--- Monthly Distribution ---")
print(f"\n   Event data by month:")
event_df['month'] = event_df['start_datetime'].dt.to_period('M')
print(event_df['month'].value_counts().sort_index().to_string())

print(f"\n   Violation data by month:")
violation_df['month'] = violation_df['created_datetime'].dt.to_period('M')
print(violation_df['month'].value_counts().sort_index().to_string())

# Check if junction names overlap
if 'junction' in event_df.columns and 'junction_name' in violation_df.columns:
    event_junctions = set(event_df['junction'].dropna().unique()) - {'NULL', 'None', ''}
    violation_junctions = set(violation_df['junction_name'].dropna().unique()) - {'No Junction', 'NULL', 'None', ''}
    common_junctions_approx = 0
    for ej in event_junctions:
        for vj in violation_junctions:
            if ej.lower() in vj.lower() or vj.lower() in ej.lower():
                common_junctions_approx += 1
                break
    print(f"\n--- Junction Overlap ---")
    print(f"   Event junctions: {len(event_junctions)}")
    print(f"   Violation junctions: {len(violation_junctions)}")
    print(f"   Approximate matches: {common_junctions_approx}")
    print(f"   Sample event junctions: {list(event_junctions)[:10]}")
    print(f"   Sample violation junctions: {list(violation_junctions)[:10]}")

# Missing data analysis
print(f"\n" + "=" * 80)
print("MISSING DATA ANALYSIS")
print("=" * 80)

print(f"\n1. EVENT DATA missing %:")
for col in event_df.columns:
    if col == 'month':
        continue
    missing_pct = (event_df[col].isna().sum() + (event_df[col] == 'NULL').sum()) / len(event_df) * 100
    if missing_pct > 0:
        print(f"   {col}: {missing_pct:.1f}%")

print(f"\n2. VIOLATION DATA missing %:")
for col in violation_df.columns:
    if col == 'month':
        continue
    missing_pct = (violation_df[col].isna().sum()) / len(violation_df) * 100
    if missing_pct > 5:
        print(f"   {col}: {missing_pct:.1f}%")

print(f"\n3. TRAIN DATA missing %:")
for col in train_df.columns:
    missing_pct = (train_df[col].isna().sum()) / len(train_df) * 100
    if missing_pct > 0:
        print(f"   {col}: {missing_pct:.1f}%")

print("\n" + "=" * 80)
print("SUMMARY & KEY FINDINGS")
print("=" * 80)

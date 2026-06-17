"""
EDA #4: OSM Road Network + Violation Mapping
==============================================
Download Bengaluru road network, map violations to nearest roads,
analyze which road types/widths/capacities are most affected.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy.spatial import cKDTree
import warnings
warnings.filterwarnings('ignore')

import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point

# ---- Config ----
VIOLATION_PATH = r"c:\Github\Gridlock project\jan to may police violation_anonymized791b166.csv"
RESEARCH_DIR = Path(r"c:\Github\Gridlock project\research")
DATA_DIR = Path(r"c:\Github\Gridlock project\data")
DATA_DIR.mkdir(exist_ok=True)

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
DPI = 150

def save_fig(name, fig=None):
    if fig is None:
        fig = plt.gcf()
    path = RESEARCH_DIR / f"04_{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  > Saved: {path.name}")

# ---- Load Violations ----
print("=" * 70)
print("EDA #4: OSM ROAD NETWORK + VIOLATION MAPPING")
print("=" * 70)

print("\nLoading violation data...")
viol_df = pd.read_csv(VIOLATION_PATH, low_memory=False)
viol_df['created_datetime'] = pd.to_datetime(viol_df['created_datetime'], errors='coerce')
viol_df = viol_df.dropna(subset=['created_datetime']).copy()
viol_df = viol_df[(viol_df['latitude'] > 12.7) & (viol_df['latitude'] < 13.4) &
                   (viol_df['longitude'] > 77.3) & (viol_df['longitude'] < 77.9)].copy()
print(f"  Violations loaded: {len(viol_df):,}")

# ---- Download OSM Road Network ----
print("\n" + "-" * 70)
print("1. DOWNLOADING BENGALURU ROAD NETWORK FROM OSM")
print("-" * 70)

osm_cache = DATA_DIR / "bengaluru_roads.graphml"
if osm_cache.exists():
    print("  Loading cached road network...")
    G = ox.load_graphml(osm_cache)
else:
    print("  Downloading from OpenStreetMap...")
    # Try multiple Overpass endpoints
    endpoints = [
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    ]
    G = None
    for endpoint in endpoints:
        try:
            print(f"  Trying: {endpoint}")
            ox.settings.overpass_url = endpoint
            ox.settings.timeout = 300
            ox.settings.overpass_rate_limit = False
            G = ox.graph_from_place(
                "Bengaluru, Karnataka, India",
                network_type='drive',
                simplify=True
            )
            print(f"  SUCCESS with {endpoint}")
            break
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")
            continue
    
    if G is None:
        print("  All endpoints failed. Trying bbox with smaller area...")
        ox.settings.overpass_url = "https://lz4.overpass-api.de/api/interpreter"
        # Use tighter bbox around core violation area
        G = ox.graph_from_bbox(
            bbox=(13.10, 12.85, 77.70, 77.50),
            network_type='drive',
            simplify=True
        )
    
    ox.save_graphml(G, osm_cache)
    print(f"  Saved to cache: {osm_cache}")

# Convert to GeoDataFrames
nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
print(f"\n  Road network stats:")
print(f"    Nodes: {len(nodes):,}")
print(f"    Edges (road segments): {len(edges):,}")
print(f"    Total road length: {edges['length'].sum()/1000:.1f} km")

# ---- Analyze Road Classification ----
print("\n" + "-" * 70)
print("2. ROAD CLASSIFICATION ANALYSIS")
print("-" * 70)

# Clean highway column (can be list or string)
def get_highway_type(val):
    if isinstance(val, list):
        return val[0]
    return val

edges['highway_type'] = edges['highway'].apply(get_highway_type)

# Road type distribution
road_types = edges.groupby('highway_type').agg(
    count=('length', 'count'),
    total_km=('length', 'sum')
).sort_values('total_km', ascending=False)
road_types['total_km'] = road_types['total_km'] / 1000

print("\n  Road type distribution:")
for rtype, row in road_types.head(15).iterrows():
    print(f"    {rtype:25s} | {int(row['count']):>5,} segments | {row['total_km']:>7.1f} km")

# Define road hierarchy with estimated capacity
ROAD_HIERARCHY = {
    'motorway': {'tier': 1, 'name': 'Expressway', 'est_lanes': 6, 'est_width_m': 25},
    'motorway_link': {'tier': 1, 'name': 'Expressway Ramp', 'est_lanes': 2, 'est_width_m': 8},
    'trunk': {'tier': 2, 'name': 'Arterial', 'est_lanes': 4, 'est_width_m': 18},
    'trunk_link': {'tier': 2, 'name': 'Arterial Ramp', 'est_lanes': 2, 'est_width_m': 8},
    'primary': {'tier': 3, 'name': 'Primary', 'est_lanes': 4, 'est_width_m': 14},
    'primary_link': {'tier': 3, 'name': 'Primary Ramp', 'est_lanes': 2, 'est_width_m': 7},
    'secondary': {'tier': 4, 'name': 'Secondary', 'est_lanes': 2, 'est_width_m': 10},
    'secondary_link': {'tier': 4, 'name': 'Secondary Ramp', 'est_lanes': 2, 'est_width_m': 7},
    'tertiary': {'tier': 5, 'name': 'Tertiary', 'est_lanes': 2, 'est_width_m': 8},
    'tertiary_link': {'tier': 5, 'name': 'Tertiary Ramp', 'est_lanes': 1, 'est_width_m': 5},
    'residential': {'tier': 6, 'name': 'Residential', 'est_lanes': 2, 'est_width_m': 6},
    'living_street': {'tier': 7, 'name': 'Living Street', 'est_lanes': 1, 'est_width_m': 4},
    'unclassified': {'tier': 6, 'name': 'Unclassified', 'est_lanes': 2, 'est_width_m': 6},
    'service': {'tier': 8, 'name': 'Service', 'est_lanes': 1, 'est_width_m': 4},
}

# Parse lanes from OSM data
def get_lanes(row):
    """Get number of lanes from OSM data or estimate from road type."""
    val = row.get('lanes')
    if val is not None:
        if isinstance(val, (list, np.ndarray)):
            val = val[0]
        try:
            if pd.notna(val):
                return int(val)
        except (ValueError, TypeError):
            pass
    # Fallback to estimate
    info = ROAD_HIERARCHY.get(row['highway_type'], {'est_lanes': 2})
    return info['est_lanes']

edges['lanes_parsed'] = edges.apply(get_lanes, axis=1)

# Parse width
def get_width(row):
    """Get road width from OSM or estimate."""
    val = row.get('width')
    if val is not None:
        if isinstance(val, (list, np.ndarray)):
            val = val[0]
        try:
            if pd.notna(val):
                return float(str(val).replace('m', '').strip())
        except (ValueError, TypeError):
            pass
    info = ROAD_HIERARCHY.get(row['highway_type'], {'est_width_m': 6})
    return info['est_width_m']

edges['width_parsed'] = edges.apply(get_width, axis=1)

# Get road tier
edges['road_tier'] = edges['highway_type'].map(
    {k: v['tier'] for k, v in ROAD_HIERARCHY.items()}
).fillna(6).astype(int)
edges['road_tier_name'] = edges['highway_type'].map(
    {k: v['name'] for k, v in ROAD_HIERARCHY.items()}
).fillna('Other')

# Lane data availability
lanes_from_osm = edges['lanes'].notna().sum()
print(f"\n  Lanes data from OSM: {lanes_from_osm:,} / {len(edges):,} ({lanes_from_osm/len(edges)*100:.1f}%)")
print(f"  Width data from OSM: {edges['width'].notna().sum():,} / {len(edges):,}")

lane_dist = edges.groupby('lanes_parsed')['length'].agg(['count', 'sum'])
lane_dist['sum_km'] = lane_dist['sum'] / 1000
print("\n  Lane distribution:")
for lanes, row in lane_dist.iterrows():
    print(f"    {lanes} lanes | {int(row['count']):>6,} segments | {row['sum_km']:>7.1f} km")

# Fig 1: Road type distribution
fig, axes = plt.subplots(1, 2, figsize=(20, 9))

top_types = road_types.head(10)
colors_r = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(top_types)))
axes[0].barh(range(len(top_types)), top_types['total_km'], color=colors_r)
axes[0].set_yticks(range(len(top_types)))
axes[0].set_yticklabels(top_types.index, fontsize=11)
axes[0].set_xlabel('Total Length (km)', fontsize=13)
axes[0].set_title('Road Types by Total Length', fontsize=14, fontweight='bold')
axes[0].invert_yaxis()
for i, val in enumerate(top_types['total_km']):
    axes[0].text(val + 5, i, f'{val:.0f} km', va='center', fontsize=9)

# Lane distribution pie
lane_summary = edges.groupby('lanes_parsed')['length'].sum() / 1000
lane_summary = lane_summary.sort_values(ascending=False)
axes[1].pie(lane_summary.values, labels=[f'{int(l)} lanes' for l in lane_summary.index],
            autopct='%1.1f%%', colors=sns.color_palette("Set2", len(lane_summary)),
            textprops={'fontsize': 11})
axes[1].set_title('Road Network by Lane Count', fontsize=14, fontweight='bold')

plt.suptitle('Bengaluru Road Network Classification (from OSM)', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("road_classification")

# ---- Map Violations to Nearest Road ----
print("\n" + "-" * 70)
print("3. MAPPING VIOLATIONS TO NEAREST ROAD SEGMENTS")
print("-" * 70)

# Get edge midpoints for spatial matching
edge_midpoints = edges.copy()
edge_midpoints['mid_lat'] = edge_midpoints.geometry.apply(
    lambda g: g.interpolate(0.5, normalized=True).y
)
edge_midpoints['mid_lon'] = edge_midpoints.geometry.apply(
    lambda g: g.interpolate(0.5, normalized=True).x
)

# Build KD-tree on edge midpoints
lat_to_m = 111000
lon_to_m = 108000

edge_coords = np.column_stack([
    edge_midpoints['mid_lat'].values * lat_to_m,
    edge_midpoints['mid_lon'].values * lon_to_m
])
viol_coords = np.column_stack([
    viol_df['latitude'].values * lat_to_m,
    viol_df['longitude'].values * lon_to_m
])

print("  Building spatial index on road segments...")
tree = cKDTree(edge_coords)

print("  Finding nearest road for each violation...")
distances, indices = tree.query(viol_coords, k=1)

# Convert distance to meters (already in meters from our scaling)
viol_df = viol_df.copy()
viol_df['nearest_road_idx'] = indices
viol_df['dist_to_road_m'] = distances

# Map road attributes
edge_idx = edge_midpoints.index.values
viol_df['road_type'] = edge_midpoints.iloc[indices]['highway_type'].values
viol_df['road_tier'] = edge_midpoints.iloc[indices]['road_tier'].values
viol_df['road_tier_name'] = edge_midpoints.iloc[indices]['road_tier_name'].values
viol_df['road_lanes'] = edge_midpoints.iloc[indices]['lanes_parsed'].values
viol_df['road_width'] = edge_midpoints.iloc[indices]['width_parsed'].values
viol_df['road_length'] = edge_midpoints.iloc[indices]['length'].values

# Get road names
def get_name(val):
    if isinstance(val, list):
        return val[0]
    if pd.isna(val):
        return 'unnamed'
    return str(val)

edge_midpoints['road_name'] = edge_midpoints['name'].apply(get_name)
viol_df['road_name'] = edge_midpoints.iloc[indices]['road_name'].values

print(f"\n  Distance to nearest road stats:")
print(f"    Mean:   {viol_df['dist_to_road_m'].mean():.1f}m")
print(f"    Median: {viol_df['dist_to_road_m'].median():.1f}m")
print(f"    P95:    {viol_df['dist_to_road_m'].quantile(0.95):.1f}m")
print(f"    Max:    {viol_df['dist_to_road_m'].max():.1f}m")
print(f"    Within 50m: {(viol_df['dist_to_road_m'] <= 50).sum():,} ({(viol_df['dist_to_road_m'] <= 50).sum()/len(viol_df)*100:.1f}%)")
print(f"    Within 100m: {(viol_df['dist_to_road_m'] <= 100).sum():,} ({(viol_df['dist_to_road_m'] <= 100).sum()/len(viol_df)*100:.1f}%)")

# ---- Violations by Road Type ----
print("\n" + "-" * 70)
print("4. VIOLATIONS BY ROAD TYPE")
print("-" * 70)

viol_by_road = viol_df.groupby('road_type').agg(
    violation_count=('road_type', 'size'),
    mean_dist=('dist_to_road_m', 'mean')
).sort_values('violation_count', ascending=False)

total_road_km = road_types['total_km']
viol_by_road = viol_by_road.join(total_road_km, how='left')
viol_by_road['violations_per_km'] = viol_by_road['violation_count'] / viol_by_road['total_km']

print("\n  Violations by road type:")
print(f"  {'Road Type':25s} | {'Count':>8s} | {'% Total':>7s} | {'Road km':>7s} | {'Viols/km':>8s}")
print("  " + "-" * 70)
for rtype, row in viol_by_road.head(12).iterrows():
    pct = row['violation_count'] / len(viol_df) * 100
    viol_per_km = row['violations_per_km'] if pd.notna(row['violations_per_km']) else 0
    total_km = row['total_km'] if pd.notna(row['total_km']) else 0
    print(f"  {rtype:25s} | {int(row['violation_count']):>8,} | {pct:>6.1f}% | {total_km:>6.1f} | {viol_per_km:>8.1f}")

# Fig 2: Violations by road type
fig, axes = plt.subplots(1, 2, figsize=(20, 9))

top_road_viols = viol_by_road.head(8)
colors_rv = sns.color_palette("rocket", len(top_road_viols))
axes[0].barh(range(len(top_road_viols)), top_road_viols['violation_count'], color=colors_rv)
axes[0].set_yticks(range(len(top_road_viols)))
axes[0].set_yticklabels(top_road_viols.index, fontsize=11)
axes[0].set_xlabel('Number of Violations', fontsize=13)
axes[0].set_title('Violations by Road Type (Count)', fontsize=14, fontweight='bold')
axes[0].invert_yaxis()
for i, val in enumerate(top_road_viols['violation_count']):
    axes[0].text(val + 500, i, f'{int(val):,}', va='center', fontsize=9)

# Per-km density
top_density = viol_by_road[viol_by_road['violations_per_km'].notna()].sort_values('violations_per_km', ascending=False).head(8)
colors_d = sns.color_palette("flare", len(top_density))
axes[1].barh(range(len(top_density)), top_density['violations_per_km'], color=colors_d)
axes[1].set_yticks(range(len(top_density)))
axes[1].set_yticklabels(top_density.index, fontsize=11)
axes[1].set_xlabel('Violations per km of Road', fontsize=13)
axes[1].set_title('Violation DENSITY by Road Type (per km)', fontsize=14, fontweight='bold')
axes[1].invert_yaxis()
for i, val in enumerate(top_density['violations_per_km']):
    axes[1].text(val + 1, i, f'{val:.1f}', va='center', fontsize=9)

plt.suptitle('Where Do Parking Violations Happen? Road Type Analysis', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("violations_by_road_type")

# ---- Violations by Lane Count ----
print("\n" + "-" * 70)
print("5. VIOLATIONS BY LANE COUNT")
print("-" * 70)

viol_by_lanes = viol_df.groupby('road_lanes').agg(
    count=('road_lanes', 'size'),
    mean_width=('road_width', 'mean')
).sort_index()

print("\n  Violations by lane count:")
for lanes, row in viol_by_lanes.iterrows():
    pct = row['count'] / len(viol_df) * 100
    print(f"    {int(lanes)} lanes | {int(row['count']):>8,} ({pct:>5.1f}%) | avg width={row['mean_width']:.1f}m")

# Fig 3: Lane analysis
fig, axes = plt.subplots(1, 2, figsize=(18, 8))

colors_l = ['#2ecc71', '#27ae60', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b'][:len(viol_by_lanes)]
axes[0].bar(viol_by_lanes.index.astype(str), viol_by_lanes['count'], color=colors_l, edgecolor='white')
for i, (lanes, row) in enumerate(viol_by_lanes.iterrows()):
    axes[0].text(i, row['count'] + 1000, f'{int(row["count"]):,}\n({row["count"]/len(viol_df)*100:.1f}%)', 
                 ha='center', fontsize=10, fontweight='bold')
axes[0].set_xlabel('Number of Lanes', fontsize=13)
axes[0].set_ylabel('Violation Count', fontsize=13)
axes[0].set_title('Violations by Road Lane Count', fontsize=14, fontweight='bold')

# Violation type breakdown by lane count
viol_types_focus = ['WRONG PARKING', 'NO PARKING', 'PARKING IN A MAIN ROAD', 'DOUBLE PARKING', 
                    'PARKING ON FOOTPATH', 'PARKING NEAR ROAD CROSSING']
for vtype in viol_types_focus:
    mask = viol_df['violation_type'].str.contains(vtype, na=False)
    lane_dist = viol_df[mask].groupby('road_lanes').size()
    lane_pct = lane_dist / lane_dist.sum() * 100
    if len(lane_pct) > 0:
        axes[1].plot(lane_pct.index, lane_pct.values, 'o-', label=vtype.title(), linewidth=2, markersize=6)

axes[1].set_xlabel('Number of Lanes', fontsize=13)
axes[1].set_ylabel('% of That Violation Type', fontsize=13)
axes[1].set_title('Violation Type Distribution Across Lane Counts', fontsize=14, fontweight='bold')
axes[1].legend(fontsize=9, loc='upper right')

plt.suptitle('Lane Count Analysis: Narrow Roads Bear the Burden?', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("violations_by_lanes")

# ---- Road Tier Analysis ----
print("\n" + "-" * 70)
print("6. ROAD TIER / HIERARCHY ANALYSIS")
print("-" * 70)

tier_analysis = viol_df.groupby(['road_tier', 'road_tier_name']).agg(
    violations=('road_tier', 'size'),
    unique_roads=('road_name', 'nunique'),
    mean_lanes=('road_lanes', 'mean'),
    mean_width=('road_width', 'mean'),
).reset_index().sort_values('road_tier')

print("\n  Violations by road hierarchy:")
for _, row in tier_analysis.iterrows():
    pct = row['violations'] / len(viol_df) * 100
    print(f"    Tier {int(row['road_tier'])} ({row['road_tier_name']:15s}) | {int(row['violations']):>8,} ({pct:>5.1f}%) | "
          f"avg lanes={row['mean_lanes']:.1f}, width={row['mean_width']:.1f}m, {int(row['unique_roads'])} roads")

# Fig 4: Road tier sunburst-style
fig, axes = plt.subplots(1, 2, figsize=(18, 9))

tier_colors = {1: '#c0392b', 2: '#e74c3c', 3: '#e67e22', 4: '#f1c40f', 
               5: '#27ae60', 6: '#3498db', 7: '#9b59b6', 8: '#95a5a6'}

# Bar chart
tier_labels = tier_analysis.apply(lambda r: f"T{int(r['road_tier'])}: {r['road_tier_name']}", axis=1)
bar_colors = [tier_colors.get(int(t), '#95a5a6') for t in tier_analysis['road_tier']]
axes[0].barh(range(len(tier_analysis)), tier_analysis['violations'], color=bar_colors, edgecolor='white')
axes[0].set_yticks(range(len(tier_analysis)))
axes[0].set_yticklabels(tier_labels, fontsize=11)
axes[0].set_xlabel('Violation Count', fontsize=13)
axes[0].set_title('Violations by Road Hierarchy', fontsize=14, fontweight='bold')
axes[0].invert_yaxis()
for i, val in enumerate(tier_analysis['violations']):
    axes[0].text(val + 500, i, f'{int(val):,}', va='center', fontsize=9)

# Violation type heatmap by tier
viol_type_tier = pd.crosstab(
    viol_df['road_tier_name'], 
    viol_df['violation_type'].str.split(',').str[0].str.strip(),
    normalize='index'
) * 100
# Keep only top violation types
top_vtypes = viol_df['violation_type'].str.split(',').str[0].str.strip().value_counts().head(6).index
viol_type_tier = viol_type_tier[viol_type_tier.columns.intersection(top_vtypes)]

sns.heatmap(viol_type_tier, cmap='YlOrRd', annot=True, fmt='.1f', ax=axes[1],
            cbar_kws={'label': '% of Tier Violations'}, annot_kws={'fontsize': 8})
axes[1].set_title('Violation Type % by Road Hierarchy', fontsize=14, fontweight='bold')
axes[1].set_ylabel('')

plt.suptitle('Road Hierarchy: Which Tiers Are Most Affected?', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("road_tier_analysis")

# ---- Top Named Roads ----
print("\n" + "-" * 70)
print("7. TOP NAMED ROADS BY VIOLATION COUNT")
print("-" * 70)

named_roads = viol_df[viol_df['road_name'] != 'unnamed'].copy()
top_roads = named_roads.groupby('road_name').agg(
    violations=('road_name', 'size'),
    road_type=('road_type', lambda x: x.mode()[0] if len(x.mode()) > 0 else 'unknown'),
    avg_lanes=('road_lanes', 'mean'),
    avg_width=('road_width', 'mean'),
).sort_values('violations', ascending=False)

print("\n  Top 20 named roads:")
for road, row in top_roads.head(20).iterrows():
    print(f"    {road:40s} | {int(row['violations']):>5,} | {row['road_type']:15s} | {row['avg_lanes']:.0f}L | {row['avg_width']:.0f}m")

# Fig 5: Top roads
fig, ax = plt.subplots(figsize=(14, 10))
top20 = top_roads.head(20)
colors_named = plt.cm.RdYlGn_r(np.linspace(0.15, 0.85, len(top20)))
ax.barh(range(len(top20)), top20['violations'], color=colors_named)
ax.set_yticks(range(len(top20)))
labels = [f"{road} ({row['road_type']}, {row['avg_lanes']:.0f}L)" 
          for road, row in top20.iterrows()]
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel('Violation Count', fontsize=13)
ax.set_title('Top 20 Named Roads by Parking Violations', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, val in enumerate(top20['violations']):
    ax.text(val + 20, i, f'{int(val):,}', va='center', fontsize=9)
plt.tight_layout()
save_fig("top_named_roads")

# ---- Violation Type by Road Characteristics ----
print("\n" + "-" * 70)
print("8. VIOLATION TYPE vs ROAD CHARACTERISTICS")
print("-" * 70)

# Congestion-relevant violations on different road types
congestion_types = ['PARKING IN A MAIN ROAD', 'DOUBLE PARKING', 
                    'PARKING NEAR ROAD CROSSING', 'PARKING NEAR BUSTOP/SCHOOL/HOSPITAL']

for vtype in congestion_types:
    mask = viol_df['violation_type'].str.contains(vtype, na=False)
    subset = viol_df[mask]
    if len(subset) > 100:
        avg_lanes = subset['road_lanes'].mean()
        avg_width = subset['road_width'].mean()
        top_tier = subset['road_tier_name'].mode()[0]
        print(f"\n  {vtype}:")
        print(f"    Count: {len(subset):,}")
        print(f"    Avg lanes: {avg_lanes:.1f}, Avg width: {avg_width:.1f}m")
        print(f"    Most common road tier: {top_tier}")
        tier_dist = subset['road_tier_name'].value_counts().head(3)
        for tier, count in tier_dist.items():
            print(f"      {tier}: {count:,} ({count/len(subset)*100:.1f}%)")

# Fig 6: Congestion-relevant violations on narrow vs wide roads
fig, axes = plt.subplots(2, 2, figsize=(18, 14))

# "PARKING IN A MAIN ROAD" by road width
for i, (vtype, ax) in enumerate(zip(congestion_types[:4], axes.flat)):
    mask = viol_df['violation_type'].str.contains(vtype, na=False)
    subset = viol_df[mask]
    if len(subset) > 50:
        tier_counts = subset['road_tier_name'].value_counts()
        colors_t = [tier_colors.get(k, '#95a5a6') for k in range(1, 9)]
        ax.bar(range(len(tier_counts)), tier_counts.values, 
               color=sns.color_palette("Set2", len(tier_counts)), edgecolor='white')
        ax.set_xticks(range(len(tier_counts)))
        ax.set_xticklabels(tier_counts.index, fontsize=8, rotation=45, ha='right')
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title(f'{vtype}\n(n={len(subset):,})', fontsize=12, fontweight='bold')
    else:
        ax.text(0.5, 0.5, f'{vtype}\n(n={len(subset):,}, too few)', 
                transform=ax.transAxes, ha='center', va='center', fontsize=12)

plt.suptitle('Congestion-Relevant Violations by Road Hierarchy', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("congestion_violations_by_road_tier")

# ---- Capacity Impact Estimation ----
print("\n" + "-" * 70)
print("9. LANE CAPACITY IMPACT ESTIMATION")
print("-" * 70)

# Estimate how much lane capacity each violation blocks
# Car width ≈ 2.0m, Scooter ≈ 0.7m, Auto ≈ 1.5m, Heavy ≈ 2.5m
VEHICLE_WIDTH = {
    'CAR': 2.0, 'SCOOTER': 0.7, 'MOTOR CYCLE': 0.7, 'MOPED': 0.6,
    'PASSENGER AUTO': 1.5, 'MAXI-CAB': 2.3, 'LGV': 2.5, 'HGV': 2.5,
    'TRACTOR': 2.5, 'AMBULANCE': 2.0, 'OMNI BUS': 2.5,
}

viol_df['vehicle_width_m'] = viol_df['vehicle_type'].map(VEHICLE_WIDTH).fillna(1.5)

# Lane capacity blocked = vehicle_width / road_width
viol_df['capacity_blocked_pct'] = (viol_df['vehicle_width_m'] / viol_df['road_width']) * 100
# Cap at 100%
viol_df['capacity_blocked_pct'] = viol_df['capacity_blocked_pct'].clip(upper=100)

# Lane equivalents blocked
viol_df['lanes_blocked'] = viol_df['vehicle_width_m'] / (viol_df['road_width'] / viol_df['road_lanes'])

print(f"\n  Capacity impact stats:")
print(f"    Mean % of road width blocked: {viol_df['capacity_blocked_pct'].mean():.1f}%")
print(f"    Median: {viol_df['capacity_blocked_pct'].median():.1f}%")
print(f"    Mean lane equivalents blocked: {viol_df['lanes_blocked'].mean():.2f}")
print(f"    Violations blocking >25% of road: {(viol_df['capacity_blocked_pct'] > 25).sum():,} ({(viol_df['capacity_blocked_pct'] > 25).sum()/len(viol_df)*100:.1f}%)")
print(f"    Violations blocking >50% of road: {(viol_df['capacity_blocked_pct'] > 50).sum():,} ({(viol_df['capacity_blocked_pct'] > 50).sum()/len(viol_df)*100:.1f}%)")

# By vehicle type
cap_by_vehicle = viol_df.groupby('vehicle_type')['capacity_blocked_pct'].agg(['mean', 'median', 'count'])
cap_by_vehicle = cap_by_vehicle.sort_values('mean', ascending=False)
print("\n  Capacity blocked by vehicle type:")
for vtype, row in cap_by_vehicle.head(10).iterrows():
    print(f"    {vtype:20s} | mean={row['mean']:>5.1f}%, median={row['median']:>5.1f}%, n={int(row['count']):>6,}")

# By road tier
cap_by_tier = viol_df.groupby('road_tier_name')['capacity_blocked_pct'].agg(['mean', 'median', 'count'])
cap_by_tier = cap_by_tier.sort_values('mean', ascending=False)
print("\n  Capacity blocked by road tier:")
for tier, row in cap_by_tier.iterrows():
    print(f"    {tier:20s} | mean={row['mean']:>5.1f}%, median={row['median']:>5.1f}%, n={int(row['count']):>6,}")

# Fig 7: Capacity impact analysis
fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# Distribution of capacity blocked
axes[0].hist(viol_df['capacity_blocked_pct'], bins=50, color='#e74c3c', edgecolor='white', alpha=0.8)
axes[0].axvline(viol_df['capacity_blocked_pct'].median(), color='blue', linestyle='--', linewidth=2,
                label=f'Median: {viol_df["capacity_blocked_pct"].median():.1f}%')
axes[0].set_xlabel('% of Road Width Blocked', fontsize=13)
axes[0].set_ylabel('Count', fontsize=13)
axes[0].set_title('Distribution of Lane Capacity Blocked per Violation', fontsize=14, fontweight='bold')
axes[0].legend(fontsize=12)

# By road tier boxplot
sns.boxplot(data=viol_df, x='capacity_blocked_pct', y='road_tier_name', 
            ax=axes[1], palette='RdYlGn_r', showfliers=False,
            order=cap_by_tier.index)
axes[1].set_xlabel('% of Road Width Blocked', fontsize=13)
axes[1].set_ylabel('')
axes[1].set_title('Capacity Impact by Road Hierarchy', fontsize=14, fontweight='bold')

plt.suptitle('Lane Capacity Impact Estimation', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("capacity_impact_analysis")

# ---- Spatial Map: Violations on Road Network ----
print("\n" + "-" * 70)
print("10. SPATIAL MAP: VIOLATIONS ON ROAD NETWORK")
print("-" * 70)

# Plot road network with violation density overlay
fig, ax = plt.subplots(figsize=(16, 16))

# Draw roads colored by tier
for tier in sorted(edges['road_tier'].unique()):
    tier_edges = edges[edges['road_tier'] == tier]
    color = tier_colors.get(tier, '#cccccc')
    linewidth = max(0.3, 2.5 - tier * 0.3)
    alpha = max(0.2, 1.0 - tier * 0.1)
    tier_name = ROAD_HIERARCHY.get(tier_edges['highway_type'].iloc[0], {}).get('name', f'Tier {tier}')
    for _, edge in tier_edges.iterrows():
        xs, ys = edge.geometry.xy
        ax.plot(xs, ys, color=color, linewidth=linewidth, alpha=alpha)

# Overlay violation hexbin
hb = ax.hexbin(viol_df['longitude'], viol_df['latitude'], gridsize=80, 
               cmap='YlOrRd', mincnt=5, alpha=0.6)
plt.colorbar(hb, ax=ax, label='Violation Count', shrink=0.6)

ax.set_xlim(77.45, 77.75)
ax.set_ylim(12.85, 13.10)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Parking Violations Overlaid on Bengaluru Road Network', fontsize=15, fontweight='bold')
ax.set_aspect('equal')
plt.tight_layout()
save_fig("violations_on_road_network")

# ---- High-Impact Segments ----
print("\n" + "-" * 70)
print("11. HIGH-IMPACT ROAD SEGMENTS")
print("-" * 70)

# Aggregate violations per road segment
segment_viols = viol_df.groupby('nearest_road_idx').agg(
    violations=('nearest_road_idx', 'size'),
    mean_capacity_blocked=('capacity_blocked_pct', 'mean'),
    road_type=('road_type', lambda x: x.mode()[0] if len(x.mode()) > 0 else 'unknown'),
    road_name=('road_name', lambda x: x.mode()[0] if len(x.mode()) > 0 else 'unnamed'),
    lanes=('road_lanes', 'first'),
    width=('road_width', 'first'),
).sort_values('violations', ascending=False)

# Impact score = violations * avg_capacity_blocked / 100
segment_viols['impact_score'] = segment_viols['violations'] * segment_viols['mean_capacity_blocked'] / 100

print("\n  Top 20 road segments by violation count:")
for idx, row in segment_viols.head(20).iterrows():
    print(f"    Seg#{idx:>5d} | {int(row['violations']):>5,} viols | {row['road_name']:30s} | "
          f"{row['road_type']:15s} | {int(row['lanes'])}L/{row['width']:.0f}m | "
          f"cap_blocked={row['mean_capacity_blocked']:.1f}% | impact={row['impact_score']:.1f}")

print("\n  Top 20 road segments by IMPACT SCORE:")
segment_viols_impact = segment_viols.sort_values('impact_score', ascending=False)
for idx, row in segment_viols_impact.head(20).iterrows():
    print(f"    Seg#{idx:>5d} | impact={row['impact_score']:>7.1f} | {int(row['violations']):>5,} viols | "
          f"{row['road_name']:30s} | {row['road_type']:15s} | {int(row['lanes'])}L/{row['width']:.0f}m")

# Fig 8: Top segments
fig, ax = plt.subplots(figsize=(14, 10))
top_segments = segment_viols_impact.head(20)
labels = [f"{row['road_name']} ({row['road_type']}, {int(row['lanes'])}L)" 
          for _, row in top_segments.iterrows()]
colors_imp = plt.cm.RdYlGn_r(np.linspace(0.2, 0.9, len(top_segments)))
ax.barh(range(len(top_segments)), top_segments['impact_score'], color=colors_imp)
ax.set_yticks(range(len(top_segments)))
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel('Impact Score (violations × capacity_blocked%)', fontsize=13)
ax.set_title('Top 20 Road Segments by Parking Impact Score', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, (_, row) in enumerate(top_segments.iterrows()):
    ax.text(row['impact_score'] + 5, i, f'{row["impact_score"]:.0f} ({int(row["violations"])} viols)', 
            va='center', fontsize=8)
plt.tight_layout()
save_fig("top_impact_segments")

# ---- Summary ----
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print(f"""
  ROAD NETWORK:
    Total road segments: {len(edges):,}
    Total road length: {edges['length'].sum()/1000:.1f} km
    
  VIOLATION MAPPING:
    Mapped to nearest road: {len(viol_df):,} violations
    Median distance to road: {viol_df['dist_to_road_m'].median():.1f}m
    Within 100m of road: {(viol_df['dist_to_road_m'] <= 100).sum()/len(viol_df)*100:.1f}%
    
  KEY FINDINGS:
    Most violated road type: {viol_by_road.index[0]} ({int(viol_by_road.iloc[0]['violation_count']):,})
    Highest density road type: {top_density.index[0]} ({top_density.iloc[0]['violations_per_km']:.1f} per km)
    Mean capacity blocked: {viol_df['capacity_blocked_pct'].mean():.1f}%
    Violations blocking >25% width: {(viol_df['capacity_blocked_pct'] > 25).sum():,} ({(viol_df['capacity_blocked_pct'] > 25).sum()/len(viol_df)*100:.1f}%)
    
  All charts saved to: {RESEARCH_DIR}/
""")
print("Done!")

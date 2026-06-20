"""
EDA #1: Police Violation Data (298K records)
============================================
Deep exploratory data analysis of parking violation records.
All graphs saved to research/ folder.
Findings summarized in research/01_violation_eda.md
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
import json
import warnings
warnings.filterwarnings('ignore')

# ---- Config ----
DATA_PATH = r"c:\Github\Gridlock project\jan to may police violation_anonymized791b166.csv"
RESEARCH_DIR = Path(r"c:\Github\Gridlock project\research")
RESEARCH_DIR.mkdir(exist_ok=True)

# Style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
FIGSIZE = (14, 8)
DPI = 150

def save_fig(name, fig=None):
    """Save figure with consistent naming."""
    if fig is None:
        fig = plt.gcf()
    path = RESEARCH_DIR / f"01_{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  ✓ Saved: {path.name}")
    return path

# ---- Load Data ----
print("=" * 70)
print("EDA #1: PARKING VIOLATION DATA")
print("=" * 70)

print("\n📂 Loading data...")
df = pd.read_csv(DATA_PATH, low_memory=False)
print(f"  Loaded {df.shape[0]:,} rows × {df.shape[1]} columns")

# ---- 1. DATA QUALITY AUDIT ----
print("\n" + "─" * 70)
print("1. DATA QUALITY AUDIT")
print("─" * 70)

# Data types
print("\n📊 Column types:")
for col in df.columns:
    non_null = df[col].notna().sum()
    pct = non_null / len(df) * 100
    print(f"  {col:40s} | {str(df[col].dtype):10s} | {non_null:>7,} non-null ({pct:.1f}%)")

# Parse datetimes
df['created_datetime'] = pd.to_datetime(df['created_datetime'], errors='coerce')
df['closed_datetime'] = pd.to_datetime(df['closed_datetime'], errors='coerce')
df['modified_datetime'] = pd.to_datetime(df['modified_datetime'], errors='coerce')
df['validation_timestamp'] = pd.to_datetime(df['validation_timestamp'], errors='coerce')

# Extract time features (drop NaT rows for time analysis)
df = df.dropna(subset=['created_datetime']).copy()
df['hour'] = df['created_datetime'].dt.hour.astype(int)
df['day_of_week'] = df['created_datetime'].dt.dayofweek.astype(int)  # 0=Monday
df['day_name'] = df['created_datetime'].dt.day_name()
df['month'] = df['created_datetime'].dt.month.astype(int)
df['month_name'] = df['created_datetime'].dt.month_name()
df['date'] = df['created_datetime'].dt.date
df['week'] = df['created_datetime'].dt.isocalendar().week.astype(int)
print(f"  After dropping NaT: {len(df):,} rows")

# ---- 2. VIOLATION TYPE ANALYSIS ----
print("\n" + "─" * 70)
print("2. VIOLATION TYPE ANALYSIS")
print("─" * 70)

# Parse violation_type (it's JSON-like)
def parse_violations(v):
    if pd.isna(v):
        return []
    try:
        # It's stored like: ["WRONG PARKING","NO PARKING"]
        return json.loads(v.replace('""', '"').strip('"'))
    except:
        try:
            import ast
            return ast.literal_eval(v)
        except:
            return [v]

df['violation_list'] = df['violation_type'].apply(parse_violations)
df['num_violations'] = df['violation_list'].apply(len)

# Explode to individual violations
all_violations = df.explode('violation_list')
violation_counts = all_violations['violation_list'].value_counts()

print("\n📊 Individual violation types (exploded):")
for vtype, count in violation_counts.items():
    print(f"  {vtype:55s} | {count:>7,} ({count/len(df)*100:.1f}%)")

# Fig 1: Violation type bar chart
fig, ax = plt.subplots(figsize=FIGSIZE)
colors = sns.color_palette("viridis", len(violation_counts))
bars = ax.barh(range(len(violation_counts)), violation_counts.values, color=colors)
ax.set_yticks(range(len(violation_counts)))
ax.set_yticklabels(violation_counts.index, fontsize=11)
ax.set_xlabel('Count', fontsize=13)
ax.set_title('Parking Violation Types — Bengaluru (Nov 2023 – Apr 2024)', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for bar, val in zip(bars, violation_counts.values):
    ax.text(val + 500, bar.get_y() + bar.get_height()/2, f'{val:,}', 
            va='center', fontsize=10, fontweight='bold')
plt.tight_layout()
save_fig("violation_types_bar")

# Fig 2: Multi-violation combinations
combo_counts = df['violation_type'].value_counts().head(15)
fig, ax = plt.subplots(figsize=(14, 9))
colors = sns.color_palette("magma", len(combo_counts))
bars = ax.barh(range(len(combo_counts)), combo_counts.values, color=colors)
labels = [str(x)[:60] for x in combo_counts.index]
ax.set_yticks(range(len(combo_counts)))
ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel('Count', fontsize=13)
ax.set_title('Top 15 Violation Type Combinations', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for bar, val in zip(bars, combo_counts.values):
    ax.text(val + 200, bar.get_y() + bar.get_height()/2, f'{val:,}', 
            va='center', fontsize=9)
plt.tight_layout()
save_fig("violation_combos_top15")

# ---- 3. TEMPORAL ANALYSIS ----
print("\n" + "─" * 70)
print("3. TEMPORAL ANALYSIS")
print("─" * 70)

# Fig 3: Violations by hour of day
hourly = df.groupby('hour').size()
print("\n📊 Hourly distribution:")
for h, c in hourly.items():
    bar = "█" * int(c / hourly.max() * 40)
    print(f"  {h:02d}:00 | {bar} {c:,}")

fig, ax = plt.subplots(figsize=FIGSIZE)
ax.bar(hourly.index, hourly.values, color=sns.color_palette("coolwarm", 24), edgecolor='white', linewidth=0.5)
ax.set_xlabel('Hour of Day', fontsize=13)
ax.set_ylabel('Number of Violations', fontsize=13)
ax.set_title('Parking Violations by Hour of Day', fontsize=15, fontweight='bold')
ax.set_xticks(range(24))
ax.set_xticklabels([f'{h:02d}:00' for h in range(24)], rotation=45, fontsize=9)
# Annotate peak
peak_hour = hourly.idxmax()
ax.annotate(f'Peak: {peak_hour:02d}:00\n({hourly.max():,})', 
            xy=(peak_hour, hourly.max()), xytext=(peak_hour+2, hourly.max()*0.95),
            fontsize=11, fontweight='bold', color='red',
            arrowprops=dict(arrowstyle='->', color='red'))
plt.tight_layout()
save_fig("violations_by_hour")

# Fig 4: Violations by day of week
daily = df.groupby(['day_of_week', 'day_name']).size().reset_index(name='count')
daily = daily.sort_values('day_of_week')

fig, ax = plt.subplots(figsize=(12, 7))
colors = sns.color_palette("Set2", 7)
ax.bar(daily['day_name'], daily['count'], color=colors, edgecolor='white', linewidth=0.5)
ax.set_xlabel('Day of Week', fontsize=13)
ax.set_ylabel('Number of Violations', fontsize=13)
ax.set_title('Parking Violations by Day of Week', fontsize=15, fontweight='bold')
for i, (_, row) in enumerate(daily.iterrows()):
    ax.text(i, row['count'] + 200, f'{row["count"]:,}', ha='center', fontsize=10, fontweight='bold')
plt.tight_layout()
save_fig("violations_by_dayofweek")

# Fig 5: Daily violations timeline
daily_ts = df.groupby('date').size()
fig, ax = plt.subplots(figsize=(16, 7))
ax.plot(daily_ts.index, daily_ts.values, color='#3498db', linewidth=0.8, alpha=0.7)
# 7-day rolling average
rolling = daily_ts.rolling(7, center=True).mean()
ax.plot(rolling.index, rolling.values, color='#e74c3c', linewidth=2.5, label='7-day moving avg')
ax.set_xlabel('Date', fontsize=13)
ax.set_ylabel('Daily Violations', fontsize=13)
ax.set_title('Daily Parking Violations Timeline (Nov 2023 – Apr 2024)', fontsize=15, fontweight='bold')
ax.legend(fontsize=12)
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
save_fig("violations_daily_timeline")

# Fig 6: Monthly violations
monthly = df.groupby('month_name').size()
month_order = ['November', 'December', 'January', 'February', 'March', 'April']
monthly = monthly.reindex(month_order)

fig, ax = plt.subplots(figsize=(12, 7))
colors = sns.color_palette("rocket", len(monthly))
bars = ax.bar(monthly.index, monthly.values, color=colors, edgecolor='white')
ax.set_xlabel('Month', fontsize=13)
ax.set_ylabel('Number of Violations', fontsize=13)
ax.set_title('Monthly Parking Violations', fontsize=15, fontweight='bold')
for bar, val in zip(bars, monthly.values):
    ax.text(bar.get_x() + bar.get_width()/2, val + 300, f'{val:,}', 
            ha='center', fontsize=11, fontweight='bold')
plt.tight_layout()
save_fig("violations_monthly")

# Fig 7: Heatmap — Hour × Day of Week
heatmap_data = df.groupby(['day_of_week', 'hour']).size().unstack(fill_value=0)
day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
heatmap_data.index = day_labels

fig, ax = plt.subplots(figsize=(16, 7))
sns.heatmap(heatmap_data, cmap='YlOrRd', annot=False, fmt='d', ax=ax,
            xticklabels=[f'{h:02d}' for h in range(24)],
            cbar_kws={'label': 'Violation Count'})
ax.set_xlabel('Hour of Day', fontsize=13)
ax.set_ylabel('Day of Week', fontsize=13)
ax.set_title('Violation Density Heatmap: Hour × Day of Week', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("violations_heatmap_hour_day")

# ---- 4. VEHICLE TYPE ANALYSIS ----
print("\n" + "─" * 70)
print("4. VEHICLE TYPE ANALYSIS")
print("─" * 70)

vehicle_counts = df['vehicle_type'].value_counts()
print("\n📊 Vehicle types:")
for vtype, count in vehicle_counts.head(15).items():
    print(f"  {vtype:25s} | {count:>7,} ({count/len(df)*100:.1f}%)")

# Fig 8: Vehicle type distribution
fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# Bar chart
top_vehicles = vehicle_counts.head(12)
colors = sns.color_palette("tab20", len(top_vehicles))
axes[0].barh(range(len(top_vehicles)), top_vehicles.values, color=colors)
axes[0].set_yticks(range(len(top_vehicles)))
axes[0].set_yticklabels(top_vehicles.index, fontsize=11)
axes[0].set_xlabel('Count', fontsize=13)
axes[0].set_title('Top 12 Vehicle Types', fontsize=14, fontweight='bold')
axes[0].invert_yaxis()
for i, val in enumerate(top_vehicles.values):
    axes[0].text(val + 200, i, f'{val:,}', va='center', fontsize=9)

# Pie chart — top 5 vs rest
top5 = vehicle_counts.head(5)
others = pd.Series({'Others': vehicle_counts.iloc[5:].sum()})
pie_data = pd.concat([top5, others])
explode = [0.03] * len(pie_data)
axes[1].pie(pie_data.values, labels=pie_data.index, autopct='%1.1f%%', 
            explode=explode, colors=sns.color_palette("pastel", len(pie_data)),
            textprops={'fontsize': 11})
axes[1].set_title('Vehicle Type Share', fontsize=14, fontweight='bold')

plt.suptitle('Vehicle Type Analysis', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig("vehicle_type_analysis")

# ---- 5. POLICE STATION ANALYSIS ----
print("\n" + "─" * 70)
print("5. POLICE STATION ANALYSIS")
print("─" * 70)

station_counts = df['police_station'].value_counts()
print(f"\n📊 {len(station_counts)} police stations")
print(f"   Top station: {station_counts.index[0]} ({station_counts.iloc[0]:,})")
print(f"   Bottom station: {station_counts.index[-1]} ({station_counts.iloc[-1]:,})")
print(f"   Mean: {station_counts.mean():.0f}, Median: {station_counts.median():.0f}")
print(f"   Std Dev: {station_counts.std():.0f}")

# Fig 9: Police station rankings
fig, ax = plt.subplots(figsize=(14, 14))
colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(station_counts)))
ax.barh(range(len(station_counts)), station_counts.values, color=colors)
ax.set_yticks(range(len(station_counts)))
ax.set_yticklabels(station_counts.index, fontsize=9)
ax.set_xlabel('Number of Violations', fontsize=13)
ax.set_title('Parking Violations by Police Station', fontsize=15, fontweight='bold')
ax.invert_yaxis()
plt.tight_layout()
save_fig("violations_by_station")

# Fig 10: Top 10 stations breakdown by violation type
top10_stations = station_counts.head(10).index.tolist()
station_viol = all_violations[all_violations['police_station'].isin(top10_stations)]
station_viol_pivot = station_viol.groupby(['police_station', 'violation_list']).size().unstack(fill_value=0)

# Keep top 5 violation types
top5_viols = violation_counts.head(5).index.tolist()
if 'Others' not in station_viol_pivot.columns:
    other_cols = [c for c in station_viol_pivot.columns if c not in top5_viols]
    station_viol_pivot['Others'] = station_viol_pivot[other_cols].sum(axis=1)
station_viol_pivot = station_viol_pivot[top5_viols + ['Others']]
station_viol_pivot = station_viol_pivot.loc[top10_stations]

fig, ax = plt.subplots(figsize=(16, 9))
station_viol_pivot.plot(kind='barh', stacked=True, ax=ax, 
                         colormap='Set2', edgecolor='white', linewidth=0.3)
ax.set_xlabel('Number of Violations', fontsize=13)
ax.set_title('Top 10 Police Stations — Violation Type Breakdown', fontsize=15, fontweight='bold')
ax.legend(title='Violation Type', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
ax.invert_yaxis()
plt.tight_layout()
save_fig("top10_stations_violation_breakdown")

# ---- 6. SPATIAL DISTRIBUTION ----
print("\n" + "─" * 70)
print("6. SPATIAL DISTRIBUTION")
print("─" * 70)

# Remove outliers
lat_mask = (df['latitude'] > 12.7) & (df['latitude'] < 13.4)
lon_mask = (df['longitude'] > 77.3) & (df['longitude'] < 77.9)
df_geo = df[lat_mask & lon_mask].copy()
print(f"\n  Records with valid coordinates: {len(df_geo):,} / {len(df):,}")

# Fig 11: Spatial scatter plot
fig, ax = plt.subplots(figsize=(14, 14))
scatter = ax.scatter(df_geo['longitude'], df_geo['latitude'], 
                     s=0.5, alpha=0.05, c='#e74c3c', rasterized=True)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title(f'Spatial Distribution of {len(df_geo):,} Parking Violations', fontsize=15, fontweight='bold')
ax.set_aspect('equal')
plt.tight_layout()
save_fig("violations_spatial_scatter")

# Fig 12: 2D Hexbin density
fig, ax = plt.subplots(figsize=(14, 14))
hb = ax.hexbin(df_geo['longitude'], df_geo['latitude'], 
               gridsize=80, cmap='inferno', mincnt=1)
plt.colorbar(hb, ax=ax, label='Violation Count', shrink=0.7)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Parking Violation Density (Hexbin)', fontsize=15, fontweight='bold')
ax.set_aspect('equal')
plt.tight_layout()
save_fig("violations_hexbin_density")

# Fig 13: Top 20 hotspot locations (most repeated lat/lon)
location_counts = df_geo.groupby(['latitude', 'longitude']).size().reset_index(name='count')
location_counts = location_counts.sort_values('count', ascending=False)
top_hotspots = location_counts.head(20)
print(f"\n📊 Top 20 violation hotspot locations:")
for _, row in top_hotspots.iterrows():
    print(f"  ({row['latitude']:.4f}, {row['longitude']:.4f}) — {row['count']:,} violations")

fig, ax = plt.subplots(figsize=(14, 14))
# Background scatter
ax.scatter(df_geo['longitude'], df_geo['latitude'], 
           s=0.3, alpha=0.02, c='gray', rasterized=True)
# Top hotspots
scatter = ax.scatter(top_hotspots['longitude'], top_hotspots['latitude'], 
                     s=top_hotspots['count']*2, c=top_hotspots['count'], 
                     cmap='hot_r', edgecolors='white', linewidth=1.5, zorder=5)
plt.colorbar(scatter, ax=ax, label='Violation Count', shrink=0.7)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Top 20 Parking Violation Hotspot Locations', fontsize=15, fontweight='bold')
ax.set_aspect('equal')
plt.tight_layout()
save_fig("violations_hotspot_locations")

# ---- 7. JUNCTION ANALYSIS ----
print("\n" + "─" * 70)
print("7. JUNCTION ANALYSIS")
print("─" * 70)

junction_counts = df['junction_name'].value_counts()
has_junction = df[df['junction_name'] != 'No Junction']
print(f"\n  Records with junction info: {len(has_junction):,} ({len(has_junction)/len(df)*100:.1f}%)")
print(f"  Records at 'No Junction': {(df['junction_name'] == 'No Junction').sum():,}")

# Top junctions (excluding "No Junction")
top_junctions = junction_counts[junction_counts.index != 'No Junction'].head(25)
print(f"\n📊 Top 25 violation junctions:")
for jname, count in top_junctions.items():
    print(f"  {jname:55s} | {count:>5,}")

fig, ax = plt.subplots(figsize=(14, 12))
colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(top_junctions)))
ax.barh(range(len(top_junctions)), top_junctions.values, color=colors)
ax.set_yticks(range(len(top_junctions)))
ax.set_yticklabels(top_junctions.index, fontsize=9)
ax.set_xlabel('Number of Violations', fontsize=13)
ax.set_title('Top 25 Violation Junctions', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, val in enumerate(top_junctions.values):
    ax.text(val + 20, i, f'{val:,}', va='center', fontsize=9)
plt.tight_layout()
save_fig("violations_top_junctions")

# ---- 8. VALIDATION STATUS ANALYSIS ----
print("\n" + "─" * 70)
print("8. VALIDATION STATUS ANALYSIS")
print("─" * 70)

val_status = df['validation_status'].value_counts()
print("\n📊 Validation status:")
for status, count in val_status.items():
    print(f"  {str(status):15s} | {count:>7,} ({count/len(df)*100:.1f}%)")

# Approval rate by station
station_approval = df[df['validation_status'].isin(['approved', 'rejected'])].groupby('police_station')['validation_status'].apply(
    lambda x: (x == 'approved').sum() / len(x) * 100
).sort_values(ascending=False)

fig, ax = plt.subplots(figsize=(14, 12))
colors = ['#2ecc71' if r > 70 else '#e74c3c' if r < 50 else '#f39c12' for r in station_approval.values]
ax.barh(range(len(station_approval)), station_approval.values, color=colors)
ax.set_yticks(range(len(station_approval)))
ax.set_yticklabels(station_approval.index, fontsize=9)
ax.set_xlabel('Approval Rate (%)', fontsize=13)
ax.set_title('Violation Approval Rate by Police Station', fontsize=15, fontweight='bold')
ax.axvline(x=70, color='green', linestyle='--', alpha=0.5, label='70% threshold')
ax.axvline(x=50, color='red', linestyle='--', alpha=0.5, label='50% threshold')
ax.legend(fontsize=10)
ax.invert_yaxis()
plt.tight_layout()
save_fig("approval_rate_by_station")

# ---- 9. REPEAT OFFENDER VEHICLES ----
print("\n" + "─" * 70)
print("9. REPEAT OFFENDER ANALYSIS")
print("─" * 70)

vehicle_freq = df['vehicle_number'].value_counts()
repeat_stats = {
    '1 violation': (vehicle_freq == 1).sum(),
    '2 violations': (vehicle_freq == 2).sum(),
    '3-5 violations': ((vehicle_freq >= 3) & (vehicle_freq <= 5)).sum(),
    '6-10 violations': ((vehicle_freq >= 6) & (vehicle_freq <= 10)).sum(),
    '11+ violations': (vehicle_freq > 10).sum(),
}
print("\n📊 Repeat offender distribution:")
for label, count in repeat_stats.items():
    print(f"  {label:20s} | {count:>7,} unique vehicles")

print(f"\n  Most cited vehicle: {vehicle_freq.index[0]} with {vehicle_freq.iloc[0]} violations")
print(f"  Total unique vehicles: {len(vehicle_freq):,}")

fig, ax = plt.subplots(figsize=(12, 7))
ax.bar(repeat_stats.keys(), repeat_stats.values(), color=sns.color_palette("Reds_r", 5), edgecolor='white')
ax.set_xlabel('Number of Violations', fontsize=13)
ax.set_ylabel('Number of Unique Vehicles', fontsize=13)
ax.set_title('Repeat Offender Distribution', fontsize=15, fontweight='bold')
for i, (k, v) in enumerate(repeat_stats.items()):
    ax.text(i, v + 200, f'{v:,}', ha='center', fontsize=11, fontweight='bold')
plt.tight_layout()
save_fig("repeat_offenders")

# Fig: Violations per vehicle histogram (log scale)
fig, ax = plt.subplots(figsize=(12, 7))
ax.hist(vehicle_freq.values, bins=50, color='#3498db', edgecolor='white', log=True)
ax.set_xlabel('Violations per Vehicle', fontsize=13)
ax.set_ylabel('Count (log scale)', fontsize=13)
ax.set_title('Distribution of Violations per Vehicle', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("violations_per_vehicle_hist")

# ---- 10. CORRELATION: DEVICE/ENFORCEMENT PATTERNS ----
print("\n" + "─" * 70)
print("10. ENFORCEMENT DEVICE PATTERNS")
print("─" * 70)

device_counts = df['device_id'].value_counts()
print(f"\n  Unique enforcement devices: {len(device_counts):,}")
print(f"  Top device: {device_counts.index[0]} ({device_counts.iloc[0]:,} captures)")
print(f"  Mean captures per device: {device_counts.mean():.0f}")
print(f"  Median captures per device: {device_counts.median():.0f}")

# Top 20 devices
top_devices = device_counts.head(20)
fig, ax = plt.subplots(figsize=(14, 9))
ax.barh(range(len(top_devices)), top_devices.values, color=sns.color_palette("mako", len(top_devices)))
ax.set_yticks(range(len(top_devices)))
ax.set_yticklabels(top_devices.index, fontsize=10)
ax.set_xlabel('Number of Violations Captured', fontsize=13)
ax.set_title('Top 20 Enforcement Devices by Violation Count', fontsize=15, fontweight='bold')
ax.invert_yaxis()
plt.tight_layout()
save_fig("top_enforcement_devices")

# ---- SUMMARY STATS ----
print("\n" + "=" * 70)
print("SUMMARY STATISTICS")
print("=" * 70)

summary = {
    "Total Records": len(df),
    "Date Range": f"{df['created_datetime'].min()} to {df['created_datetime'].max()}",
    "Unique Vehicles": df['vehicle_number'].nunique(),
    "Unique Police Stations": df['police_station'].nunique(),
    "Unique Devices": df['device_id'].nunique(),
    "Unique Junctions": df['junction_name'].nunique(),
    "Approval Rate": f"{(df['validation_status'] == 'approved').sum() / df['validation_status'].notna().sum() * 100:.1f}%",
    "Peak Hour": f"{hourly.idxmax():02d}:00 ({hourly.max():,} violations)",
    "Peak Day": f"{daily.loc[daily['count'].idxmax(), 'day_name']}",
    "Peak Month": f"{monthly.idxmax()} ({monthly.max():,})",
    "Top Station": f"{station_counts.index[0]} ({station_counts.iloc[0]:,})",
    "Top Vehicle Type": f"{vehicle_counts.index[0]} ({vehicle_counts.iloc[0]:,})",
    "Repeat Offenders (2+)": f"{(vehicle_freq >= 2).sum():,} vehicles",
    "Multi-violation Records": f"{(df['num_violations'] > 1).sum():,} ({(df['num_violations'] > 1).sum()/len(df)*100:.1f}%)",
}

for k, v in summary.items():
    print(f"  {k:35s} | {v}")

print(f"\n✅ All graphs saved to: {RESEARCH_DIR}/")
print(f"   Total graphs generated: 15")
print("Done!")

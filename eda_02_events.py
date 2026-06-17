"""
EDA #2: Astram Event Data (8.2K records)
=========================================
Deep exploratory data analysis of traffic events/incidents.
All graphs saved to research/ folder.
Findings summarized in research/02_event_eda.md
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

# ---- Config ----
DATA_PATH = r"c:\Github\Gridlock project\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
RESEARCH_DIR = Path(r"c:\Github\Gridlock project\research")
RESEARCH_DIR.mkdir(exist_ok=True)

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
FIGSIZE = (14, 8)
DPI = 150

def save_fig(name, fig=None):
    if fig is None:
        fig = plt.gcf()
    path = RESEARCH_DIR / f"02_{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  > Saved: {path.name}")
    return path

# ---- Load Data ----
print("=" * 70)
print("EDA #2: ASTRAM EVENT / TRAFFIC INCIDENT DATA")
print("=" * 70)

print("\nLoading data...")
df = pd.read_csv(DATA_PATH, low_memory=False)
print(f"  Loaded {df.shape[0]:,} rows x {df.shape[1]} columns")
print(f"  Columns: {list(df.columns)}")

# ---- 1. DATA QUALITY AUDIT ----
print("\n" + "-" * 70)
print("1. DATA QUALITY AUDIT")
print("-" * 70)

print("\nColumn completeness:")
for col in df.columns:
    non_null = df[col].notna().sum()
    # Also check for 'NULL' string values
    null_str = (df[col].astype(str) == 'NULL').sum()
    real_non_null = non_null - null_str
    pct = real_non_null / len(df) * 100
    if pct < 99.5:
        print(f"  {col:40s} | {real_non_null:>6,} / {len(df):,} ({pct:.1f}%)")

# Parse datetimes
df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
df['end_datetime'] = pd.to_datetime(df['end_datetime'], errors='coerce')
df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
df['modified_datetime'] = pd.to_datetime(df['modified_datetime'], errors='coerce')
df['closed_datetime_parsed'] = pd.to_datetime(df['closed_datetime'], errors='coerce')
df['resolved_datetime'] = pd.to_datetime(df['resolved_datetime'], errors='coerce')

# Drop rows with no start_datetime
df = df.dropna(subset=['start_datetime']).copy()
print(f"\n  After dropping NaT start_datetime: {len(df):,} rows")

# Extract time features
df['hour'] = df['start_datetime'].dt.hour.astype(int)
df['day_of_week'] = df['start_datetime'].dt.dayofweek.astype(int)
df['day_name'] = df['start_datetime'].dt.day_name()
df['month'] = df['start_datetime'].dt.month.astype(int)
df['month_name'] = df['start_datetime'].dt.month_name()
df['date'] = df['start_datetime'].dt.date

# ---- 2. EVENT TYPE & CAUSE ANALYSIS ----
print("\n" + "-" * 70)
print("2. EVENT TYPE & CAUSE ANALYSIS")
print("-" * 70)

# Event type
event_type_counts = df['event_type'].value_counts()
print("\nEvent types:")
for etype, count in event_type_counts.items():
    print(f"  {etype:20s} | {count:>5,} ({count/len(df)*100:.1f}%)")

# Event cause
cause_counts = df['event_cause'].value_counts()
print("\nEvent causes:")
for cause, count in cause_counts.items():
    print(f"  {cause:25s} | {count:>5,} ({count/len(df)*100:.1f}%)")

# Fig 1: Event cause distribution
fig, axes = plt.subplots(1, 2, figsize=(20, 9))

# Bar chart
colors = sns.color_palette("Set2", len(cause_counts))
bars = axes[0].barh(range(len(cause_counts)), cause_counts.values, color=colors)
axes[0].set_yticks(range(len(cause_counts)))
axes[0].set_yticklabels(cause_counts.index, fontsize=11)
axes[0].set_xlabel('Count', fontsize=13)
axes[0].set_title('Traffic Event Causes', fontsize=15, fontweight='bold')
axes[0].invert_yaxis()
for bar, val in zip(bars, cause_counts.values):
    axes[0].text(val + 20, bar.get_y() + bar.get_height()/2, f'{val:,}', va='center', fontsize=10)

# Pie chart
top_causes = cause_counts.head(6)
others = pd.Series({'Others': cause_counts.iloc[6:].sum()})
pie_data = pd.concat([top_causes, others])
axes[1].pie(pie_data.values, labels=pie_data.index, autopct='%1.1f%%',
            colors=sns.color_palette("pastel", len(pie_data)),
            textprops={'fontsize': 11}, explode=[0.03]*len(pie_data))
axes[1].set_title('Event Cause Share', fontsize=15, fontweight='bold')
plt.suptitle('Bengaluru Traffic Events — Cause Analysis', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("event_causes")

# Fig 2: Planned vs Unplanned
fig, ax = plt.subplots(figsize=(10, 6))
planned_counts = df['event_type'].value_counts()
colors_pu = ['#e74c3c', '#2ecc71'] if planned_counts.index[0] == 'unplanned' else ['#2ecc71', '#e74c3c']
ax.bar(planned_counts.index, planned_counts.values, color=colors_pu, edgecolor='white', width=0.5)
for i, (idx, val) in enumerate(planned_counts.items()):
    ax.text(i, val + 50, f'{val:,}\n({val/len(df)*100:.1f}%)', ha='center', fontsize=14, fontweight='bold')
ax.set_ylabel('Count', fontsize=13)
ax.set_title('Planned vs Unplanned Events', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("planned_vs_unplanned")

# ---- 3. CONGESTION-SPECIFIC ANALYSIS ----
print("\n" + "-" * 70)
print("3. CONGESTION-RELEVANT EVENT ANALYSIS")
print("-" * 70)

# Define congestion-relevant causes
congestion_causes = ['congestion', 'vehicle_breakdown', 'accident', 'construction', 
                     'water_logging', 'road_conditions', 'public_event']
df['is_congestion_relevant'] = df['event_cause'].isin(congestion_causes)

congestion_df = df[df['is_congestion_relevant']].copy()
print(f"\n  Congestion-relevant events: {len(congestion_df):,} / {len(df):,} ({len(congestion_df)/len(df)*100:.1f}%)")
print("\n  Breakdown:")
for cause in congestion_causes:
    count = (df['event_cause'] == cause).sum()
    if count > 0:
        print(f"    {cause:25s} | {count:>5,}")

# Road closure flag
closure_counts = df['requires_road_closure'].value_counts()
print(f"\n  Events requiring road closure:")
for val, count in closure_counts.items():
    print(f"    {str(val):10s} | {count:>5,} ({count/len(df)*100:.1f}%)")

# Fig 3: Congestion-relevant events by cause with road closure breakdown
fig, ax = plt.subplots(figsize=(14, 8))
causes_for_chart = congestion_df['event_cause'].value_counts()

# Split by road closure
closure_data = congestion_df.groupby(['event_cause', 'requires_road_closure']).size().unstack(fill_value=0)
closure_data = closure_data.reindex(causes_for_chart.index)
if True in closure_data.columns and False in closure_data.columns:
    ax.barh(range(len(closure_data)), closure_data[False].values, color='#3498db', label='No Road Closure')
    ax.barh(range(len(closure_data)), closure_data[True].values, 
            left=closure_data[False].values, color='#e74c3c', label='Road Closure Required')
else:
    ax.barh(range(len(causes_for_chart)), causes_for_chart.values, color='#3498db')
ax.set_yticks(range(len(causes_for_chart)))
ax.set_yticklabels(causes_for_chart.index, fontsize=12)
ax.set_xlabel('Count', fontsize=13)
ax.set_title('Congestion-Relevant Events by Cause (with Road Closure Flag)', fontsize=15, fontweight='bold')
ax.legend(fontsize=12)
ax.invert_yaxis()
plt.tight_layout()
save_fig("congestion_events_by_cause")

# ---- 4. TEMPORAL PATTERNS ----
print("\n" + "-" * 70)
print("4. TEMPORAL PATTERNS")
print("-" * 70)

# Hourly
hourly = df.groupby('hour').size()
print("\nHourly distribution (UTC):")
for h, c in hourly.items():
    bar = "#" * int(c / hourly.max() * 40)
    print(f"  {h:02d}:00 | {bar} {c:,}")

# Fig 4: Hourly pattern
fig, ax = plt.subplots(figsize=FIGSIZE)
colors_h = ['#e74c3c' if h in [2,3,4,5,6,7,8] else '#3498db' for h in range(24)]
ax.bar(hourly.index, hourly.values, color=colors_h, edgecolor='white', linewidth=0.5)
ax.set_xlabel('Hour of Day (UTC)', fontsize=13)
ax.set_ylabel('Number of Events', fontsize=13)
ax.set_title('Traffic Events by Hour of Day (UTC)\nRed = IST 7:30 AM - 1:30 PM (Peak Reporting Window)', fontsize=14, fontweight='bold')
ax.set_xticks(range(24))
ax.set_xticklabels([f'{h:02d}' for h in range(24)], fontsize=9)
peak_h = hourly.idxmax()
ax.annotate(f'Peak: {peak_h:02d}:00 UTC\n= {(peak_h+5)%24}:{30 if peak_h+5<24 else 30}0 IST\n({hourly.max():,} events)',
            xy=(peak_h, hourly.max()), xytext=(peak_h+3, hourly.max()*0.9),
            fontsize=11, fontweight='bold', color='red',
            arrowprops=dict(arrowstyle='->', color='red'))
plt.tight_layout()
save_fig("events_by_hour")

# Fig 5: Hourly pattern — congestion-relevant only
hourly_cong = congestion_df.groupby('hour').size()
hourly_cause = congestion_df.groupby(['hour', 'event_cause']).size().unstack(fill_value=0)

fig, ax = plt.subplots(figsize=(16, 8))
hourly_cause_top = hourly_cause[causes_for_chart.head(5).index.tolist()].copy()
if len(hourly_cause.columns) > 5:
    hourly_cause_top['Others'] = hourly_cause.drop(columns=hourly_cause_top.columns, errors='ignore').sum(axis=1)
hourly_cause_top.plot(kind='bar', stacked=True, ax=ax, colormap='Set2', edgecolor='white', linewidth=0.3)
ax.set_xlabel('Hour of Day (UTC)', fontsize=13)
ax.set_ylabel('Event Count', fontsize=13)
ax.set_title('Congestion-Relevant Events by Hour — Cause Breakdown', fontsize=15, fontweight='bold')
ax.legend(title='Cause', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=10)
ax.set_xticklabels([f'{h:02d}' for h in range(24)], rotation=0, fontsize=9)
plt.tight_layout()
save_fig("congestion_events_hourly_stacked")

# Fig 6: Day of week
daily = df.groupby(['day_of_week', 'day_name']).size().reset_index(name='count')
daily = daily.sort_values('day_of_week')

fig, ax = plt.subplots(figsize=(12, 7))
colors_d = sns.color_palette("Set2", 7)
ax.bar(daily['day_name'], daily['count'], color=colors_d, edgecolor='white')
for i, (_, row) in enumerate(daily.iterrows()):
    ax.text(i, row['count'] + 15, f'{row["count"]:,}', ha='center', fontsize=11, fontweight='bold')
ax.set_ylabel('Number of Events', fontsize=13)
ax.set_title('Traffic Events by Day of Week', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("events_by_dayofweek")

# Fig 7: Monthly
monthly = df.groupby('month_name').size()
month_order = ['November', 'December', 'January', 'February', 'March', 'April']
monthly = monthly.reindex(month_order)

fig, ax = plt.subplots(figsize=(12, 7))
colors_m = sns.color_palette("rocket", len(monthly))
bars = ax.bar(monthly.index, monthly.values, color=colors_m, edgecolor='white')
for bar, val in zip(bars, monthly.values):
    ax.text(bar.get_x() + bar.get_width()/2, val + 20, f'{val:,}', ha='center', fontsize=12, fontweight='bold')
ax.set_ylabel('Number of Events', fontsize=13)
ax.set_title('Traffic Events by Month', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("events_monthly")

# Fig 8: Daily timeline
daily_ts = df.groupby('date').size()
fig, ax = plt.subplots(figsize=(16, 7))
ax.plot(daily_ts.index, daily_ts.values, color='#3498db', linewidth=0.8, alpha=0.7)
rolling = daily_ts.rolling(7, center=True).mean()
ax.plot(rolling.index, rolling.values, color='#e74c3c', linewidth=2.5, label='7-day moving avg')
ax.set_xlabel('Date', fontsize=13)
ax.set_ylabel('Daily Events', fontsize=13)
ax.set_title('Daily Traffic Events Timeline (Nov 2023 - Apr 2024)', fontsize=15, fontweight='bold')
ax.legend(fontsize=12)
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
save_fig("events_daily_timeline")

# Fig 9: Hour x Day heatmap
heatmap_data = df.groupby(['day_of_week', 'hour']).size().unstack(fill_value=0)
day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
heatmap_data.index = day_labels

fig, ax = plt.subplots(figsize=(16, 7))
sns.heatmap(heatmap_data, cmap='YlOrRd', annot=True, fmt='d', ax=ax,
            xticklabels=[f'{h:02d}' for h in range(24)],
            cbar_kws={'label': 'Event Count'}, annot_kws={'fontsize': 7})
ax.set_xlabel('Hour of Day (UTC)', fontsize=13)
ax.set_ylabel('Day of Week', fontsize=13)
ax.set_title('Event Density Heatmap: Hour x Day of Week', fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("events_heatmap_hour_day")

# ---- 5. DURATION & RESOLUTION ANALYSIS ----
print("\n" + "-" * 70)
print("5. DURATION & RESOLUTION ANALYSIS")
print("-" * 70)

# Calculate event duration (start to close/resolve)
df['duration_hours'] = (df['closed_datetime_parsed'] - df['start_datetime']).dt.total_seconds() / 3600
df['resolution_hours'] = (df['resolved_datetime'] - df['start_datetime']).dt.total_seconds() / 3600

valid_durations = df[df['duration_hours'].notna() & (df['duration_hours'] > 0) & (df['duration_hours'] < 720)]
print(f"\n  Events with valid close time: {len(valid_durations):,}")
print(f"  Duration stats (hours):")
print(f"    Mean:   {valid_durations['duration_hours'].mean():.1f}")
print(f"    Median: {valid_durations['duration_hours'].median():.1f}")
print(f"    P90:    {valid_durations['duration_hours'].quantile(0.9):.1f}")
print(f"    Max:    {valid_durations['duration_hours'].max():.1f}")

# Duration by cause
dur_by_cause = valid_durations.groupby('event_cause')['duration_hours'].agg(['mean', 'median', 'count'])
dur_by_cause = dur_by_cause.sort_values('median', ascending=False)
dur_by_cause = dur_by_cause[dur_by_cause['count'] >= 10]
print("\n  Median duration by cause (hours):")
for cause, row in dur_by_cause.iterrows():
    print(f"    {cause:25s} | median={row['median']:.1f}h, mean={row['mean']:.1f}h (n={int(row['count'])})")

# Fig 10: Duration distribution
fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# Histogram
axes[0].hist(valid_durations['duration_hours'], bins=50, color='#3498db', edgecolor='white', range=(0, 50))
axes[0].axvline(valid_durations['duration_hours'].median(), color='red', linestyle='--', linewidth=2, label=f'Median: {valid_durations["duration_hours"].median():.1f}h')
axes[0].set_xlabel('Duration (hours)', fontsize=13)
axes[0].set_ylabel('Count', fontsize=13)
axes[0].set_title('Event Duration Distribution', fontsize=14, fontweight='bold')
axes[0].legend(fontsize=12)

# Boxplot by cause
dur_by_cause_box = valid_durations[valid_durations['event_cause'].isin(dur_by_cause.head(8).index)]
cause_order = dur_by_cause.head(8).index.tolist()
sns.boxplot(data=dur_by_cause_box, x='duration_hours', y='event_cause', order=cause_order,
            ax=axes[1], palette='Set2', showfliers=False)
axes[1].set_xlabel('Duration (hours)', fontsize=13)
axes[1].set_ylabel('')
axes[1].set_title('Event Duration by Cause (capped at P95)', fontsize=14, fontweight='bold')
axes[1].set_xlim(0, valid_durations['duration_hours'].quantile(0.95))
plt.tight_layout()
save_fig("event_duration_analysis")

# ---- 6. STATUS ANALYSIS ----
print("\n" + "-" * 70)
print("6. STATUS ANALYSIS")
print("-" * 70)

status_counts = df['status'].value_counts()
print("\nEvent status:")
for s, c in status_counts.items():
    print(f"  {s:15s} | {c:>5,} ({c/len(df)*100:.1f}%)")

# Fig 11: Status by cause
status_cause = df.groupby(['event_cause', 'status']).size().unstack(fill_value=0)
status_cause = status_cause.loc[cause_counts.index]

fig, ax = plt.subplots(figsize=(14, 9))
status_cause.plot(kind='barh', stacked=True, ax=ax, colormap='Set3', edgecolor='white', linewidth=0.3)
ax.set_xlabel('Count', fontsize=13)
ax.set_title('Event Status by Cause', fontsize=15, fontweight='bold')
ax.legend(title='Status', fontsize=10)
ax.invert_yaxis()
plt.tight_layout()
save_fig("event_status_by_cause")

# ---- 7. CORRIDOR & PRIORITY ANALYSIS ----
print("\n" + "-" * 70)
print("7. CORRIDOR & PRIORITY ANALYSIS")
print("-" * 70)

corridor_counts = df['corridor'].value_counts()
print(f"\n  Total unique corridors: {len(corridor_counts)}")
print("\nTop 15 corridors:")
for corr, count in corridor_counts.head(15).items():
    print(f"  {corr:30s} | {count:>5,}")

priority_counts = df['priority'].value_counts()
print("\nPriority levels:")
for p, c in priority_counts.items():
    print(f"  {p:10s} | {c:>5,} ({c/len(df)*100:.1f}%)")

# Fig 12: Top corridors
top_corridors = corridor_counts.head(20)
fig, ax = plt.subplots(figsize=(14, 10))
colors_c = plt.cm.viridis(np.linspace(0.2, 0.8, len(top_corridors)))
ax.barh(range(len(top_corridors)), top_corridors.values, color=colors_c)
ax.set_yticks(range(len(top_corridors)))
ax.set_yticklabels(top_corridors.index, fontsize=10)
ax.set_xlabel('Number of Events', fontsize=13)
ax.set_title('Top 20 Corridors by Event Count', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, val in enumerate(top_corridors.values):
    ax.text(val + 5, i, f'{val:,}', va='center', fontsize=9)
plt.tight_layout()
save_fig("events_top_corridors")

# Fig 13: Priority x Cause heatmap
priority_cause = df.groupby(['event_cause', 'priority']).size().unstack(fill_value=0)

fig, ax = plt.subplots(figsize=(10, 9))
sns.heatmap(priority_cause, cmap='YlOrRd', annot=True, fmt='d', ax=ax,
            cbar_kws={'label': 'Event Count'})
ax.set_title('Event Cause vs Priority Level', fontsize=15, fontweight='bold')
ax.set_ylabel('')
plt.tight_layout()
save_fig("priority_vs_cause")

# ---- 8. SPATIAL DISTRIBUTION ----
print("\n" + "-" * 70)
print("8. SPATIAL DISTRIBUTION")
print("-" * 70)

lat_mask = (df['latitude'] > 12.7) & (df['latitude'] < 13.4)
lon_mask = (df['longitude'] > 77.3) & (df['longitude'] < 77.9)
df_geo = df[lat_mask & lon_mask].copy()
print(f"\n  Records with valid coordinates: {len(df_geo):,} / {len(df):,}")

# Fig 14: Spatial scatter by cause
fig, ax = plt.subplots(figsize=(14, 14))
cause_list = cause_counts.head(6).index.tolist()
colors_scatter = sns.color_palette("bright", len(cause_list))
for i, cause in enumerate(cause_list):
    subset = df_geo[df_geo['event_cause'] == cause]
    ax.scatter(subset['longitude'], subset['latitude'], s=8, alpha=0.4, 
               label=f'{cause} ({len(subset):,})', color=colors_scatter[i])
others = df_geo[~df_geo['event_cause'].isin(cause_list)]
ax.scatter(others['longitude'], others['latitude'], s=5, alpha=0.2, color='gray', label=f'others ({len(others):,})')
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title(f'Spatial Distribution of {len(df_geo):,} Traffic Events by Cause', fontsize=15, fontweight='bold')
ax.legend(fontsize=10, markerscale=3)
ax.set_aspect('equal')
plt.tight_layout()
save_fig("events_spatial_by_cause")

# Fig 15: Hexbin density
fig, ax = plt.subplots(figsize=(14, 14))
hb = ax.hexbin(df_geo['longitude'], df_geo['latitude'], gridsize=50, cmap='hot_r', mincnt=1)
plt.colorbar(hb, ax=ax, label='Event Count', shrink=0.7)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Traffic Event Density (Hexbin)', fontsize=15, fontweight='bold')
ax.set_aspect('equal')
plt.tight_layout()
save_fig("events_hexbin_density")

# ---- 9. VEHICLE BREAKDOWN DEEP DIVE ----
print("\n" + "-" * 70)
print("9. VEHICLE BREAKDOWN DEEP DIVE")
print("-" * 70)

breakdowns = df[df['event_cause'] == 'vehicle_breakdown'].copy()
print(f"\n  Vehicle breakdown events: {len(breakdowns):,}")

# Vehicle types in breakdowns
veh_type_bd = breakdowns['veh_type'].value_counts()
print("\n  Vehicle types in breakdowns:")
for vt, c in veh_type_bd.items():
    if str(vt) != 'nan' and str(vt) != 'NULL':
        print(f"    {vt:20s} | {c:>4,}")

# Fig 16: Breakdown vehicle types
valid_veh = breakdowns[breakdowns['veh_type'].notna() & (breakdowns['veh_type'] != 'NULL')]
veh_counts = valid_veh['veh_type'].value_counts()

fig, ax = plt.subplots(figsize=(12, 8))
colors_v = sns.color_palette("Spectral", len(veh_counts))
ax.barh(range(len(veh_counts)), veh_counts.values, color=colors_v)
ax.set_yticks(range(len(veh_counts)))
ax.set_yticklabels(veh_counts.index, fontsize=11)
ax.set_xlabel('Count', fontsize=13)
ax.set_title('Vehicle Types in Breakdown Events', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, val in enumerate(veh_counts.values):
    ax.text(val + 5, i, f'{val:,}', va='center', fontsize=10)
plt.tight_layout()
save_fig("breakdown_vehicle_types")

# ---- 10. POLICE STATION & ZONE ANALYSIS ----
print("\n" + "-" * 70)
print("10. POLICE STATION & ZONE ANALYSIS")
print("-" * 70)

station_counts = df['police_station'].value_counts()
print(f"\n  Unique police stations: {len(station_counts)}")
print("\n  Top 15 stations by event count:")
for stn, count in station_counts.head(15).items():
    print(f"    {stn:30s} | {count:>4,}")

# Fig 17: Top stations
top_stations = station_counts.head(20)
fig, ax = plt.subplots(figsize=(14, 10))
colors_s = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(top_stations)))
ax.barh(range(len(top_stations)), top_stations.values, color=colors_s)
ax.set_yticks(range(len(top_stations)))
ax.set_yticklabels(top_stations.index, fontsize=10)
ax.set_xlabel('Number of Events', fontsize=13)
ax.set_title('Top 20 Police Stations by Event Count', fontsize=15, fontweight='bold')
ax.invert_yaxis()
for i, val in enumerate(top_stations.values):
    ax.text(val + 3, i, f'{val:,}', va='center', fontsize=9)
plt.tight_layout()
save_fig("events_top_stations")

# Zone analysis
if 'zone' in df.columns:
    zone_counts = df['zone'].value_counts()
    # Filter out NULL
    zone_counts = zone_counts[zone_counts.index.astype(str) != 'NULL']
    zone_counts = zone_counts[zone_counts.index.astype(str) != 'nan']
    if len(zone_counts) > 0:
        print(f"\n  Zone distribution:")
        for z, c in zone_counts.items():
            print(f"    {z:30s} | {c:>4,}")

        # Fig 18: Zone distribution
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.bar(zone_counts.index, zone_counts.values, color=sns.color_palette("Set3", len(zone_counts)),
               edgecolor='white')
        ax.set_ylabel('Event Count', fontsize=13)
        ax.set_title('Traffic Events by Zone', fontsize=15, fontweight='bold')
        ax.tick_params(axis='x', rotation=45)
        for i, val in enumerate(zone_counts.values):
            ax.text(i, val + 5, f'{val:,}', ha='center', fontsize=10, fontweight='bold')
        plt.tight_layout()
        save_fig("events_by_zone")

# ---- 11. CONGESTION & ACCIDENT HOTSPOTS ----
print("\n" + "-" * 70)
print("11. CONGESTION & ACCIDENT HOTSPOTS")
print("-" * 70)

# Just congestion + accident events
cong_acc = df[df['event_cause'].isin(['congestion', 'accident'])].copy()
print(f"\n  Congestion events: {(df['event_cause']=='congestion').sum():,}")
print(f"  Accident events: {(df['event_cause']=='accident').sum():,}")
print(f"  Total: {len(cong_acc):,}")

# Top congestion corridors
cong_corridors = cong_acc.groupby('corridor').size().sort_values(ascending=False)
print("\n  Top congestion+accident corridors:")
for corr, count in cong_corridors.head(10).items():
    print(f"    {corr:30s} | {count:>4,}")

# Top congestion police stations
cong_stations = cong_acc.groupby('police_station').size().sort_values(ascending=False)
print("\n  Top congestion+accident stations:")
for stn, count in cong_stations.head(10).items():
    print(f"    {stn:30s} | {count:>4,}")

# Fig 19: Congestion+Accident spatial scatter
fig, ax = plt.subplots(figsize=(14, 14))
# Background: all events
ax.scatter(df_geo['longitude'], df_geo['latitude'], s=3, alpha=0.1, color='gray', label='All events')
# Overlay: congestion
cong_geo = cong_acc[(cong_acc['latitude'] > 12.7) & (cong_acc['latitude'] < 13.4) & 
                     (cong_acc['longitude'] > 77.3) & (cong_acc['longitude'] < 77.9)]
cong_only = cong_geo[cong_geo['event_cause'] == 'congestion']
acc_only = cong_geo[cong_geo['event_cause'] == 'accident']
ax.scatter(cong_only['longitude'], cong_only['latitude'], s=40, alpha=0.6, color='#e74c3c', 
           label=f'Congestion ({len(cong_only):,})', edgecolors='white', linewidth=0.3)
ax.scatter(acc_only['longitude'], acc_only['latitude'], s=40, alpha=0.6, color='#f39c12',
           label=f'Accident ({len(acc_only):,})', edgecolors='white', linewidth=0.3, marker='^')
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Congestion & Accident Event Locations', fontsize=15, fontweight='bold')
ax.legend(fontsize=12, markerscale=2)
ax.set_aspect('equal')
plt.tight_layout()
save_fig("congestion_accident_spatial")

# ---- 12. EVENT DESCRIPTION TEXT ANALYSIS ----
print("\n" + "-" * 70)
print("12. DESCRIPTION TEXT ANALYSIS")
print("-" * 70)

descriptions = df['description'].dropna()
descriptions = descriptions[descriptions.astype(str) != 'NULL']
print(f"\n  Events with descriptions: {len(descriptions):,} / {len(df):,} ({len(descriptions)/len(df)*100:.1f}%)")

# Common keywords
all_text = ' '.join(descriptions.astype(str).str.lower())
# Simple word frequency
words = all_text.split()
# Filter out common stop words and short words
stop_words = {'sir', 'the', 'to', 'is', 'in', 'and', 'of', 'at', 'on', 'for', 'a', 'from', 'near', 'due', 
              'no', 'not', 'has', 'have', 'was', 'are', 'been', 'will', 'one', 'towards', 'road', 'traffic',
              'null', 'nan', 'side', 'moving', 'junction'}
word_counts = Counter(w for w in words if len(w) > 2 and w not in stop_words)
top_words = word_counts.most_common(25)
print("\n  Top 25 keywords in descriptions:")
for word, count in top_words:
    print(f"    {word:20s} | {count:>5,}")

# Fig 20: Word frequency
fig, ax = plt.subplots(figsize=(14, 9))
words_list = [w for w, _ in top_words]
counts_list = [c for _, c in top_words]
ax.barh(range(len(words_list)), counts_list, color=sns.color_palette("mako", len(words_list)))
ax.set_yticks(range(len(words_list)))
ax.set_yticklabels(words_list, fontsize=11)
ax.set_xlabel('Frequency', fontsize=13)
ax.set_title('Top 25 Keywords in Event Descriptions', fontsize=15, fontweight='bold')
ax.invert_yaxis()
plt.tight_layout()
save_fig("event_description_keywords")

# ---- SUMMARY ----
print("\n" + "=" * 70)
print("SUMMARY STATISTICS")
print("=" * 70)

summary = {
    "Total Records": len(df),
    "Date Range": f"{df['start_datetime'].min()} to {df['start_datetime'].max()}",
    "Planned Events": f"{(df['event_type']=='planned').sum():,} ({(df['event_type']=='planned').sum()/len(df)*100:.1f}%)",
    "Unplanned Events": f"{(df['event_type']=='unplanned').sum():,} ({(df['event_type']=='unplanned').sum()/len(df)*100:.1f}%)",
    "Top Cause": f"{cause_counts.index[0]} ({cause_counts.iloc[0]:,})",
    "Congestion Events": f"{(df['event_cause']=='congestion').sum():,}",
    "Accident Events": f"{(df['event_cause']=='accident').sum():,}",
    "Public Events": f"{(df['event_cause']=='public_event').sum():,}",
    "Road Closures": f"{(df['requires_road_closure']==True).sum():,}",
    "Median Duration": f"{valid_durations['duration_hours'].median():.1f} hours",
    "Top Corridor": f"{corridor_counts.index[0]} ({corridor_counts.iloc[0]:,})",
    "Top Station": f"{station_counts.index[0]} ({station_counts.iloc[0]:,})",
    "Unique Corridors": f"{len(corridor_counts)}",
    "Unique Stations": f"{len(station_counts)}",
}

for k, v in summary.items():
    print(f"  {k:35s} | {v}")

print(f"\nAll graphs saved to: {RESEARCH_DIR}/")
print("Done!")

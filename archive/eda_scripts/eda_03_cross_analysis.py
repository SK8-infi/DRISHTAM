"""
EDA #3: Cross-Dataset Analysis — Violation × Event Correlation
================================================================
The critical test: Do parking violation hotspots correlate with
traffic congestion/incident hotspots?
All graphs saved to research/ folder.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
from scipy import stats
from sklearn.preprocessing import MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

# ---- Config ----
VIOLATION_PATH = r"c:\Github\Gridlock project\jan to may police violation_anonymized791b166.csv"
EVENT_PATH = r"c:\Github\Gridlock project\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
RESEARCH_DIR = Path(r"c:\Github\Gridlock project\research")

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
DPI = 150

def save_fig(name, fig=None):
    if fig is None:
        fig = plt.gcf()
    path = RESEARCH_DIR / f"03_{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  > Saved: {path.name}")
    return path

# ---- Load Data ----
print("=" * 70)
print("EDA #3: CROSS-DATASET CORRELATION ANALYSIS")
print("=" * 70)

print("\nLoading violation data...")
viol_df = pd.read_csv(VIOLATION_PATH, low_memory=False)
viol_df['created_datetime'] = pd.to_datetime(viol_df['created_datetime'], errors='coerce')
viol_df = viol_df.dropna(subset=['created_datetime']).copy()
print(f"  Violations: {len(viol_df):,} records")

print("Loading event data...")
event_df = pd.read_csv(EVENT_PATH, low_memory=False)
event_df['start_datetime'] = pd.to_datetime(event_df['start_datetime'], errors='coerce')
event_df = event_df.dropna(subset=['start_datetime']).copy()
print(f"  Events: {len(event_df):,} records")

# Filter to valid Bengaluru coordinates
viol_df = viol_df[(viol_df['latitude'] > 12.7) & (viol_df['latitude'] < 13.4) &
                   (viol_df['longitude'] > 77.3) & (viol_df['longitude'] < 77.9)].copy()
event_df = event_df[(event_df['latitude'] > 12.7) & (event_df['latitude'] < 13.4) &
                     (event_df['longitude'] > 77.3) & (event_df['longitude'] < 77.9)].copy()
print(f"  After geo-filter: {len(viol_df):,} violations, {len(event_df):,} events")

# =====================================================
# ANALYSIS 1: GRID-BASED SPATIAL CORRELATION
# =====================================================
print("\n" + "-" * 70)
print("1. GRID-BASED SPATIAL CORRELATION")
print("-" * 70)

# Create 500m x 500m grid cells
# At Bengaluru's latitude (~13N), 1 degree lat ≈ 111km, 1 degree lon ≈ 108km
# 500m ≈ 0.0045 degrees lat, 0.00463 degrees lon
GRID_SIZE_LAT = 0.0045  # ~500m
GRID_SIZE_LON = 0.00463  # ~500m

lat_min, lat_max = 12.8, 13.15
lon_min, lon_max = 77.4, 77.8

# Assign grid cells
def assign_grid(df, lat_col='latitude', lon_col='longitude'):
    df = df[(df[lat_col] >= lat_min) & (df[lat_col] <= lat_max) &
            (df[lon_col] >= lon_min) & (df[lon_col] <= lon_max)].copy()
    df['grid_row'] = ((df[lat_col] - lat_min) / GRID_SIZE_LAT).astype(int)
    df['grid_col'] = ((df[lon_col] - lon_min) / GRID_SIZE_LON).astype(int)
    df['grid_id'] = df['grid_row'].astype(str) + '_' + df['grid_col'].astype(str)
    return df

viol_grid = assign_grid(viol_df)
event_grid = assign_grid(event_df)

# Count per grid cell
viol_counts = viol_grid.groupby('grid_id').size().reset_index(name='violation_count')
event_counts = event_grid.groupby('grid_id').size().reset_index(name='event_count')

# Merge
grid_merged = pd.merge(viol_counts, event_counts, on='grid_id', how='outer').fillna(0)
grid_merged['violation_count'] = grid_merged['violation_count'].astype(int)
grid_merged['event_count'] = grid_merged['event_count'].astype(int)

# Grid cells with BOTH violations and events
both = grid_merged[(grid_merged['violation_count'] > 0) & (grid_merged['event_count'] > 0)]
viol_only = grid_merged[(grid_merged['violation_count'] > 0) & (grid_merged['event_count'] == 0)]
event_only = grid_merged[(grid_merged['violation_count'] == 0) & (grid_merged['event_count'] > 0)]

print(f"\n  Grid cells with violations only: {len(viol_only)}")
print(f"  Grid cells with events only: {len(event_only)}")
print(f"  Grid cells with BOTH: {len(both)}")
print(f"  Total grid cells with any data: {len(grid_merged)}")
print(f"  Co-occurrence rate: {len(both) / len(grid_merged) * 100:.1f}%")

# Correlation
active_cells = grid_merged[(grid_merged['violation_count'] > 0) | (grid_merged['event_count'] > 0)]
pearson_r, pearson_p = stats.pearsonr(active_cells['violation_count'], active_cells['event_count'])
spearman_r, spearman_p = stats.spearmanr(active_cells['violation_count'], active_cells['event_count'])

print(f"\n  Pearson correlation:  r={pearson_r:.4f}, p={pearson_p:.2e}")
print(f"  Spearman correlation: r={spearman_r:.4f}, p={spearman_p:.2e}")

# Fig 1: Scatter plot — violation count vs event count per grid cell
fig, axes = plt.subplots(1, 2, figsize=(20, 9))

# Raw scatter
ax = axes[0]
ax.scatter(active_cells['violation_count'], active_cells['event_count'], 
           alpha=0.3, s=20, c='#3498db', edgecolors='white', linewidth=0.3)
ax.set_xlabel('Violation Count per Grid Cell', fontsize=13)
ax.set_ylabel('Event Count per Grid Cell', fontsize=13)
ax.set_title(f'Violations vs Events per 500m Grid Cell\nPearson r={pearson_r:.3f} (p={pearson_p:.2e})', 
             fontsize=14, fontweight='bold')
# Regression line
z = np.polyfit(active_cells['violation_count'], active_cells['event_count'], 1)
p_line = np.poly1d(z)
x_line = np.linspace(0, active_cells['violation_count'].max(), 100)
ax.plot(x_line, p_line(x_line), 'r-', linewidth=2, label=f'OLS fit: y={z[0]:.3f}x + {z[1]:.1f}')
ax.legend(fontsize=11)

# Log-log scatter
ax = axes[1]
log_cells = active_cells[(active_cells['violation_count'] > 0) & (active_cells['event_count'] > 0)]
ax.scatter(np.log10(log_cells['violation_count']), np.log10(log_cells['event_count']),
           alpha=0.4, s=25, c='#e74c3c', edgecolors='white', linewidth=0.3)
ax.set_xlabel('log10(Violation Count)', fontsize=13)
ax.set_ylabel('log10(Event Count)', fontsize=13)
log_r, log_p = stats.pearsonr(np.log10(log_cells['violation_count']), np.log10(log_cells['event_count']))
ax.set_title(f'Log-Log Scatter (cells with both)\nPearson r={log_r:.3f} (p={log_p:.2e})', 
             fontsize=14, fontweight='bold')
# Fit line
z2 = np.polyfit(np.log10(log_cells['violation_count']), np.log10(log_cells['event_count']), 1)
p2 = np.poly1d(z2)
x2 = np.linspace(np.log10(log_cells['violation_count']).min(), np.log10(log_cells['violation_count']).max(), 100)
ax.plot(x2, p2(x2), 'b-', linewidth=2, label=f'OLS: y={z2[0]:.2f}x + {z2[1]:.2f}')
ax.legend(fontsize=11)

plt.suptitle('Spatial Correlation: Parking Violations vs Traffic Events', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig("grid_scatter_correlation")

# Fig 2: Binned analysis — group cells by violation quartile
grid_merged_active = grid_merged[grid_merged['violation_count'] > 0].copy()
grid_merged_active['viol_bin'] = pd.qcut(grid_merged_active['violation_count'], q=5, 
                                          labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
                                          duplicates='drop')
bin_stats = grid_merged_active.groupby('viol_bin', observed=True).agg(
    mean_events=('event_count', 'mean'),
    median_events=('event_count', 'median'),
    total_events=('event_count', 'sum'),
    cell_count=('event_count', 'count')
).reset_index()

print("\n  Events per violation quintile:")
for _, row in bin_stats.iterrows():
    print(f"    {row['viol_bin']:10s} | mean_events={row['mean_events']:.2f}, median={row['median_events']:.1f}, "
          f"total={int(row['total_events'])}, n_cells={int(row['cell_count'])}")

fig, axes = plt.subplots(1, 2, figsize=(18, 8))
# Mean events per quintile
colors_bin = ['#2ecc71', '#a3d977', '#f1c40f', '#e67e22', '#e74c3c']
axes[0].bar(bin_stats['viol_bin'], bin_stats['mean_events'], color=colors_bin, edgecolor='white')
for i, row in bin_stats.iterrows():
    axes[0].text(i, row['mean_events'] + 0.05, f'{row["mean_events"]:.2f}', ha='center', fontsize=12, fontweight='bold')
axes[0].set_xlabel('Violation Density Quintile', fontsize=13)
axes[0].set_ylabel('Mean Event Count per Cell', fontsize=13)
axes[0].set_title('Mean Traffic Events by Violation Density Quintile', fontsize=14, fontweight='bold')

# Total events per quintile
axes[1].bar(bin_stats['viol_bin'], bin_stats['total_events'], color=colors_bin, edgecolor='white')
for i, row in bin_stats.iterrows():
    axes[1].text(i, row['total_events'] + 10, f'{int(row["total_events"]):,}', ha='center', fontsize=11, fontweight='bold')
axes[1].set_xlabel('Violation Density Quintile', fontsize=13)
axes[1].set_ylabel('Total Event Count', fontsize=13)
axes[1].set_title('Total Traffic Events by Violation Density Quintile', fontsize=14, fontweight='bold')

plt.suptitle('THE HYPOTHESIS TEST: Do High-Violation Areas Have More Congestion?', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig("violation_quintile_vs_events")

# =====================================================
# ANALYSIS 2: POLICE STATION LEVEL CORRELATION
# =====================================================
print("\n" + "-" * 70)
print("2. POLICE STATION LEVEL CORRELATION")
print("-" * 70)

# Per-station counts
viol_station = viol_df.groupby('police_station').size().reset_index(name='violation_count')
event_station = event_df.groupby('police_station').size().reset_index(name='event_count')

station_merged = pd.merge(viol_station, event_station, on='police_station', how='outer').fillna(0)
station_merged = station_merged[station_merged['police_station'] != 'No Police Station']

station_r, station_p = stats.pearsonr(station_merged['violation_count'], station_merged['event_count'])
station_sr, station_sp = stats.spearmanr(station_merged['violation_count'], station_merged['event_count'])

print(f"\n  Stations with both: {len(station_merged)}")
print(f"  Pearson correlation:  r={station_r:.4f}, p={station_p:.4e}")
print(f"  Spearman correlation: r={station_sr:.4f}, p={station_sp:.4e}")

# Identify outlier stations (high violations but low events, or vice versa)
station_merged['viol_rank'] = station_merged['violation_count'].rank(ascending=False)
station_merged['event_rank'] = station_merged['event_count'].rank(ascending=False)
station_merged['rank_diff'] = abs(station_merged['viol_rank'] - station_merged['event_rank'])

print("\n  Top 10 stations by violation count (with event rank):")
top10_viol = station_merged.nlargest(10, 'violation_count')
for _, row in top10_viol.iterrows():
    print(f"    {row['police_station']:25s} | violations={int(row['violation_count']):>6,} (#{int(row['viol_rank'])}) "
          f"| events={int(row['event_count']):>4,} (#{int(row['event_rank'])})")

# Fig 3: Station-level scatter
fig, ax = plt.subplots(figsize=(14, 10))
ax.scatter(station_merged['violation_count'], station_merged['event_count'],
           s=80, alpha=0.7, c='#e74c3c', edgecolors='white', linewidth=1)

# Label top stations
for _, row in station_merged.nlargest(10, 'violation_count').iterrows():
    ax.annotate(row['police_station'], 
                xy=(row['violation_count'], row['event_count']),
                xytext=(10, 5), textcoords='offset points', fontsize=8,
                arrowprops=dict(arrowstyle='-', color='gray', alpha=0.5))
for _, row in station_merged.nlargest(5, 'event_count').iterrows():
    if row['police_station'] not in station_merged.nlargest(10, 'violation_count')['police_station'].values:
        ax.annotate(row['police_station'],
                    xy=(row['violation_count'], row['event_count']),
                    xytext=(10, -10), textcoords='offset points', fontsize=8, color='blue',
                    arrowprops=dict(arrowstyle='-', color='blue', alpha=0.5))

# Regression line
z = np.polyfit(station_merged['violation_count'], station_merged['event_count'], 1)
p_line = np.poly1d(z)
x_vals = np.linspace(0, station_merged['violation_count'].max(), 100)
ax.plot(x_vals, p_line(x_vals), 'b--', linewidth=2, alpha=0.7, label=f'OLS fit')
ax.set_xlabel('Violation Count', fontsize=13)
ax.set_ylabel('Event Count', fontsize=13)
ax.set_title(f'Police Station Level: Violations vs Events\nPearson r={station_r:.3f} (p={station_p:.4e}), '
             f'Spearman r={station_sr:.3f}', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
plt.tight_layout()
save_fig("station_correlation_scatter")

# Fig 4: Dual bar chart — Top 15 stations
top15 = station_merged.nlargest(15, 'violation_count').sort_values('violation_count', ascending=True)
fig, ax = plt.subplots(figsize=(14, 10))
y_pos = np.arange(len(top15))
bar_width = 0.35

# Normalize for dual axis
scaler_v = MinMaxScaler()
scaler_e = MinMaxScaler()
top15['viol_norm'] = scaler_v.fit_transform(top15[['violation_count']])
top15['event_norm'] = scaler_e.fit_transform(top15[['event_count']])

ax.barh(y_pos - bar_width/2, top15['violation_count'], bar_width, 
        color='#e74c3c', alpha=0.8, label='Violations')
ax2 = ax.twiny()
ax2.barh(y_pos + bar_width/2, top15['event_count'], bar_width, 
         color='#3498db', alpha=0.8, label='Events')
ax.set_yticks(y_pos)
ax.set_yticklabels(top15['police_station'], fontsize=10)
ax.set_xlabel('Violation Count', fontsize=12, color='#e74c3c')
ax2.set_xlabel('Event Count', fontsize=12, color='#3498db')
ax.set_title('Top 15 Stations: Violations vs Events Side by Side', fontsize=14, fontweight='bold')
ax.legend(loc='lower right', fontsize=11)
ax2.legend(loc='lower center', fontsize=11)
plt.tight_layout()
save_fig("station_dual_bar")

# =====================================================
# ANALYSIS 3: TEMPORAL CORRELATION
# =====================================================
print("\n" + "-" * 70)
print("3. TEMPORAL CORRELATION (Daily)")
print("-" * 70)

viol_df['date'] = viol_df['created_datetime'].dt.date
event_df['date'] = event_df['start_datetime'].dt.date

viol_daily = viol_df.groupby('date').size().reset_index(name='violations')
event_daily = event_df.groupby('date').size().reset_index(name='events')

temporal = pd.merge(viol_daily, event_daily, on='date', how='outer').fillna(0).sort_values('date')
temporal['date'] = pd.to_datetime(temporal['date'])

temp_r, temp_p = stats.pearsonr(temporal['violations'], temporal['events'])
temp_sr, temp_sp = stats.spearmanr(temporal['violations'], temporal['events'])

print(f"\n  Daily temporal correlation:")
print(f"  Pearson:  r={temp_r:.4f}, p={temp_p:.4e}")
print(f"  Spearman: r={temp_sr:.4f}, p={temp_sp:.4e}")

# Lag correlation analysis
print("\n  Cross-correlation (lag analysis):")
max_lag = 7
lag_corrs = []
for lag in range(-max_lag, max_lag + 1):
    if lag == 0:
        r, p = stats.pearsonr(temporal['violations'], temporal['events'])
    elif lag > 0:
        r, p = stats.pearsonr(temporal['violations'].iloc[:-lag], temporal['events'].iloc[lag:])
    else:
        r, p = stats.pearsonr(temporal['violations'].iloc[-lag:], temporal['events'].iloc[:lag])
    lag_corrs.append({'lag': lag, 'r': r, 'p': p})
    if abs(lag) <= 3:
        print(f"    Lag {lag:+d} day(s): r={r:.4f}, p={p:.4e}")
lag_df = pd.DataFrame(lag_corrs)

# Fig 5: Temporal dual-axis timeline
fig, ax1 = plt.subplots(figsize=(18, 8))

color1 = '#e74c3c'
color2 = '#3498db'
ax1.plot(temporal['date'], temporal['violations'], color=color1, alpha=0.4, linewidth=0.8)
viol_roll = temporal.set_index('date')['violations'].rolling(7).mean()
ax1.plot(viol_roll.index, viol_roll.values, color=color1, linewidth=2.5, label='Violations (7d avg)')
ax1.set_xlabel('Date', fontsize=13)
ax1.set_ylabel('Daily Violations', fontsize=13, color=color1)
ax1.tick_params(axis='y', labelcolor=color1)
ax1.tick_params(axis='x', rotation=45)

ax2 = ax1.twinx()
ax2.plot(temporal['date'], temporal['events'], color=color2, alpha=0.4, linewidth=0.8)
event_roll = temporal.set_index('date')['events'].rolling(7).mean()
ax2.plot(event_roll.index, event_roll.values, color=color2, linewidth=2.5, label='Events (7d avg)')
ax2.set_ylabel('Daily Events', fontsize=13, color=color2)
ax2.tick_params(axis='y', labelcolor=color2)

fig.legend(loc='upper right', bbox_to_anchor=(0.95, 0.95), fontsize=12)
ax1.set_title(f'Daily Violations vs Events Over Time\nPearson r={temp_r:.3f}, Spearman r={temp_sr:.3f}',
              fontsize=15, fontweight='bold')
plt.tight_layout()
save_fig("temporal_dual_timeline")

# Fig 6: Lag correlation bar chart
fig, ax = plt.subplots(figsize=(12, 6))
colors_lag = ['#e74c3c' if r > 0 else '#3498db' for r in lag_df['r']]
ax.bar(lag_df['lag'], lag_df['r'], color=colors_lag, edgecolor='white')
ax.set_xlabel('Lag (days)', fontsize=13)
ax.set_ylabel('Pearson Correlation', fontsize=13)
ax.set_title('Cross-Correlation: Violations Leading/Lagging Events', fontsize=15, fontweight='bold')
ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_xticks(range(-max_lag, max_lag+1))
best_lag = lag_df.loc[lag_df['r'].abs().idxmax()]
ax.annotate(f'Best: lag={int(best_lag["lag"])}, r={best_lag["r"]:.3f}', 
            xy=(best_lag['lag'], best_lag['r']),
            xytext=(best_lag['lag']+1.5, best_lag['r']),
            fontsize=11, fontweight='bold', color='red',
            arrowprops=dict(arrowstyle='->', color='red'))
plt.tight_layout()
save_fig("lag_correlation")

# =====================================================
# ANALYSIS 4: HOURLY PATTERN COMPARISON
# =====================================================
print("\n" + "-" * 70)
print("4. HOURLY PATTERN COMPARISON")
print("-" * 70)

viol_hourly = viol_df.groupby(viol_df['created_datetime'].dt.hour).size()
event_hourly = event_df.groupby(event_df['start_datetime'].dt.hour).size()

# Normalize to %
viol_hourly_pct = viol_hourly / viol_hourly.sum() * 100
event_hourly_pct = event_hourly / event_hourly.sum() * 100

hourly_r, hourly_p = stats.pearsonr(viol_hourly_pct.reindex(range(24), fill_value=0), 
                                     event_hourly_pct.reindex(range(24), fill_value=0))
print(f"\n  Hourly profile correlation: r={hourly_r:.4f}, p={hourly_p:.4e}")

# Fig 7: Hourly profiles overlay
fig, ax = plt.subplots(figsize=(16, 8))
hours = range(24)
ax.bar(np.array(list(hours)) - 0.2, viol_hourly_pct.reindex(hours, fill_value=0), 
       width=0.4, color='#e74c3c', alpha=0.7, label='Violations %')
ax.bar(np.array(list(hours)) + 0.2, event_hourly_pct.reindex(hours, fill_value=0),
       width=0.4, color='#3498db', alpha=0.7, label='Events %')
ax.set_xlabel('Hour of Day (UTC)', fontsize=13)
ax.set_ylabel('% of Total', fontsize=13)
ax.set_title(f'Hourly Profile Comparison: Violations vs Events\nProfile correlation: r={hourly_r:.3f}',
             fontsize=15, fontweight='bold')
ax.set_xticks(hours)
ax.set_xticklabels([f'{h:02d}\n({(h+5)%24:02d}:{30 if True else 0}0 IST)' for h in hours], fontsize=7)
ax.legend(fontsize=12)
plt.tight_layout()
save_fig("hourly_profile_comparison")

# =====================================================
# ANALYSIS 5: PROXIMITY ANALYSIS (300m radius)
# =====================================================
print("\n" + "-" * 70)
print("5. PROXIMITY ANALYSIS (300m radius)")
print("-" * 70)

from scipy.spatial import cKDTree

# Convert to radians for haversine-like distance
def haversine_dist(lat1, lon1, lat2, lon2):
    """Approximate distance in meters between two lat/lon points."""
    R = 6371000
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# Use KD-tree for efficient spatial queries
# Scale lat/lon to meters approximately
lat_to_m = 111000  # 1 degree lat ≈ 111km
lon_to_m = 108000  # at ~13N latitude

# Create coordinate arrays
viol_coords = np.column_stack([viol_df['latitude'].values * lat_to_m, 
                                viol_df['longitude'].values * lon_to_m])
event_coords = np.column_stack([event_df['latitude'].values * lat_to_m,
                                 event_df['longitude'].values * lon_to_m])

# Build KD-tree on violation locations
print("  Building spatial index...")
viol_tree = cKDTree(viol_coords)

# For each event, count violations within 300m
RADIUS = 300  # meters
print(f"  Counting violations within {RADIUS}m of each event...")

# Query the tree
event_nearby_counts = []
for i in range(len(event_coords)):
    nearby = viol_tree.query_ball_point(event_coords[i], r=RADIUS)
    event_nearby_counts.append(len(nearby))

event_df = event_df.copy()
event_df['nearby_violations'] = event_nearby_counts

# Statistics
print(f"\n  Events with 0 nearby violations: {(event_df['nearby_violations'] == 0).sum()} ({(event_df['nearby_violations'] == 0).sum()/len(event_df)*100:.1f}%)")
print(f"  Events with 1+ nearby violations: {(event_df['nearby_violations'] > 0).sum()} ({(event_df['nearby_violations'] > 0).sum()/len(event_df)*100:.1f}%)")
print(f"  Events with 10+ nearby violations: {(event_df['nearby_violations'] >= 10).sum()} ({(event_df['nearby_violations'] >= 10).sum()/len(event_df)*100:.1f}%)")
print(f"  Events with 50+ nearby violations: {(event_df['nearby_violations'] >= 50).sum()} ({(event_df['nearby_violations'] >= 50).sum()/len(event_df)*100:.1f}%)")
print(f"\n  Nearby violation stats:")
print(f"    Mean:   {event_df['nearby_violations'].mean():.1f}")
print(f"    Median: {event_df['nearby_violations'].median():.0f}")
print(f"    Max:    {event_df['nearby_violations'].max()}")

# By event cause
cause_nearby = event_df.groupby('event_cause')['nearby_violations'].agg(['mean', 'median', 'count']).sort_values('mean', ascending=False)
print("\n  Mean nearby violations by event cause:")
for cause, row in cause_nearby.iterrows():
    print(f"    {cause:25s} | mean={row['mean']:>7.1f}, median={row['median']:>5.0f} (n={int(row['count'])})")

# Fig 8: Nearby violations distribution
fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# Histogram
axes[0].hist(event_df['nearby_violations'], bins=50, color='#3498db', edgecolor='white', range=(0, 500))
axes[0].axvline(event_df['nearby_violations'].median(), color='red', linestyle='--', linewidth=2,
                label=f'Median: {event_df["nearby_violations"].median():.0f}')
axes[0].set_xlabel('Number of Violations within 300m', fontsize=13)
axes[0].set_ylabel('Count of Events', fontsize=13)
axes[0].set_title('How Many Violations Surround Each Traffic Event?', fontsize=14, fontweight='bold')
axes[0].legend(fontsize=12)

# By cause
top_causes = event_df['event_cause'].value_counts().head(8).index
cause_data = event_df[event_df['event_cause'].isin(top_causes)]
cause_order = cause_nearby.head(8).index.tolist()
cause_order_filtered = [c for c in cause_order if c in top_causes]
sns.boxplot(data=cause_data, x='nearby_violations', y='event_cause', order=cause_order_filtered,
            ax=axes[1], palette='Set2', showfliers=False)
axes[1].set_xlabel('Nearby Violations (within 300m)', fontsize=13)
axes[1].set_ylabel('')
axes[1].set_title('Nearby Violations by Event Cause', fontsize=14, fontweight='bold')
axes[1].set_xlim(0, event_df['nearby_violations'].quantile(0.95))

plt.suptitle('Proximity Analysis: Do Events Occur Near Parking Violations?', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig("proximity_analysis")

# =====================================================
# ANALYSIS 6: CONGESTION-SPECIFIC SPATIAL TEST
# =====================================================
print("\n" + "-" * 70)
print("6. CONGESTION-SPECIFIC SPATIAL TEST")
print("-" * 70)

# Compare nearby violations for different event causes
congestion_events = event_df[event_df['event_cause'] == 'congestion']
breakdown_events = event_df[event_df['event_cause'] == 'vehicle_breakdown']
accident_events = event_df[event_df['event_cause'] == 'accident']
all_events = event_df

print(f"\n  Congestion events nearby violations: mean={congestion_events['nearby_violations'].mean():.1f}, median={congestion_events['nearby_violations'].median():.0f}")
print(f"  Breakdown events nearby violations:  mean={breakdown_events['nearby_violations'].mean():.1f}, median={breakdown_events['nearby_violations'].median():.0f}")
print(f"  Accident events nearby violations:   mean={accident_events['nearby_violations'].mean():.1f}, median={accident_events['nearby_violations'].median():.0f}")
print(f"  ALL events nearby violations:        mean={all_events['nearby_violations'].mean():.1f}, median={all_events['nearby_violations'].median():.0f}")

# Mann-Whitney U test: do congestion events have more nearby violations than average?
if len(congestion_events) > 5:
    u_stat, u_pval = stats.mannwhitneyu(congestion_events['nearby_violations'], 
                                         event_df['nearby_violations'], alternative='greater')
    print(f"\n  Mann-Whitney U test (congestion > all): U={u_stat:.0f}, p={u_pval:.4f}")
    print(f"  {'SIGNIFICANT' if u_pval < 0.05 else 'NOT significant'} at p<0.05")

# =====================================================
# ANALYSIS 7: HIGH vs LOW VIOLATION ZONE COMPARISON
# =====================================================
print("\n" + "-" * 70)
print("7. HIGH vs LOW VIOLATION ZONE COMPARISON")
print("-" * 70)

# Divide grid cells into High and Low violation zones
median_viol = grid_merged_active['violation_count'].median()
high_viol_cells = set(grid_merged_active[grid_merged_active['violation_count'] >= grid_merged_active['violation_count'].quantile(0.75)]['grid_id'])
low_viol_cells = set(grid_merged_active[grid_merged_active['violation_count'] <= grid_merged_active['violation_count'].quantile(0.25)]['grid_id'])

# Events in high vs low violation zones
event_grid_tagged = event_grid.copy()
event_grid_tagged['zone_type'] = 'Medium'
event_grid_tagged.loc[event_grid_tagged['grid_id'].isin(high_viol_cells), 'zone_type'] = 'High Violation'
event_grid_tagged.loc[event_grid_tagged['grid_id'].isin(low_viol_cells), 'zone_type'] = 'Low Violation'

zone_event_counts = event_grid_tagged.groupby('zone_type').size()
zone_event_rates = event_grid_tagged.groupby('zone_type').size() / event_grid_tagged.groupby('zone_type')['grid_id'].nunique()

print(f"\n  High violation zone events: {zone_event_counts.get('High Violation', 0):,}")
print(f"  Low violation zone events:  {zone_event_counts.get('Low Violation', 0):,}")
print(f"  Medium zone events:         {zone_event_counts.get('Medium', 0):,}")
print(f"\n  Event rate per grid cell:")
for zone, rate in zone_event_rates.items():
    print(f"    {zone:20s} | {rate:.2f} events/cell")

if 'High Violation' in zone_event_rates.index and 'Low Violation' in zone_event_rates.index:
    ratio = zone_event_rates['High Violation'] / zone_event_rates['Low Violation']
    print(f"\n  >>> High-violation zones have {ratio:.1f}x more events per cell than low-violation zones <<<")

# Fig 9: High vs Low comparison
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# Event count comparison
zone_order = ['Low Violation', 'Medium', 'High Violation']
zone_colors = ['#2ecc71', '#f39c12', '#e74c3c']
rates = [zone_event_rates.get(z, 0) for z in zone_order]
axes[0].bar(zone_order, rates, color=zone_colors, edgecolor='white')
for i, r in enumerate(rates):
    axes[0].text(i, r + 0.05, f'{r:.2f}', ha='center', fontsize=14, fontweight='bold')
axes[0].set_ylabel('Events per Grid Cell', fontsize=13)
axes[0].set_title('Event Rate by Violation Zone Type', fontsize=14, fontweight='bold')

# Event cause breakdown in high vs low
for zone_label, ax_col, color in [('High Violation', 1, '#e74c3c')]:
    zone_events = event_grid_tagged[event_grid_tagged['zone_type'] == zone_label]
    cause_dist = zone_events['event_cause'].value_counts().head(8)
    axes[1].barh(range(len(cause_dist)), cause_dist.values, color=sns.color_palette("Set2", len(cause_dist)))
    axes[1].set_yticks(range(len(cause_dist)))
    axes[1].set_yticklabels(cause_dist.index, fontsize=10)
    axes[1].set_xlabel('Count', fontsize=13)
    axes[1].set_title(f'Event Causes in High-Violation Zones', fontsize=14, fontweight='bold')
    axes[1].invert_yaxis()

plt.suptitle(f'High vs Low Violation Zones: Event Comparison\nHigh-violation zones have {ratio:.1f}x more events/cell',
             fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
save_fig("high_vs_low_violation_zones")

# =====================================================
# ANALYSIS 8: SIDE-BY-SIDE DENSITY MAP
# =====================================================
print("\n" + "-" * 70)
print("8. SIDE-BY-SIDE SPATIAL DENSITY COMPARISON")
print("-" * 70)

fig, axes = plt.subplots(1, 2, figsize=(22, 12))

# Violation density
hb1 = axes[0].hexbin(viol_df['longitude'], viol_df['latitude'], 
                      gridsize=60, cmap='YlOrRd', mincnt=1)
plt.colorbar(hb1, ax=axes[0], label='Count', shrink=0.7)
axes[0].set_xlabel('Longitude', fontsize=12)
axes[0].set_ylabel('Latitude', fontsize=12)
axes[0].set_title('Parking Violation Density\n(298K records)', fontsize=14, fontweight='bold')
axes[0].set_aspect('equal')

# Event density
hb2 = axes[1].hexbin(event_df['longitude'], event_df['latitude'],
                      gridsize=60, cmap='YlGnBu', mincnt=1)
plt.colorbar(hb2, ax=axes[1], label='Count', shrink=0.7)
axes[1].set_xlabel('Longitude', fontsize=12)
axes[1].set_ylabel('Latitude', fontsize=12)
axes[1].set_title('Traffic Event Density\n(8K records)', fontsize=14, fontweight='bold')
axes[1].set_aspect('equal')

# Match axes
for ax in axes:
    ax.set_xlim(77.4, 77.8)
    ax.set_ylim(12.8, 13.15)

plt.suptitle('Side-by-Side Spatial Comparison: Violations vs Events', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
save_fig("side_by_side_density")

# =====================================================
# ANALYSIS 9: OVERLAY DENSITY MAP
# =====================================================
print("\n" + "-" * 70)
print("9. OVERLAY DENSITY MAP")
print("-" * 70)

# Create grid-based heatmaps for both datasets and overlay
grid_lat = np.arange(lat_min, lat_max, GRID_SIZE_LAT)
grid_lon = np.arange(lon_min, lon_max, GRID_SIZE_LON)

# Create 2D histograms
viol_hist, _, _ = np.histogram2d(viol_df['latitude'], viol_df['longitude'],
                                  bins=[grid_lat, grid_lon])
event_hist, _, _ = np.histogram2d(event_df['latitude'], event_df['longitude'],
                                   bins=[grid_lat, grid_lon])

# Normalize both to 0-1
viol_norm = viol_hist / viol_hist.max() if viol_hist.max() > 0 else viol_hist
event_norm = event_hist / event_hist.max() if event_hist.max() > 0 else event_hist

# Create RGB overlay: Red = violations, Blue = events, Purple = both
overlay = np.zeros((*viol_norm.shape, 3))
overlay[:, :, 0] = viol_norm  # Red channel = violations
overlay[:, :, 2] = event_norm  # Blue channel = events

fig, ax = plt.subplots(figsize=(14, 14))
ax.imshow(overlay, origin='lower', extent=[lon_min, lon_max, lat_min, lat_max], aspect='auto', alpha=0.9)
ax.set_xlabel('Longitude', fontsize=13)
ax.set_ylabel('Latitude', fontsize=13)
ax.set_title('Violation-Event Overlay Map\nRed = Violations Only | Blue = Events Only | Purple = BOTH',
             fontsize=15, fontweight='bold')

# Add legend patches
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='red', label='High Violations Only'),
    Patch(facecolor='blue', label='High Events Only'),
    Patch(facecolor='purple', label='Both High (Correlation Zone)'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=12)
plt.tight_layout()
save_fig("overlay_density_map")

# =====================================================
# SUMMARY
# =====================================================
print("\n" + "=" * 70)
print("CROSS-DATASET CORRELATION SUMMARY")
print("=" * 70)

print(f"""
  SPATIAL CORRELATION (500m grid):
    Pearson r  = {pearson_r:.4f} (p={pearson_p:.2e})
    Spearman r = {spearman_r:.4f} (p={spearman_p:.2e})
    Log-log r  = {log_r:.4f} (p={log_p:.2e})

  STATION-LEVEL CORRELATION:
    Pearson r  = {station_r:.4f} (p={station_p:.4e})
    Spearman r = {station_sr:.4f} (p={station_sp:.4e})

  TEMPORAL CORRELATION (daily):
    Pearson r  = {temp_r:.4f} (p={temp_p:.4e})
    Spearman r = {temp_sr:.4f} (p={temp_sp:.4e})

  HOURLY PROFILE CORRELATION:
    Pearson r  = {hourly_r:.4f} (p={hourly_p:.4e})

  PROXIMITY ANALYSIS (300m):
    Mean violations near events: {event_df['nearby_violations'].mean():.1f}
    Events with 10+ nearby violations: {(event_df['nearby_violations'] >= 10).sum()/len(event_df)*100:.1f}%

  ZONE COMPARISON:
    High-violation zones: {ratio:.1f}x more events per cell than low-violation zones

  All graphs saved to: {RESEARCH_DIR}/
""")
print("Done!")

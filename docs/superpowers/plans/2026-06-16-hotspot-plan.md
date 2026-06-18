# Hotspot Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement hotspot detection using DBSCAN and analyze clusters.

**Architecture:** Load `location_cluster_input.csv`, run DBSCAN, join with original dataset on rounded lat/lon, aggregate, and save to `hotspot_clusters.csv`.

**Tech Stack:** Python, pandas, scikit-learn.

---

### Task 1: Setup Test Structure

**Files:**
- Create: `tests/test_hotspot.py`

- [ ] **Step 1: Create initial test file**

```python
import pytest
import pandas as pd
import os
from src.hotspot import run_hotspot_detection

def test_hotspot_detection_runs():
    # Create dummy data
    input_df = pd.DataFrame({
        'latitude': [12.9255, 12.9254, 13.0, 13.01],
        'longitude': [77.6186, 77.6185, 77.5, 77.51],
        'severity_score': [2, 5, 1, 3]
    })
    input_df.to_csv('data/location_cluster_input.csv', index=False)
    
    # Create minimal original data
    orig_df = pd.DataFrame({
        'latitude': [12.9255, 12.9254, 13.0, 13.01],
        'longitude': [77.6186, 77.6185, 77.5, 77.51],
        'violation_type': ['No Parking', 'No Parking', 'Speeding', 'Speeding'],
        'vehicle_type': ['Car', 'Car', 'Bike', 'Bike'],
        'police_station': ['PS1', 'PS1', 'PS2', 'PS2'],
        'junction_name': ['J1', 'J1', 'No Junction', 'No Junction']
    })
    orig_df.to_csv('jan to may police violation_anonymized791b166.csv', index=False)
    
    # Run
    run_hotspot_detection()
    
    # Verify
    assert os.path.exists('data/hotspot_clusters.csv')
```

### Task 2: Implement Hotspot Detection

**Files:**
- Create: `src/hotspot.py`

- [ ] **Step 1: Implement `run_hotspot_detection`**

```python
import pandas as pd
from sklearn.cluster import DBSCAN

def run_hotspot_detection():
    # Load
    input_df = pd.read_csv('data/location_cluster_input.csv')
    
    # Cluster
    db = DBSCAN(eps=0.003, min_samples=10).fit(input_df[['latitude', 'longitude']])
    input_df['cluster'] = db.labels_
    
    # Filter noise
    clusters = input_df[input_df['cluster'] != -1]
    
    # Load original for join (using rounded lat/lon to 4 decimal places)
    orig_df = pd.read_csv('jan to may police violation_anonymized791b166.csv')
    orig_df['lat_r'] = orig_df['latitude'].round(4)
    orig_df['lon_r'] = orig_df['longitude'].round(4)
    clusters['lat_r'] = clusters['latitude'].round(4)
    clusters['lon_r'] = clusters['longitude'].round(4)
    
    # Merge
    merged = clusters.merge(orig_df, on=['lat_r', 'lon_r'], how='left')
    
    # Aggregate
    agg = merged.groupby('cluster').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'severity_score': 'mean',
        'violation_type': lambda x: x.mode()[0] if not x.mode().empty else 'Unknown',
        'vehicle_type': lambda x: x.mode()[0] if not x.mode().empty else 'Unknown',
        'police_station': lambda x: x.mode()[0] if not x.mode().empty else 'Unknown',
        'junction_name': 'first' # Simplified for demo
    })
    
    agg['violation_count'] = merged.groupby('cluster').size()
    
    # Calculate congestion score
    agg['junction_density_flag'] = agg['junction_name'].apply(lambda x: 1 if x != 'No Junction' else 0.5)
    agg['congestion_score'] = agg['violation_count'] * agg['severity_score'] * agg['junction_density_flag']
    
    # Calculate risk tier
    agg['risk_val'] = agg['violation_count'] * agg['severity_score']
    agg = agg.sort_values('risk_val', ascending=False)
    
    def get_tier(i):
        if i < 10: return 'Critical'
        if i < 30: return 'High'
        return 'Moderate'
        
    agg['risk_tier'] = [get_tier(i) for i in range(len(agg))]
    
    agg.to_csv('data/hotspot_clusters.csv')
```

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

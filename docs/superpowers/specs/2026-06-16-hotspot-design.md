# Hotspot Detection Design

**Goal:** Detect illegal parking hotspots and quantify their impact to enable targeted enforcement.

**Architecture:**
1. **Load Data:** Read `data/location_cluster_input.csv` (lat, lon, severity_score).
2. **Cluster:** Run `DBSCAN` with `eps=0.003` and `min_samples=10` on `latitude` and `longitude`.
3. **Merge:** Join clustered data with the original dataset `jan to may police violation_anonymized791b166.csv` using rounded latitude and longitude (4 decimal places).
4. **Analyze Clusters:**
   - Compute centroid (mean lat/lon).
   - Compute violation count (number of violations in cluster).
   - Compute mean severity score.
   - Compute mode (dominant) of violation type, vehicle type, and police station.
   - Assign risk tier: Critical (top 10 by count*severity), High (next 20), Moderate (remaining).
   - Calculate congestion score = `violation_count` * `mean_severity` * `junction_density_flag`.
5. **Output:** Save results to `data/hotspot_clusters.csv`.

**Tech Stack:**
- Python
- pandas
- scikit-learn (DBSCAN)

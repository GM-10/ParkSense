# MapMyIndia Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Mappls JS SDK for visualization and implement Reverse Geocoding for hotspot enrichment.

**Architecture:** Use `st.components.v1.html` for map visualization. Use Mappls API to enrich cluster centroids with locality names in `src/hotspot.py`.

**Tech Stack:** `streamlit`, `requests`, Mappls API.

---

### Task 1: Pipeline & Hotspot Enrichment

**Files:**
- Modify: `src/pipeline.py`
- Modify: `src/hotspot.py`

- [ ] **Step 1: Pipeline Update**
Update `process_data` to derive `day_of_week`.

- [ ] **Step 2: Hotspot Reverse Geocoding**
Modify `src/hotspot.py`: 
- Implement a helper to call Mappls Reverse Geocode API (`https://apis.mappls.com/advancedmaps/v1/{key}/rev_geocode?lat={lat}&lng={lon}`) for cluster centroids.
- Store results in `locality_name` column of `hotspot_clusters.csv`.

- [ ] **Step 3: Commit**
```bash
git add src/pipeline.py src/hotspot.py
git commit -m "feat: integrate mappls reverse geocoding"
```

---

### Task 2: Dashboard Visualization Overhaul

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Replace Folium with Mappls JS SDK**
Remove `folium` logic in Tab 1. Use `st.components.v1.html` to inject Mappls map code.
- Ensure the map receives marker/heatmap data as JSON from Python.

- [ ] **Step 2: Verification**
Verify the map renders correctly with locality names from `hotspot_clusters.csv` in popups.

- [ ] **Step 3: Commit**
```bash
git add app.py
git commit -m "feat: replace folium with mappls sdk"
```

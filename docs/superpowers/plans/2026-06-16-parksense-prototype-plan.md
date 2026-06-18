# ParkSense Competition Prototype Implementation Plan

**Goal:** Implement the 4-component traffic intelligence system (Data Pipeline, Hotspot Detection, Dashboard, AI Agent).

---

### Task 1: Component 1 — Data Pipeline (`src/pipeline.py`)

**Files:**
- Create: `src/pipeline.py`
- Modify: `requirements.txt` (if needed)

- [ ] **Step 1: Write `src/pipeline.py`**
Implement functionality to load `data/jan_to_may_police_violation_anonymized791b166.csv`, parse JSON arrays in `violation_type` and `offence_code`, calculate `violation_severity_score` based on the specified weights, extract hour/month from `created_datetime`, and aggregate to generate `junction_summary.csv`, `police_station_summary.csv`, and `location_cluster_input.csv`.

- [ ] **Step 2: Verify Pipeline**
Run `src/pipeline.py` and verify all three output CSVs are generated correctly in `data/`.

- [ ] **Step 3: Commit**

---

### Task 2: Component 2 — Hotspot Detection (`src/hotspot.py`)

**Files:**
- Create: `src/hotspot.py`

- [ ] **Step 1: Write `src/hotspot.py`**
Implement DBSCAN clustering on `location_cluster_input.csv` using `eps=0.003` and `min_samples=10`. Assign risk tiers (Critical, High, Moderate) based on the derived `congestion_score`. Output `hotspot_clusters.csv`.

- [ ] **Step 2: Verify Clustering**
Run `src/hotspot.py` and inspect `hotspot_clusters.csv` to ensure clusters map meaningfully to high-violation areas.

- [ ] **Step 3: Commit**

---

### Task 3: Component 3 — Interactive Dashboard (`app.py`)

**Files:**
- Create: `app.py`

- [ ] **Step 1: Implement Dashboard UI**
Build a Streamlit app with 3 tabs:
- Tab 1: Hotspot Map (Folium) with heatmap and risk-tier markers.
- Tab 2: Temporal Analysis (Plotly charts for hours/months/vehicle types).
- Tab 3: Placeholder for AI Agent.

- [ ] **Step 2: Verify Dashboard**
Run `streamlit run app.py` and ensure all tabs are populated with data.

- [ ] **Step 3: Commit**

---

### Task 4: Component 4 — AI Enforcement Agent (`src/agent.py`)

**Files:**
- Modify: `src/agent.py`

- [ ] **Step 1: Setup ChromaDB**
Implement the RAG setup in `src/agent.py` to ingest `junction_summary.csv` and `police_station_summary.csv` into ChromaDB.

- [ ] **Step 2: Implement LangChain RAG Chain**
Refine the prompt for the Groq-powered agent as specified.

- [ ] **Step 3: Integrate Chat Interface**
Connect the agent to the `app.py` Tab 3.

- [ ] **Step 4: Verify Agent**
Test the 5 example queries to ensure structured, bilingual (EN/KN) responses.

- [ ] **Step 5: Final Commit**

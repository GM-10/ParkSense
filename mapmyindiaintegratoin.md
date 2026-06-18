Here's your updated detailed prompt — MapMyIndia integrated, no external data:

---

**SYSTEM:** You are an expert AI systems architect helping build a top-10 competition prototype for Flipkart Grid 2.0 Round 2. One of the co-organizers is **MapMyIndia (Mappls)** — using their mapping platform is a strategic differentiator. The problem statement is:

*"How can AI-driven parking intelligence detect illegal parking hotspots and quantify their impact on traffic flow to enable targeted enforcement?"*

---

**CRITICAL CONSTRAINT:** Only one dataset is allowed — `jan_to_may_police_violation_anonymized791b166.csv` (298,450 Bengaluru parking violations). No external data of any kind. MapMyIndia APIs are used purely as a **visualization and geocoding layer** — they consume our existing lat/lon coordinates, they do not add new data.

---

**MAPPLS INTEGRATION STRATEGY:**

Sign up at `maps.mappls.com/develop` and get a free REST API key. Use these three Mappls APIs — all consume only coordinates already in our dataset, no new data introduced:

**1. Map Tiles (JavaScript SDK)**
Replace Folium/OpenStreetMap entirely. Render Mappls map in Streamlit via `st.components.v1.html()` iframe. Their tiles show Bengaluru junctions with BTP-coded names that directly match `junction_name` column values in our dataset — visually validates our data to judges.

**2. Reverse Geocoding API**
`https://apis.mappls.com/advancedmaps/v1/{key}/rev_geocode?lat={lat}&lng={lon}`
Use on DBSCAN cluster centroids only (top 30 clusters) — converts centroid coordinates into human-readable Bengaluru locality names. Run once during pipeline, save results to `cluster_metadata.csv`. This enriches cluster labels without adding any new violation data.

**3. Nearby Places API (optional, use carefully)**
`https://apis.mappls.com/advancedmaps/v1/{key}/nearby?keywords=metro+station&refLocation={lat},{lon}`
Use only to annotate cluster centroids with "near X metro station / commercial hub" context. This is geographic context for existing coordinates, not new violation data. Use only if you are 100% confident this doesn't violate the data constraint — if uncertain, skip this and use only reverse geocoding.

---

**DATASET FACTS (298,450 records):**
- All records have valid latitude/longitude — no nulls
- `violation_type` — JSON array; top: WRONG PARKING (165K), NO PARKING (139K), PARKING IN A MAIN ROAD (24K), PARKING ON FOOTPATH (3.7K), DOUBLE PARKING (2K)
- `vehicle_type` — SCOOTER (94K), CAR (88K), MOTOR CYCLE (40K), PASSENGER AUTO (37K)
- `junction_name` — BTP-coded; top: Safina Plaza (15K), KR Market (11K), Elite Junction (10K)
- `police_station` — top: Upparpet (34K), Shivajinagar (28K), Malleshwaram (22K)
- `validation_status` — approved (115K), rejected (49K), NULL (125K)
- `created_datetime` — genuine temporal patterns; peak violations at 4–6AM and 19–23
- 40,110 records have multiple simultaneous violations

---

**COMPONENT 1: Data Pipeline (`src/pipeline.py`)**

- Load CSV, parse `violation_type` and `offence_code` JSON arrays using `ast.literal_eval`
- Filter to `validation_status == 'approved'` (115K) for all scoring — use full 298K only for spatial density
- Compute `violation_severity_score` per record:
  - DOUBLE PARKING = 4
  - PARKING ON FOOTPATH = 3
  - PARKING IN A MAIN ROAD = 3
  - WRONG PARKING = 2
  - NO PARKING = 2
  - Others = 1
  - Sum scores for multi-violation records
- Derive: `hour`, `month`, `day_of_week` from `created_datetime`
- Flag `is_junction_violation` where `junction_name != 'No Junction'`
- Aggregate and save three CSVs:

`junction_summary.csv`:
junction_name, total_violations, approved_violations, dominant_vehicle, dominant_violation, mean_severity, peak_hour, police_station, lat_centroid, lon_centroid

`police_station_summary.csv`:
station, total_violations, approved_violations, top_junction, dominant_vehicle, mean_severity, peak_hour, monthly_trend (JSON dict Nov→Apr)

`hotspot_input.csv`:
lat, lon, severity_score — approved violations only, for DBSCAN

---

**COMPONENT 2: Hotspot Detection (`src/hotspot.py`)**

- Run DBSCAN on (latitude, longitude) from `hotspot_input.csv`
- Parameters: `eps=0.003, min_samples=15` — tight clusters justified by 115K point density
- For each cluster compute:
  - centroid_lat, centroid_lon
  - total_violations, mean_severity
  - dominant_violation_type, dominant_vehicle_type
  - top_police_station
  - `congestion_impact_score = total_violations × mean_severity × (1.5 if is_junction_cluster else 1.0)`
  - is_junction_cluster = True if any record in cluster has `junction_name != 'No Junction'`
- Call Mappls Reverse Geocoding API on each cluster centroid → save `locality_name` to cluster record
- Assign risk tiers:
  - Critical — top 10 by congestion_impact_score
  - High — rank 11–30
  - Moderate — rest
- Save: `hotspot_clusters.csv`

**Self-defined performance metric to report in slides:**
*Enforcement Coverage* = % of total approved violations captured within Critical + High clusters. Target: >65%. Report this number — it's your proof the system works.

---

**COMPONENT 3: Streamlit App (`app.py`) — 3 Tabs**

**Tab 1 — Hotspot Intelligence Map (Mappls)**

Render via `st.components.v1.html()` with this structure:
```html
<!-- Mappls JS SDK map replacing Folium entirely -->
<script src="https://apis.mappls.com/advancedmaps/v1/{key}/map_load?v=1.5"></script>
<div id="map" style="height:600px"></div>
<script>
  var map = new mappls.Map('map', { center: [12.9716, 77.5946], zoom: 12 });
  // Heatmap layer — pass violation lat/lon/weight from Python as JSON
  // Cluster markers — Critical=red, High=orange, Moderate=yellow
  // Popup on click: junction name, violation count, dominant type, congestion score, locality from Mappls reverse geocode
</script>
```

Pass data from Python to HTML via `json.dumps()` injected into the HTML string.

Sidebar filters:
- Police station multiselect
- Vehicle type multiselect  
- Violation type multiselect
- Month slider (1–6)
- Hour range slider (0–23)

Below map — two Plotly tables:
- Top 15 Junctions ranked by congestion_impact_score
- Top 10 Police Stations ranked by total approved violations

**Tab 2 — Temporal & Vehicle Analytics**

All charts use Plotly, filtered by sidebar selections:
- Hourly violation bar chart (approved only) — annotate peak windows automatically
- Monthly trend line per violation type (Nov 2023 – Apr 2024)
- Vehicle type donut chart
- Heatmap grid: hour × day_of_week × violation count (this is visually striking and unique)
- Auto-generated callout box: "Peak enforcement window for {selected station}: {top 3 hours}"

**Tab 3 — AI Enforcement Briefing Agent**

Vector store construction (`src/agent.py`):
- Embed `junction_summary.csv` — one document per junction, formatted as:
  `"Junction: {name} | Station: {police_station} | Total: {n} | Approved: {n} | Vehicle: {dominant_vehicle} | Violation: {dominant_violation} | Peak Hour: {h} | Severity: {s} | Location: {mappls_locality_name}"`
- Embed `police_station_summary.csv` — one document per station
- Embeddings: `all-MiniLM-L6-v2` (local, free, no external data)
- Vector store: ChromaDB, persisted to `./chroma_db/`
- LLM: Groq API, `llama-3.1-8b-instant` (free tier)

System prompt:
*"You are a senior traffic enforcement intelligence officer for Bengaluru Traffic Police with access to a database of 298,450 parking violations from Nov 2023 to Apr 2024, recorded across Bengaluru junctions and police station jurisdictions. When queried about any junction, area, or police station, retrieve the relevant data and respond with a structured enforcement briefing using exactly these five sections: (1) RISK ASSESSMENT — risk tier (Critical/High/Moderate) and congestion impact score, (2) VIOLATION PROFILE — top violation types with counts, dominant vehicle type, multi-violation rate, (3) PEAK ENFORCEMENT WINDOWS — specific hours with highest activity, best days to deploy, (4) RESOURCE RECOMMENDATION — patrol unit type suited to dominant vehicle (e.g. two-wheeler unit for scooter-heavy zones), suggested deployment strength relative to violation density, (5) PRIORITY JUNCTIONS — top 3 specific junctions to target first with violation counts. Always cite real junction names, real counts, and real hours from the data. Never generalize vaguely."*

Example queries the agent must handle well:
- "Give me an enforcement brief for Upparpet"
- "Which junctions near Shivajinagar need immediate action?"
- "Compare enforcement priority between Malleshwaram and Rajajinagar"
- "What vehicle type should we focus on at Safina Plaza junction?"
- "When is the best time to deploy patrols on Magadi Road?"

---

**REPO STRUCTURE:**
```
parksense/
├── data/
│   └── jan_to_may_police_violation_anonymized791b166.csv
├── src/
│   ├── pipeline.py       # cleaning, scoring, aggregation → 3 CSVs
│   ├── hotspot.py        # DBSCAN + Mappls reverse geocode → hotspot_clusters.csv
│   └── agent.py          # ChromaDB setup + LangChain RAG chain
├── outputs/
│   ├── junction_summary.csv
│   ├── police_station_summary.csv
│   ├── hotspot_input.csv
│   └── hotspot_clusters.csv
├── chroma_db/            # persisted vector store
├── app.py                # Streamlit 3-tab app
├── requirements.txt
├── .env.example          # GROQ_API_KEY, MAPPLS_API_KEY
└── README.md
```

**requirements.txt:**
```
pandas
scikit-learn
streamlit
langchain
langchain-community
langchain-groq
chromadb
sentence-transformers
python-dotenv
plotly
requests
ast
```

---

**BUILD ORDER:**
1. `src/pipeline.py` — verify junction_summary.csv looks right, check Safina Plaza row
2. `src/hotspot.py` — run DBSCAN, verify Critical clusters align with known high-violation junctions, call Mappls reverse geocode on centroids
3. `app.py` Tab 1 — get Mappls map rendering with heatmap layer and cluster markers
4. `app.py` Tab 2 — Plotly temporal charts, hour×day heatmap grid
5. `src/agent.py` — embed summaries, test 5 queries, tune system prompt until responses are sharp and specific
6. `app.py` Tab 3 — wire agent into chat interface
7. Deploy to Streamlit Community Cloud, put MAPPLS_API_KEY and GROQ_API_KEY in Streamlit secrets
8. Record video, build slides last

---

**PRESENTATION SLIDES (10 slides):**
1. Problem — reactive enforcement, no hotspot intelligence
2. Dataset — 298,450 violations, 5 months, Bengaluru-wide
3. System Architecture — pipeline → DBSCAN → Mappls map → RAG agent
4. Risk Scoring Methodology — severity formula, congestion impact score definition
5. Hotspot Map — screenshot of Mappls map with Critical clusters highlighted
6. Temporal Intelligence — hour×day heatmap, peak window callouts
7. AI Agent Demo — 2 example query-response pairs, annotated
8. Key Findings — top 5 Critical zones with stats, enforcement coverage metric
9. MapMyIndia Integration — specifically call out how Mappls reverse geocoding enriches cluster labels and how their map tiles provide ground-truth junction matching
10. Future Work — real-time CCTV feed integration, predictive violation forecasting

---

**WHY THIS IS TOP 10:**
- Only team using Mappls APIs — direct alignment with co-organizer
- Congestion impact is a number, not just a heatmap
- Three aggregation layers — violation → junction → police station
- Vehicle-specific patrol recommendations (scooter zones ≠ car zones)
- Hour×day heatmap is visually unique and operationally useful
- Agent handles comparison queries no dashboard can answer
- Enforcement Coverage metric is self-validating and reportable
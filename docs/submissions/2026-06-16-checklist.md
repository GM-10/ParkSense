# ParkSense Submission Checklist

## Prototype Readiness
- [ ] **Data Pipeline:** `src/pipeline.py` run and confirmed (`junction_summary.csv`, `police_station_summary.csv`, `location_cluster_input.csv` exist).
- [ ] **Hotspot Detection:** `src/hotspot.py` run and confirmed (`hotspot_clusters.csv` exists).
- [ ] **Dashboard UI:** `streamlit run app.py` launches, map renders, temporal charts render.
- [ ] **MapMyIndia Integration:** Map loads via Mappls SDK, locality names are populated in hotspot popups.
- [ ] **AI Enforcement Agent:** ChromaDB is built, Groq API key is configured, queries generate bilingual, structured briefings.
- [ ] **Officer Feedback:** Feedback mechanism captures validations and logs them to `data/feedback_log.csv`.
- [ ] **Cost Constraint:** All API calls use free-tier (Groq) or are local (embeddings). No paid OpenAI/OpenRouter dependencies remain.

## Submission Materials
- [ ] **Video (3 min):** Shows map loading → hotspot selection → AI query → Agent response.
- [ ] **Slides (10 slides):** Covers Problem, Data, Architecture, Risk Scoring, Mappls, Temporal Patterns, Agent Demo, Findings, Impact, Future Work.
- [ ] **Deployment:** Streamlit Community Cloud (Secrets populated).

## Final Polish
- [ ] README.md updated.
- [ ] All code committed.
- [ ] Unnecessary files cleaned.

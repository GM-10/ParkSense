# ParkSense: AI-Driven Parking Intelligence & Enforcement Briefing System

ParkSense is a tactical-grade traffic intelligence system designed to detect illegal parking hotspots, quantify their congestion impact, and provide actionable enforcement briefings to the Bengaluru Traffic Police.

## 🛠️ Tech Stack
- **AI/ML Engine**: DBSCAN (Spatial Clustering), Haversine (Geospatial)
- **RAG Architecture**: LangChain, ChromaDB, Llama 3.1 (via Groq API)
- **Visualization**: Mappls JS SDK (Mappls API), Plotly (Temporal Analytics)
- **Framework**: Streamlit (Command Center UI)
- **Economic Model**: Custom Bengaluru-specific productivity loss algorithm

## 🚀 Key Differentiators
1.  **Quantified Congestion Impact:** Not just a heatmap, but a `congestion_impact_score` = `violation_count` × `mean_severity` × `junction_density_flag`.
2.  **Mappls Integration:** Strategic alignment with MapMyIndia/Mappls for accurate Bengaluru-specific junction visualization and locality enrichment.
3.  **Prescriptive Enforcement:** The "Intervention Simulator" allows officers to model the impact of patrol units *before* deployment.
4.  **Actionable Intelligence Agent:** Bilingual (EN/KN) RAG agent provides structured briefings, patrol windows, and resource allocation recommendations.
5.  **Tactical UI:** High-contrast, dark-themed command center interface for rapid situational awareness.

## ⚙️ Setup & Execution

### Prerequisites
1. Get a **Groq API Key** (for LLM).
2. Get a **Mappls API Key** (for Map visualization).
3. Populate `.env`:
   ```env
   GROQ_API_KEY=your_groq_key
   MAPPLS_API_KEY=your_mappls_key
   ```

### Execution
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run Pipeline (Processes 298K records):**
   ```bash
   python src/pipeline.py
   ```
3. **Generate Hotspots:**
   ```bash
   python src/hotspot.py
   ```
4. **Launch Command Center:**
   ```bash
   streamlit run app.py
   ```

---
*Developed for Flipkart Grid 2.0 Round 2.*

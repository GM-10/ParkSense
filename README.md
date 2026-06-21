# 🚦 ParkSense: Urban Mobility & Traffic Intelligence Platform

> **ParkSense** is a state-of-the-art, government-grade urban traffic intelligence platform designed for municipal command centers. It transforms raw incident feeds and congestion telemetry into actionable field dispatch instructions, utilizing advanced spatial clustering, economic impact quantification, and resource-constrained optimization.

---

## 🚀 Key Competition & Architecture Highlights

*   **Geospatial Clustering (HDBSCAN)**: Uses density-based clustering with noise-filtering to locate hotspots without assuming spherical distribution, outperforming traditional DBSCAN on variable-density traffic flows.
*   **Haversine Distance Metric**: Used globally across map components, routing logic, and ETA engines for precise curvature-aware distance calculation.
*   **Economic Impact Assessment**: Quantifies congestion delays in terms of economic loss (INR/USD lost per minute of blockage) to help controllers prioritize issues based on financial productivity impact.
*   **Resource-Constrained Optimization**: Assigns and routes a limited fleet of traffic officers and vehicles (tow trucks, interceptors) to high-priority hotspots using distance, availability, and incident severity.
*   **Digital Twin Simulation**: Enables operators to simulate the traffic clearing impact of an intervention (e.g., lane closures, signal timing adjustments, officer dispatch) before sending units to the field.
*   **Bilingual Alerts (English + Kannada)**: Ready-to-send WhatsApp/SMS/Telegram dispatcher payloads generated automatically in both English and Kannada to suit local Karnataka municipal authorities.
*   **Officer-in-the-Loop Validation**: Dispatchers and field officers can confirm, update, or dismiss AI-generated findings, refining the model dynamically.
*   **Tactical "War Room" UI**: A premium, high-contrast dashboard with instant dark/light mode toggle designed for 24/7 command center operations.

---

## 🛠 Tech Stack

*   **Frontend**: React (TypeScript), Vite, Tailwind CSS, Leaflet Maps.
*   **Backend**: Python, FastAPI, Uvicorn, SQLite.
*   **Data Science**: Pandas, NumPy, Scikit-Learn (DBSCAN/HDBSCAN), Haversine.

---

## 📂 Project Structure

```text
├── src/                      # Python backend API & analytics pipeline
│   ├── api.py                # FastAPI endpoints & session auth
│   ├── analytics.py          # Hotspot clustering, stats, & impact scoring
│   ├── forecasting.py        # Trend analysis & predictive models
│   ├── persistence.py        # Database operations & data ingestion
│   └── copilot.py            # AI Query answering & RAG engine
├── frontend/                 # React frontend application
│   ├── src/
│   │   ├── views/            # CommandCenter, DispatchCenter, Reports, AI views
│   │   ├── components/       # UI Shell, header, loaders
│   │   └── api/              # Axios client and endpoints definition
├── db/                       # Local SQLite instances
└── run_pipeline.py           # Database migration & background pipeline ingestion
```

---

## 🏁 Quick Start & Local Run

### 1. Prerequisites
Ensure you have Python 3.10+ and Node.js 18+ installed on your machine.

### 2. Backend Setup
1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/GM-10/ParkSense.git
   cd ParkSense
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Initialize the database and run the data pipeline:
   ```bash
   python run_pipeline.py
   ```
4. Start the FastAPI backend server:
   ```bash
   uvicorn src.api:app --reload --reload-dir src --port 8000
   ```
   The backend will be running at `http://127.0.0.1:8000`.

### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the development web server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser to view the tactical command dashboard.

---

## 🛡 License
This project is proprietary and built for hackathon evaluation. All rights reserved.

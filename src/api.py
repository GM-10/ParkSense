import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Import existing ParkGuard logic
from src.agent import initialize_rag, ask_agent
from src.pipeline import load_data, process_data, aggregate_data
from src.hotspot import detect_hotspots

load_dotenv()

app = FastAPI(
    title="ParkGuard Tactical API",
    description="Enterprise-grade API for Bengaluru Traffic Police Parking Intelligence",
    version="1.0.0"
)

# --- GLOBAL STATE ---
# Initialize RAG on startup
initialize_rag()

# --- MODELS ---
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    confidence: str
    sources: List[str]

# --- ENDPOINTS ---

@app.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "operational",
        "components": {
            "rag_engine": "initialized",
            "data_pipeline": "available",
            "llm": "groq-llama-3.1-8b"
        }
    }

@app.get("/data/hotspots")
async def get_hotspots(risk_tier: Optional[str] = None):
    """Returns hotspot cluster data with optional risk tier filtering."""
    try:
        df = pd.read_csv("data/hotspot_clusters.csv")
        if risk_tier:
            df = df[df['risk_tier'] == risk_tier]
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data Error: {str(e)}")

@app.get("/data/junctions")
async def get_junctions():
    """Returns summary of all traffic junctions."""
    try:
        df = pd.read_csv("data/junction_summary.csv")
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data Error: {str(e)}")

@app.get("/data/stations")
async def get_stations():
    """Returns summary of all police stations."""
    try:
        df = pd.read_csv("data/police_station_summary.csv")
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data Error: {str(e)}")

@app.post("/agent/query")
async def query_agent(request: QueryRequest):
    """Tactical RAG interface for police briefings."""
    result = ask_agent(request.question)
    if "Error" in result["answer"]:
        raise HTTPException(status_code=500, detail=result["answer"])
    return result

@app.post("/pipeline/refresh")
async def refresh_data():
    """Triggers the full data pipeline and hotspot detection."""
    try:
        # 1. Run ETL Pipeline
        df_raw = load_data('jan to may police violation_anonymized791b166.csv')
        df_processed = process_data(df_raw)
        aggregate_data(df_processed)

        # 2. Run Hotspot Detection
        detect_hotspots()

        return {"status": "success", "message": "All datasets refreshed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

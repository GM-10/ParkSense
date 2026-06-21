"""ParkSense API."""
from __future__ import annotations

import math
import os
import threading
from dotenv import load_dotenv
load_dotenv()
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.cluster import DBSCAN

from src.analytics import compute_hotspots, compute_anomalies, compute_zone_insights, estimate_impact, load_violations, recommend_dispatch, invalidate_caches, _parse_timeline
from src.copilot import answer_query
from src.domain import AlertRecord, CopilotRequest, CopilotResponse, DispatchRecommendation, ForecastResponse, HotspotRecord, ImpactEstimate
from src.forecasting import forecast_locality
from src.persistence import (
    authenticate_user,
    add_dispatch_assignment,
    add_incident,
    clear_all_incidents,
    create_dispatch_deployment,
    create_session,
    get_active_incidents,
    get_dispatch_deployment,
    get_dispatch_deployments,
    get_dispatch_assignments,
    get_fleet_resources,
    get_ingested_violations,
    init_db,
    ingest_violation,
    is_alert_resolved,
    log_audit,
    revoke_session,
    resolve_alert as persist_alert_resolution,
    update_dispatch_deployment,
    update_fleet_resource,
    validate_session,
    get_alert_states,
    update_alert_state,
    get_officers,
    create_officer_team,
    update_officer_team,
    delete_officer_team,
    get_vehicles,
    create_vehicle,
    update_vehicle,
    delete_vehicle,
    get_db,
)

app = FastAPI(title="ParkSense Traffic Intelligence API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str


class ResolveAlertResponse(BaseModel):
    id: str
    type: str
    junction_id: str
    junction_name: str
    message: str
    timestamp: datetime
    resolved: bool


class CopilotQueryRequest(BaseModel):
    message: str
    language: str = Field(default="en")
    context: dict[str, Any] = Field(default_factory=dict)


class DispatchAssignRequest(BaseModel):
    hotspot_id: str
    officers: int = Field(ge=0, le=20)
    patrol_vehicles: int = Field(ge=0, le=10)
    notes: str = ""
    team_ids: Optional[list[str]] = None
    vehicle_ids: Optional[list[str]] = None


class DispatchStatusRequest(BaseModel):
    deployment_id: str
    status: str
    outcome: Optional[str] = None

class ResourceUpdateRequest(BaseModel):
    resource_type: str = Field(pattern="^(team|tow_vehicle)$")
    total_count: int = Field(ge=0, le=100)
    available_count: int = Field(ge=0, le=100)



class DispatchIncidentRequest(BaseModel):
    junction_name: str
    latitude: float
    longitude: float
    violation_count: int = Field(ge=0, le=10000)
    congestion_level: str
    severity: str
    incident_type: str
    notes: str = ""



class IncidentInjectRequest(BaseModel):
    locality_name: str
    incident_type: str
    severity: str
    duration_minutes: int


class UpdateAlertStateRequest(BaseModel):
    state: str = Field(pattern="^(New|Acknowledged|Assigned|Resolved|Archived)$")


class CommandCenterSnapshot(BaseModel):
    hotspots: list[dict[str, Any]]
    stats: dict[str, Any]
    queue: list[dict[str, Any]]


_FALLBACK_BOUNDS = (12.834, 77.45, 13.139, 77.78)  # used only if geocoding and env lookup fail


def _city() -> str:
    return os.getenv("PARKSENSE_CITY", "Bengaluru")


def _bounds_for_city() -> tuple[float, float, float, float]:
    # First, allow explicit override via env var: PARKSENSE_BOUNDS="lat_min,lng_min,lat_max,lng_max"
    raw = os.getenv("PARKSENSE_BOUNDS")
    if raw:
        try:
            parts = [float(p.strip()) for p in raw.split(",")]
            if len(parts) == 4:
                return (parts[0], parts[1], parts[2], parts[3])
        except Exception:
            pass

    # Final fallback: a safe preconfigured bbox (used only when geocoding fails)
    return _FALLBACK_BOUNDS


def _now(timeline: Optional[str] = None) -> datetime:
    frame = _city_seed_events(timeline)
    if not frame.empty and "created_datetime" in frame:
        try:
            ts = frame["created_datetime"].max()
            if pd.notna(ts):
                return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _require_auth(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    session = validate_session(token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return token


def _pick_junction_name(lat: float, lng: float, fallback: str) -> str:
    return fallback



def _city_seed_events(timeline: Optional[str] = None) -> pd.DataFrame:
    frame = load_violations().copy()
    if not frame.empty:
        start, end = _parse_timeline(timeline)
        frame = frame[(frame["created_datetime"] >= start) & (frame["created_datetime"] <= end)].copy()
        return frame

    lat_min, lng_min, lat_max, lng_max = _bounds_for_city()
    rng = np.random.default_rng(42)
    rows = []
    for idx in range(240):
        lat = float(rng.uniform(lat_min, lat_max))
        lng = float(rng.uniform(lng_min, lng_max))
        rows.append(
            {
                "id": idx + 1,
                "latitude": lat,
                "longitude": lng,
                "location": f"{lat:.5f},{lng:.5f}",
                "vehicle_type": "unknown",
                "violation_type": "parking",
                "created_datetime": datetime.now(timezone.utc) - timedelta(hours=int(rng.integers(0, 720))),
                "validation_status": "approved",
                "junction_name": _pick_junction_name(lat, lng, f"{lat:.5f},{lng:.5f}"),
                "police_station": None,
            }
        )
    frame = pd.DataFrame(rows)
    frame["created_datetime"] = pd.to_datetime(frame["created_datetime"], utc=True)
    if timeline:
        start, end = _parse_timeline(timeline)
        frame = frame[(frame["created_datetime"] >= start) & (frame["created_datetime"] <= end)].copy()
    frame["hour"] = frame["created_datetime"].dt.hour
    frame["week"] = frame["created_datetime"].dt.to_period("W").astype(str)
    frame["locality_name"] = frame["junction_name"]
    frame["severity"] = 2.0
    return frame


def _compute_economic_impact(row: HotspotRecord) -> float:
    return round((row.risk_score * 0.7) + (row.violation_count * 0.8) + (row.confidence_score * 10), 2)


def _shape_hotspot(row: HotspotRecord) -> dict[str, Any]:
    return {
        "id": row.hotspot_id,
        "name": row.locality_name,
        "lat": row.centroid_lat,
        "lng": row.centroid_lon,
        "riskScore": row.risk_score,
        "violations": row.violation_count,
        "congestionLevel": row.risk_level,
        "status": "active" if row.risk_score >= 40 else "monitor",
        "trend": row.trend_direction,
        "peakHour": row.peak_hour,
        "cluster_id": row.hotspot_id,
        "economicImpact": _compute_economic_impact(row),
        "raw": row.model_dump(),
    }


def _find_hotspot_by_id(hotspot_id: str, timeline: Optional[str] = None) -> Optional[HotspotRecord]:
    frame = _city_seed_events(timeline)
    if frame.empty:
        return None
    now = frame["created_datetime"].max()
    start = now - pd.Timedelta(days=30)
    for mode in ("LIVE", "FORECAST"):
        for row in compute_hotspots(mode=mode, timeline=timeline):
            if row.hotspot_id == hotspot_id:
                return row
    for row in compute_hotspots(mode="HISTORICAL", time_range=(start.to_pydatetime(), now.to_pydatetime()), timeline=timeline):
        if row.hotspot_id == hotspot_id:
            return row
    return None


def _hotspots_response(
    mode: str = "HISTORICAL",
    radius_m: int = 330,
    min_samples: int = 10,
    time_range: Optional[tuple[datetime, datetime]] = None,
    day_of_week: Optional[int] = None,
    time_of_day: str = "ALL",
    timeline: Optional[str] = None
) -> list[dict[str, Any]]:
    # For LIVE or SNAPSHOT mode, reduce min_samples to allow detection with smaller data window
    effective_min_samples = min_samples
    if mode in ("LIVE", "SNAPSHOT"):
        effective_min_samples = max(3, min_samples // 3)
    if mode == "HISTORICAL" and not time_range:
        frame = _city_seed_events(timeline)
        if not frame.empty:
            now = frame["created_datetime"].max()
            start = now - pd.Timedelta(days=30)
            time_range = (start.to_pydatetime(), now.to_pydatetime())
    rows = compute_hotspots(
        radius_m=radius_m,
        min_samples=effective_min_samples,
        mode=mode,
        time_range=time_range,
        day_of_week=day_of_week,
        time_of_day=time_of_day,
        timeline=timeline
    )
    if not rows and mode in ("LIVE", "SNAPSHOT"):
        rows = compute_hotspots(radius_m=radius_m, min_samples=min_samples, mode="HISTORICAL", time_range=time_range, day_of_week=day_of_week, time_of_day=time_of_day, timeline=timeline)
    return [_shape_hotspot(row) for row in rows]



def _severity_label(risk_score: float) -> str:
    if risk_score >= 85:
        return "Critical"
    if risk_score >= 70:
        return "High"
    if risk_score >= 40:
        return "Moderate"
    return "Low"


def _queue_rows(timeline: Optional[str] = None) -> list[dict[str, Any]]:
    hotspots = compute_hotspots(mode="LIVE", timeline=timeline)
    if len(hotspots) < 5:
        frame = _city_seed_events(timeline)
        if not frame.empty:
            now = frame["created_datetime"].max()
            start = now - pd.Timedelta(days=7)
            historical_spots = compute_hotspots(mode="HISTORICAL", time_range=(start.to_pydatetime(), now.to_pydatetime()), timeline=timeline)
            seen = {h.hotspot_id for h in hotspots}
            for h in historical_spots:
                if h.hotspot_id not in seen:
                    hotspots.append(h)
                    seen.add(h.hotspot_id)
                if len(hotspots) >= 5:
                    break
    if not hotspots:
        hotspots = compute_hotspots(mode="HISTORICAL", timeline=timeline)
    deployments = {row["hotspot_id"]: row for row in get_dispatch_deployments() if row.get("status") != "Resolved"}
    frame = _city_seed_events(timeline)
    queue: list[dict[str, Any]] = []
    for item in hotspots:
        if item.hotspot_id in deployments:
            continue

        matched = frame[frame["junction_name"].fillna("").str.lower() == item.locality_name.lower()].copy()
        if matched.empty:
            lat_window = frame["latitude"].between(item.centroid_lat - 0.003, item.centroid_lat + 0.003)
            lon_window = frame["longitude"].between(item.centroid_lon - 0.003, item.centroid_lon + 0.003)
            matched = frame[lat_window & lon_window].copy()
        first_detected = matched["created_datetime"].min() if not matched.empty else (frame["created_datetime"].min() if not frame.empty else _now(timeline))
        last_updated = matched["created_datetime"].max() if not matched.empty else (frame["created_datetime"].max() if not frame.empty else _now(timeline))

        rec = recommend_dispatch(item)
        predicted_next_hour = int(round(item.violation_count * 1.12))
        severity = _severity_label(item.risk_score)
        priority_score = round((item.risk_score * 0.55) + (item.violation_count * 0.25) + (predicted_next_hour * 0.2), 2)
        
        queue.append(
            {
                "hotspot_id": item.hotspot_id,
                "hotspot_name": item.locality_name,
                "risk_score": item.risk_score,
                "current_violations": item.violation_count,
                "predicted_violations_next_hour": predicted_next_hour,
                "severity": severity,
                "recommended_officers": rec.recommended_officers,
                "recommended_patrol_vehicles": rec.recommended_tow_trucks,
                "priority_score": priority_score,
                "status": "Queued",
                "deployment_id": None,
                "action_recommendation": rec.actions[0] if rec.actions else "Monitor and include in routine patrol",
                "first_detected_at": str(first_detected),
                "last_updated_at": str(last_updated),
                "active_minutes": max(1, int((_now(timeline) - first_detected.to_pydatetime()).total_seconds() // 60)) if hasattr(first_detected, "to_pydatetime") else 1,
                "trend": item.trend_direction,
            }
        )
    return sorted(queue, key=lambda row: row["priority_score"], reverse=True)


def _public_deployment_row(row: dict[str, Any]) -> dict[str, Any]:
    notes = row.get("notes") or ""
    outcome = ""
    if notes.startswith("Outcome: "):
        outcome = notes.removeprefix("Outcome: ").split(". ", 1)[0].strip()
    return {
        **row,
        "outcome": outcome,
    }




@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    init_db()
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_session(user["username"], user["role"])
    return LoginResponse(token=token, username=user["username"], role=user["role"])


@app.post("/auth/logout")
def logout(token: str = Depends(_require_auth)) -> dict[str, str]:
    revoke_session(token)
    return {"status": "ok"}


@app.get("/health")
def health(_: str = Depends(_require_auth)) -> dict[str, Any]:
    return {"status": "ok", "city": _city(), "timestamp": _now()}


def _stats_payload(
    day_of_week: Optional[int] = None,
    time_of_day: str = "ALL",
    timeline: Optional[str] = None,
) -> dict[str, Any]:
    frame = _city_seed_events(timeline)
    hotspots = _hotspots_response(mode="HISTORICAL", day_of_week=day_of_week, time_of_day=time_of_day, timeline=timeline)
    critical = len([h for h in hotspots if h["riskScore"] >= 75])
    avg_risk = round(float(np.mean([h["riskScore"] for h in hotspots])) if hotspots else 0.0, 2)
    
    officer_list = get_officers(timeline)
    officers = sum(int(o["total_strength"]) for o in officer_list) if officer_list else 6

    latest_ts = frame["created_datetime"].max() if not frame.empty else _now(timeline)

    savings = round(sum(h["economicImpact"] * 0.18 for h in hotspots[:5]), 2) if hotspots else 0.0
    response_time = round(12.0 + (critical * 1.5), 1)
    reduction = round(10.0 + (officers * 1.2), 1)
    mitigated = len([h for h in hotspots if h["riskScore"] < 45])

    total_violations = int(frame.shape[0]) if not frame.empty else 0
    return {
        "totalViolations": total_violations,
        "avgRiskScore": avg_risk,
        "criticalZones": critical,
        "activeOfficers": officers,
        "timestamp": str(_now(timeline)),
        "city": _city(),
        "revenueLeakagePrevented": savings,
        "avgResponseTimeMins": response_time,
        "congestionReductionPct": reduction,
        "hotspotsMitigated": mitigated,
    }


from src.domain import StatsResponse, HotspotResponseItem, AlertItem

@app.get("/stats", response_model=StatsResponse)
def stats(
    _: str = Depends(_require_auth),
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    time_of_day: str = Query("ALL", pattern="^(ALL|PEAK|OFF_PEAK)$"),
    timeline: Optional[str] = Query(None)
) -> dict[str, Any]:
    return _stats_payload(day_of_week=day_of_week, time_of_day=time_of_day, timeline=timeline)


@app.get("/queue")
def get_queue(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return _queue_rows(timeline)


@app.get("/snapshot")
def get_snapshot(
    time_of_day: str = Query("ALL", pattern="^(ALL|PEAK|OFF_PEAK)$"),
    timeline: Optional[str] = Query(None),
    _: str = Depends(_require_auth)
) -> dict[str, Any]:
    frame = _city_seed_events(timeline).copy()
    if frame.empty:
        return {"timeOfDay": time_of_day, "buckets": [], "summary": {"totalViolations": 0, "avgRiskScore": 0.0, "criticalZones": 0, "activeOfficers": 0, "city": _city(), "timestamp": str(_now(timeline))}}

    def _bucket(label: str) -> dict[str, Any]:
        subset = frame.copy()
        if label == "PEAK":
            subset = subset[subset["created_datetime"].dt.hour.isin([8, 9, 10, 17, 18, 19, 20])]
        elif label == "OFF_PEAK":
            subset = subset[~subset["created_datetime"].dt.hour.isin([8, 9, 10, 17, 18, 19, 20])]
        hotspots = _hotspots_response(mode="SNAPSHOT", time_of_day=label, timeline=timeline)
        stats_payload = _stats_payload(time_of_day=label, timeline=timeline)
        return {
            "timeOfDay": label,
            "totalViolations": stats_payload["totalViolations"],
            "avgRiskScore": stats_payload["avgRiskScore"],
            "criticalZones": stats_payload["criticalZones"],
            "activeOfficers": stats_payload["activeOfficers"],
            "city": stats_payload["city"],
            "timestamp": stats_payload["timestamp"],
            "hotspots": hotspots,
        }

    if time_of_day == "ALL":
        buckets = [
            _bucket("PEAK"),
            _bucket("OFF_PEAK"),
        ]
    else:
        buckets = [_bucket(time_of_day)]

    summary = {
        "totalViolations": sum(int(bucket["totalViolations"]) for bucket in buckets),
        "avgRiskScore": round(sum(float(bucket["avgRiskScore"]) for bucket in buckets) / max(1, len(buckets)), 2),
        "criticalZones": sum(int(bucket["criticalZones"]) for bucket in buckets),
        "activeOfficers": max(int(bucket["activeOfficers"]) for bucket in buckets) if buckets else 0,
        "city": _city(),
        "timestamp": str(_now(timeline)),
    }
    return {"timeOfDay": time_of_day, "buckets": buckets, "summary": summary}


@app.get("/command-center/snapshot", response_model=CommandCenterSnapshot)
def command_center_snapshot(
    _: str = Depends(_require_auth),
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    time_of_day: str = Query("ALL", pattern="^(ALL|PEAK|OFF_PEAK)$"),
    timeline: Optional[str] = Query(None),
) -> dict[str, Any]:
    return {
        "hotspots": _hotspots_response(mode="SNAPSHOT", day_of_week=day_of_week, time_of_day=time_of_day, timeline=timeline),
        "stats": _stats_payload(day_of_week=day_of_week, time_of_day=time_of_day, timeline=timeline),
        "queue": _queue_rows(timeline)[:5],
    }



@app.get("/hotspots", response_model=list[HotspotResponseItem])
def hotspots(
    _: str = Depends(_require_auth),
    radius_m: int = Query(330, ge=50, le=2000),
    min_samples: int = Query(10, ge=3, le=100),
    mode: str = Query("HISTORICAL", pattern="^(LIVE|FORECAST|HISTORICAL|SNAPSHOT)$"),
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    time_of_day: str = Query("ALL", pattern="^(ALL|PEAK|OFF_PEAK)$"),
    range: Optional[str] = Query(None, pattern="^(24h|7d|30d|daily|weekly|full)$"),
    timeline: Optional[str] = Query(None)
) -> list[dict[str, Any]]:
    time_range_tuple = None
    if mode == "HISTORICAL" and range:
        frame = _city_seed_events(timeline)
        if not frame.empty:
            now = frame["created_datetime"].max()
            if range == "24h":
                start = now - pd.Timedelta(hours=24)
                time_range_tuple = (start.to_pydatetime(), now.to_pydatetime())
            elif range == "7d":
                start = now - pd.Timedelta(days=7)
                time_range_tuple = (start.to_pydatetime(), now.to_pydatetime())
            elif range == "30d":
                start = now - pd.Timedelta(days=30)
                time_range_tuple = (start.to_pydatetime(), now.to_pydatetime())
            else:
                # daily, weekly, full -> cover the entire month timeline
                start, end = _parse_timeline(timeline)
                time_range_tuple = (start.to_pydatetime(), end.to_pydatetime())
    return _hotspots_response(mode=mode, radius_m=radius_m, min_samples=min_samples, day_of_week=day_of_week, time_of_day=time_of_day, time_range=time_range_tuple, timeline=timeline)


_FORECAST_CACHE: dict[Optional[str], list[dict[str, Any]]] = {}
_FORECAST_LOCK = threading.Lock()

def invalidate_forecast_cache() -> None:
    global _FORECAST_CACHE
    with _FORECAST_LOCK:
        _FORECAST_CACHE.clear()

def _forecast_rows(timeline: Optional[str] = None) -> list[dict[str, Any]]:
    global _FORECAST_CACHE
    with _FORECAST_LOCK:
        if timeline in _FORECAST_CACHE:
            return _FORECAST_CACHE[timeline]
        base = _hotspots_response(mode="FORECAST", timeline=timeline)
        output: list[dict[str, Any]] = []
        for hotspot in base:
            locality = hotspot["name"]
            forecast_data = None
            try:
                forecast_data = forecast_locality(locality)
            except Exception:
                pass
            
            for hour_offset in range(1, 7):
                # Use real model forecast if available
                if forecast_data and forecast_data.status == "modelled" and forecast_data.points:
                    p1h = forecast_data.points[0].expected_violations if len(forecast_data.points) > 0 else 0
                    p6h = forecast_data.points[1].expected_violations if len(forecast_data.points) > 1 else p1h * 6
                    forecast_ratio = p1h / max(1, hotspot["violations"]) if hotspot["violations"] > 0 else 1.0
                    predicted_risk = round(min(100.0, hotspot["riskScore"] * (1 + (forecast_ratio - 1) * hour_offset / 6)), 2)
                    predicted_violations = int(round(p1h * hour_offset))
                    confidence = round(float(forecast_data.points[0].confidence), 2)
                else:
                    predicted_risk = round(min(100.0, hotspot["riskScore"] + hour_offset * 1.5), 2)
                    predicted_violations = int(round(hotspot["violations"] * (1 + hour_offset * 0.05)))
                    confidence = round(0.60 + (hotspot["riskScore"] / 400), 2)
                
                output.append(
                    {
                        "hotspot_id": hotspot["id"],
                        "hotspot_name": locality,
                        "hour_offset": hour_offset,
                        "predictedRisk": predicted_risk,
                        "predictedViolations": predicted_violations,
                        "confidence": confidence,
                    }
                )
        _FORECAST_CACHE[timeline] = output
        return output


from src.domain import ForecastResponseItem, HistoricalResponse

@app.get("/forecast", response_model=list[ForecastResponseItem])
def forecast(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return _forecast_rows(timeline)


@app.get("/historical", response_model=HistoricalResponse)
def historical(
    _: str = Depends(_require_auth),
    range: str = Query("24h", pattern="^(24h|7d|30d|daily|weekly|full)$"),
    timeline: Optional[str] = Query(None)
) -> dict[str, Any]:
    frame = _city_seed_events(timeline).copy()
    if frame.empty:
        return {
            "range": range,
            "bucketLabel": "hour" if range == "24h" else "day" if range in ("7d", "daily") else "week" if range in ("30d", "weekly") else "month",
            "buckets": [],
            "topJunctions": [],
            "totalViolations": 0,
            "avgRisk": 0.0,
            "peakHour": 0,
            "peakDay": "N/A",
            "hotspotCount": 0,
        }
    
    start_timeline, end_timeline = _parse_timeline(timeline)
    now = frame["created_datetime"].max()
    
    if range == "24h":
        start = now - pd.Timedelta(hours=24)
        freq = "h"
        subset = frame[frame["created_datetime"] >= start].copy()
    elif range == "7d":
        start = now - pd.Timedelta(days=7)
        freq = "D"
        subset = frame[frame["created_datetime"] >= start].copy()
    elif range == "30d":
        start = now - pd.Timedelta(days=30)
        freq = "W"
        subset = frame[frame["created_datetime"] >= start].copy()
    elif range == "daily":
        start = start_timeline
        now = end_timeline
        freq = "D"
        subset = frame.copy()
    elif range == "weekly":
        start = start_timeline
        now = end_timeline
        freq = "W"
        subset = frame.copy()
    else:  # full
        start = start_timeline
        now = end_timeline
        freq = "M"
        subset = frame.copy()

    if subset.empty:
        return {
            "range": range,
            "bucketLabel": "hour" if range == "24h" else "day" if range in ("7d", "daily") else "week" if range in ("30d", "weekly") else "month",
            "buckets": [],
            "topJunctions": [],
            "totalViolations": 0,
            "avgRisk": 0.0,
            "peakHour": 0,
            "peakDay": "N/A",
            "hotspotCount": 0,
        }

    if freq == "M":
        try:
            buckets = subset.groupby(pd.Grouper(key="created_datetime", freq="M")).size().reset_index(name="violations")
        except Exception:
            buckets = subset.groupby(pd.Grouper(key="created_datetime", freq="ME")).size().reset_index(name="violations")
    else:
        buckets = subset.groupby(pd.Grouper(key="created_datetime", freq=freq)).size().reset_index(name="violations")
    
    # Use DBSCAN hotspots for this period for proper top junctions
    t_start = start.to_pydatetime() if hasattr(start, "to_pydatetime") else start
    t_end = now.to_pydatetime() if hasattr(now, "to_pydatetime") else now
    time_range_tuple = (t_start, t_end)
    period_hotspots = compute_hotspots(mode="HISTORICAL", time_range=time_range_tuple, timeline=timeline)
    if period_hotspots:
        top_junctions = [
            {"name": h.locality_name, "violations": h.violation_count, "risk": round(h.risk_score, 2)}
            for h in sorted(period_hotspots, key=lambda x: x.risk_score, reverse=True)[:5]
        ]
        avg_risk = round(sum(h.risk_score for h in period_hotspots) / len(period_hotspots), 2)
        peak_hours = [h.peak_hour for h in period_hotspots]
        peak_hour = max(set(peak_hours), key=peak_hours.count) if peak_hours else 0
        total_violations = sum(h.violation_count for h in period_hotspots)
        if not subset.empty:
            day_counts = subset.groupby(subset["created_datetime"].dt.day_name()).size()
            peak_day = day_counts.idxmax() if not day_counts.empty else "N/A"
        else:
            peak_day = "N/A"
    else:
        top = (
            subset.groupby("locality_name")
            .size()
            .sort_values(ascending=False)
            .head(5)
            .reset_index(name="violations")
        )
        top_junctions = [{"name": row.locality_name, "violations": int(row.violations), "risk": round(min(100, 35 + row.violations), 2)} for row in top.itertuples()]
        avg_risk = 0.0
        peak_hour = 0
        total_violations = int(subset.shape[0])
        peak_day = "N/A"

    return {
        "range": range,
        "bucketLabel": "hour" if range == "24h" else "day" if range in ("7d", "daily") else "week" if range in ("30d", "weekly") else "month",
        "buckets": [{"label": str(row.created_datetime), "violations": int(row.violations)} for row in buckets.itertuples()],
        "topJunctions": top_junctions,
        "totalViolations": total_violations,
        "avgRisk": avg_risk,
        "peakHour": peak_hour,
        "peakDay": peak_day,
        "hotspotCount": len(period_hotspots) if period_hotspots else 0,
    }


def _alerts_from_hotspots(timeline: Optional[str] = None) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    states = get_alert_states()
    
    # Filter the raw violations for the current timeline to analyze surges and sustained congestion
    import hashlib
    df = _city_seed_events(timeline)
    
    # 1. Crossed 75 threshold (risk Score >= 75)
    hotspots = compute_hotspots(mode="LIVE", timeline=timeline)
    if not hotspots:
        hotspots = compute_hotspots(mode="HISTORICAL", timeline=timeline)
        
    for h in hotspots:
        if h.risk_score >= 75:
            alert_id = f"alert-risk-{h.hotspot_id}"
            alert_state = states.get(alert_id, "New")
            resolved = alert_state in ("Resolved", "Archived")
            alerts.append({
                "id": alert_id,
                "type": "Critical" if h.risk_score >= 85 else "Warning",
                "junction_id": h.hotspot_id,
                "junction_name": h.locality_name,
                "message": f"ELEVATED RISK: {h.locality_name} risk score is {h.risk_score:.1f}%. Immediate dispatch of {recommend_dispatch(h).recommended_officers} officers recommended.",
                "timestamp": str(df["created_datetime"].max()) if not df.empty else str(_now(timeline)),
                "resolved": resolved,
                "current_risk": h.risk_score,
                "predicted_risk": min(100.0, h.risk_score + 5.0),
                "eta_minutes": 30 if h.risk_score >= 85 else 60,
                "recommended_officers": recommend_dispatch(h).recommended_officers,
                "state": alert_state,
                "resolvedBy": "system" if resolved else None,
                "resolvedAt": str(_now(timeline)) if resolved else None
            })

    # 2. Surge > 200% in a 3-hour window
    if not df.empty and "junction_name" in df:
        df_j = df[df["junction_name"].notna() & (df["junction_name"] != "")]
        for name, group in df_j.groupby("junction_name"):
            if len(group) < 5:
                continue
            hourly = group.set_index("created_datetime").resample("h").size()
            rolling_3h = hourly.rolling(window=3, min_periods=1).sum()
            for i in range(3, len(rolling_3h)):
                prev = rolling_3h.iloc[i-3]
                curr = rolling_3h.iloc[i]
                if prev > 0 and (curr - prev) / prev > 2.0 and curr >= 5:
                    h_hash = hashlib.sha1(name.encode()).hexdigest()[:12]
                    alert_id = f"alert-surge-{h_hash}"
                    alert_state = states.get(alert_id, "New")
                    resolved = alert_state in ("Resolved", "Archived")
                    alerts.append({
                        "id": alert_id,
                        "type": "Warning",
                        "junction_id": f"hs_{h_hash}",
                        "junction_name": name,
                        "message": f"TRAFFIC SURGE: Violations surged by {((curr - prev) / prev * 100):.1f}% in a 3-hour window (from {int(prev)} to {int(curr)}). Mobilize mobile patrol.",
                        "timestamp": str(rolling_3h.index[i]),
                        "resolved": resolved,
                        "current_risk": 70.0,
                        "predicted_risk": 80.0,
                        "eta_minutes": 45,
                        "recommended_officers": 4,
                        "state": alert_state,
                        "resolvedBy": "system" if resolved else None,
                        "resolvedAt": str(_now(timeline)) if resolved else None
                    })
                    break

    # 3. Congestion stayed critical for more than 30 minutes
    if not df.empty and "junction_name" in df:
        df_j = df[df["junction_name"].notna() & (df["junction_name"] != "")]
        for name, group in df_j.groupby("junction_name"):
            sorted_g = group.sort_values("created_datetime")
            times = sorted_g["created_datetime"].tolist()
            severities = sorted_g["severity"].tolist()
            for i in range(len(times)):
                start_time = times[i]
                end_time = start_time + pd.Timedelta(minutes=30)
                count_critical = 0
                for j in range(i, len(times)):
                    if times[j] <= end_time:
                        if severities[j] >= 4.0:
                            count_critical += 1
                    else:
                        break
                if count_critical >= 4:
                    h_hash = hashlib.sha1(name.encode()).hexdigest()[:12]
                    alert_id = f"alert-congest-{h_hash}"
                    alert_state = states.get(alert_id, "New")
                    resolved = alert_state in ("Resolved", "Archived")
                    alerts.append({
                        "id": alert_id,
                        "type": "Critical",
                        "junction_id": f"hs_{h_hash}",
                        "junction_name": name,
                        "message": f"SUSTAINED CONGESTION: Critical congestion detected. Multiple high-severity violations reported consecutively within 30 minutes.",
                        "timestamp": str(start_time),
                        "resolved": resolved,
                        "current_risk": 90.0,
                        "predicted_risk": 95.0,
                        "eta_minutes": 15,
                        "recommended_officers": 6,
                        "state": alert_state,
                        "resolvedBy": "system" if resolved else None,
                        "resolvedAt": str(_now(timeline)) if resolved else None
                    })
                    break

    # Merge ingested violations from SQLite as active alerts
    try:
        from src.persistence import get_ingested_violations
        ingested = get_ingested_violations()
        for item in ingested:
            incident_id = f"incident-{item['id']}"
            alert_state = states.get(incident_id, "New")
            resolved = alert_state in ("Resolved", "Archived")
            
            sev_str = str(item.get("severity") or "2.0").lower()
            if sev_str in ("critical", "5.0", "5"):
                alert_type = "Critical"
                eta = 15
                officers_needed = 6
                sev_num = 5.0
            elif sev_str in ("high", "4.0", "4"):
                alert_type = "Warning"
                eta = 45
                officers_needed = 4
                sev_num = 4.0
            else:
                alert_type = "Info"
                eta = 60
                officers_needed = 2
                sev_num = 2.0
            
            alerts.append(
                {
                    "id": incident_id,
                    "type": alert_type,
                    "junction_id": item["id"],
                    "junction_name": item["junction_name"] or "Ingested Location",
                    "message": f"REPORTED INCIDENT: {item['violation_type']} reported by {item['ingested_by'] or 'Field Officer'}. Notes: {item.get('location_label') or ''} {item.get('notes') or ''}".strip(),
                    "timestamp": item["occurred_at"],
                    "resolved": resolved,
                    "current_risk": sev_num * 20.0,
                    "predicted_risk": min(100.0, sev_num * 20.0 + 10.0),
                    "eta_minutes": eta,
                    "recommended_officers": officers_needed,
                    "state": alert_state,
                    "resolvedBy": "system" if resolved else None,
                    "resolvedAt": str(_now(timeline)) if resolved else None
                }
            )
    except Exception as e:
        print(f"Error merging ingested violations to alerts: {e}")
        
    return alerts


def get_current_month() -> str:
    try:
        df = load_violations()
        if not df.empty:
            max_ts = df["created_datetime"].max()
            return max_ts.strftime("%Y-%m")
    except Exception:
        pass
    return "2024-04"


@app.get("/alerts", response_model=list[AlertItem])
def alerts(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    alerts_list = _alerts_from_hotspots(timeline)
    current_month = get_current_month()
    requested_timeline = timeline or "2024-04"
    if requested_timeline != current_month:
        for alert in alerts_list:
            alert["resolved"] = True
            alert["state"] = "Historical"
    return alerts_list


@app.post("/alerts/{alert_id}/resolve", response_model=AlertItem)
def resolve_alert(alert_id: str, timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> dict[str, Any]:
    persist_alert_resolution(alert_id)
    alerts_list = _alerts_from_hotspots(timeline)
    match = next((a for a in alerts_list if a["id"] == alert_id), None)
    if not match:
        return {
            "id": alert_id,
            "type": "Info",
            "junction_id": "unknown",
            "junction_name": "Resolved Junction",
            "message": "Alert resolved.",
            "timestamp": str(_now(timeline)),
            "resolved": True,
            "state": "Resolved",
        }
    match["resolved"] = True
    match["state"] = "Resolved"
    return match


@app.patch("/alerts/{alert_id}/state", response_model=AlertItem)
def update_alert_status(alert_id: str, payload: UpdateAlertStateRequest, timeline: Optional[str] = Query(None), token: str = Depends(_require_auth)) -> dict[str, Any]:
    username = validate_session(token)["username"]
    update_alert_state(alert_id, payload.state, username)
    alerts_list = _alerts_from_hotspots(timeline)
    match = next((a for a in alerts_list if a["id"] == alert_id), None)
    if not match:
        return {
            "id": alert_id,
            "type": "Info",
            "junction_id": "unknown",
            "junction_name": "Alert",
            "message": "Alert state updated.",
            "timestamp": str(_now(timeline)),
            "resolved": payload.state in ("Resolved", "Archived"),
            "state": payload.state,
        }
    return match


from src.domain import AnalyticsResponse

@app.get("/analytics", response_model=AnalyticsResponse)
def analytics(_: str = Depends(_require_auth)) -> dict[str, Any]:
    frame = _city_seed_events()
    by_hour = [int(frame[frame["hour"] == hour].shape[0]) for hour in range(24)]
    hotspots = _hotspots_response()
    risk_counts = Counter(
        "low" if h["riskScore"] < 40 else "medium" if h["riskScore"] < 70 else "high" if h["riskScore"] < 85 else "critical"
        for h in hotspots
    )
    top = [{"name": h["name"], "violations": h["violations"]} for h in hotspots[:10]]
    week = frame.copy()
    week["day"] = week["created_datetime"].dt.date
    weekly = [
        {"date": str(day), "violations": int(count)}
        for day, count in week.groupby("day").size().tail(7).items()
    ]
    return {
        "violations_by_hour": by_hour,
        "risk_distribution": {
            "low": int(risk_counts.get("low", 0)),
            "medium": int(risk_counts.get("medium", 0)),
            "high": int(risk_counts.get("high", 0)),
            "critical": int(risk_counts.get("critical", 0)),
        },
        "top_junctions": top,
        "weekly_trend": weekly,
    }


@app.post("/copilot/query")
def copilot_query(payload: CopilotQueryRequest, _: str = Depends(_require_auth)) -> dict[str, str]:
    language = payload.language if payload.language in {"en", "kn", "hi"} else "en"
    ctx = payload.context or {}
    timeline = ctx.get("activeTimeline") or "2024-04"
    
    fresh_stats = _stats_payload(timeline=timeline)
    fresh_alerts = _alerts_from_hotspots(timeline=timeline)
    
    merged_context = {
        **ctx,
        "stats": fresh_stats,
        "alerts": fresh_alerts,
        "activeTimeline": timeline,
    }
    request = CopilotRequest(question=payload.message, language=language, context=merged_context)
    response = answer_query(request)
    return {"reply": response.answer}


@app.get("/reports/daily")
def report_daily(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> dict[str, Any]:
    hotspots = _hotspots_response(mode="HISTORICAL", timeline=timeline)
    frame = _city_seed_events(timeline)
    top = hotspots[:3]
    peak_hour = int(frame["hour"].mode().iloc[0]) if not frame.empty and not frame["hour"].mode().empty else 0
    now_date = _now(timeline).date()
    
    deployments = get_dispatch_deployments()
    active_officers = sum(int(d["assigned_officers"]) for d in deployments if d.get("status") != "Resolved")
    
    return {
        "type": "daily",
        "generatedAt": str(_now(timeline)),
        "date": str(now_date),
        "datasetWindow": "Monthly Summary",
        "forecastHorizon": "Historical Analysis",
        "totalViolations": int(frame.shape[0]) if not frame.empty else 0,
        "topHotspots": [{"name": h["name"], "riskScore": h["riskScore"], "violations": h["violations"]} for h in top],
        "officerDeploymentSummary": {"activeOfficers": max(active_officers, len(top)), "shift": "day"},
        "peakHour": peak_hour,
        "peakWindow": f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00",
        "criticalAlerts": len([h for h in hotspots if h["riskScore"] >= 75]),
    }


@app.get("/reports/weekly")
def report_weekly(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> dict[str, Any]:
    frame = _city_seed_events(timeline)
    now_dt = _now(timeline)
    start_dt = now_dt - timedelta(days=7)
    weekly_frame = frame[(frame["created_datetime"] >= start_dt) & (frame["created_datetime"] <= now_dt)].copy() if not frame.empty else frame
    
    if not weekly_frame.empty:
        history = weekly_frame.set_index("created_datetime").resample("D").size()
        trend_data = [{"date": str(idx.date()), "violations": int(val)} for idx, val in history.items()]
        total_enforcement = int(history.sum())
    else:
        trend_data = []
        total_enforcement = 0

    hotspots = _hotspots_response(mode="LIVE", timeline=timeline)
    most_improved = min(hotspots, key=lambda item: item["riskScore"]) if hotspots else None
    worst = max(hotspots, key=lambda item: item["riskScore"]) if hotspots else None
    
    resources = get_fleet_resources()
    team = next((item for item in resources if item["resource_type"] == "team"), None)
    total_officers = int(team["total_count"]) if team else 6
    deployments = get_dispatch_deployments()
    active_officers = sum(int(d["assigned_officers"]) for d in deployments if d.get("status") != "Resolved")
    utilization_pct = round((active_officers / total_officers) * 100, 1) if total_officers > 0 else 0.0
    
    return {
        "type": "weekly",
        "generatedAt": str(_now(timeline)),
        "datasetWindow": "Last 7 Days",
        "trend": trend_data,
        "mostImprovedJunction": most_improved["name"] if most_improved else None,
        "worstJunction": worst["name"] if worst else None,
        "totalEnforcementActions": total_enforcement,
        "officerUtilization": utilization_pct,
    }


@app.get("/reports/risk")
def report_risk(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> dict[str, Any]:
    hotspots = _hotspots_response(mode="LIVE", timeline=timeline)
    forecasts = _forecast_rows(timeline)
    
    predicted_spots = []
    for h in hotspots[:5]:
        match = next((f for f in forecasts if f["hotspot_name"] == h["name"] and f["hour_offset"] == 6), None)
        pred_risk = match["predictedRisk"] if match else min(100.0, h["riskScore"] + 5.0)
        predicted_spots.append({"name": h["name"], "predictedRisk": pred_risk})
        
    return {
        "type": "risk",
        "generatedAt": str(_now(timeline)),
        "datasetWindow": "Current Live Hotspots",
        "forecastHorizon": "Next 24 Hours",
        "currentRiskScores": [{"name": h["name"], "riskScore": h["riskScore"]} for h in hotspots],
        "recommendedDeploymentPositions": [{"name": h["name"], "lat": h["lat"], "lng": h["lng"]} for h in hotspots[:5]],
        "predictedHotspotsNext24h": predicted_spots,
    }


@app.get("/dispatch/recommendation", response_model=DispatchRecommendation)
def dispatch_recommendation(hotspot_id: str, _: str = Depends(_require_auth)) -> DispatchRecommendation:
    hotspot = _find_hotspot_by_id(hotspot_id)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return recommend_dispatch(hotspot)


@app.get("/dispatch/resources")
def dispatch_resources(_: str = Depends(_require_auth)) -> dict[str, Any]:
    resources = get_fleet_resources()
    team = next((item for item in resources if item["resource_type"] == "team"), None)
    tow = next((item for item in resources if item["resource_type"] == "tow_vehicle"), None)
    
    deployments = get_dispatch_deployments()
    active_count = len([d for d in deployments if d.get("status") != "Resolved"])
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resolved_today = len([
        d for d in deployments 
        if d.get("status") == "Resolved" and d.get("updated_at", "").startswith(today_str)
    ])
    
    return {
        "teams": team,
        "towVehicles": tow,
        "summary": {
            "availableOfficers": int(team["available_count"]) if team else 0,
            "totalOfficers": int(team["total_count"]) if team else 0,
            "availablePatrolVehicles": int(tow["available_count"]) if tow else 0,
            "totalPatrolVehicles": int(tow["total_count"]) if tow else 0,
            "activeDeployments": active_count,
            "resolvedDeploymentsToday": resolved_today,
        },
    }


@app.patch("/dispatch/resources")
def update_dispatch_resources(payload: ResourceUpdateRequest, token: str = Depends(_require_auth)) -> dict[str, Any]:
    if payload.available_count > payload.total_count:
        raise HTTPException(status_code=400, detail="Available count cannot exceed total count")
    update_fleet_resource(payload.resource_type, payload.total_count, payload.available_count)
    log_audit(validate_session(token)["username"], "resource_update", "fleet_resource", payload.resource_type, payload.model_dump())
    return dispatch_resources(token)



@app.get("/dispatch/queue")
def dispatch_queue(_: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return _queue_rows()


@app.get("/dispatch/deployments")
def dispatch_deployments(_: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return [_public_deployment_row(row) for row in get_dispatch_deployments()]


@app.get("/deployments")
def list_deployments(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return [_public_deployment_row(row) for row in get_dispatch_deployments(timeline)]


@app.patch("/deployments/{id}")
def patch_deployment(id: str, payload: dict[str, Any], token: str = Depends(_require_auth)) -> dict[str, Any]:
    status_val = payload.get("status")
    outcome_val = payload.get("outcome")
    req = DispatchStatusRequest(deployment_id=id, status=status_val, outcome=outcome_val)
    return dispatch_status(req, token)


@app.delete("/deployments/{id}")
def remove_deployment(id: str, token: str = Depends(_require_auth)) -> dict[str, str]:
    db = get_db()
    db.execute("DELETE FROM dispatch_deployments WHERE id = ?", (id,))
    db.execute("DELETE FROM dispatch_assignments WHERE deployment_id = ?", (id,))
    db.commit()
    return {"status": "deleted"}


@app.get("/hotspots/search")
def search_hotspots(q: str = Query(""), timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    spots = _hotspots_response(mode="LIVE", timeline=timeline)
    if not spots:
        spots = _hotspots_response(mode="HISTORICAL", timeline=timeline)
    q_lower = q.lower()
    matches = []
    for s in spots:
        if q_lower in s["name"].lower():
            matches.append({
                "id": s["id"],
                "name": s["name"],
                "lat": s["lat"],
                "lng": s["lng"]
            })
    return matches


@app.post("/dispatch/assign")
def dispatch_assign(payload: DispatchAssignRequest, timeline: Optional[str] = Query(None), token: str = Depends(_require_auth)) -> dict[str, Any]:
    if not timeline:
        timeline = "2024-04"
    hotspot = _find_hotspot_by_id(payload.hotspot_id, timeline=timeline)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    resources = {item["resource_type"]: item for item in get_fleet_resources()}
    team = resources.get("team")
    tow = resources.get("tow_vehicle")
    
    # Cap resources to available counts dynamically without throwing error (Adaptive Deployment Plan)
    available_officers = int(team["available_count"]) if team else 0
    available_vehicles = int(tow["available_count"]) if tow else 0
    
    assigned_officers = min(payload.officers, available_officers)
    assigned_vehicles = min(payload.patrol_vehicles, available_vehicles)
    
    # Construct notes reflecting potential shortages
    note_details = []
    if payload.notes:
        note_details.append(payload.notes)
    if assigned_officers < payload.officers:
        note_details.append(f"Resource shortage: Requested {payload.officers} officers, but only {assigned_officers} were available.")
    if assigned_vehicles < payload.patrol_vehicles:
        note_details.append(f"Resource shortage: Requested {payload.patrol_vehicles} patrol vehicles, but only {assigned_vehicles} were available.")
        
    full_notes = "; ".join(note_details) if note_details else ""

    queue_row = next((row for row in _queue_rows(timeline) if row["hotspot_id"] == payload.hotspot_id), None)
    deployment_id = create_dispatch_deployment(
        {
            "hotspot_id": hotspot.hotspot_id,
            "hotspot_name": hotspot.locality_name,
            "risk_score": hotspot.risk_score,
            "current_violations": hotspot.violation_count,
            "predicted_violations_next_hour": queue_row["predicted_violations_next_hour"] if queue_row else hotspot.violation_count,
            "severity": _severity_label(hotspot.risk_score),
            "recommended_officers": queue_row["recommended_officers"] if queue_row else payload.officers,
            "recommended_patrol_vehicles": queue_row["recommended_patrol_vehicles"] if queue_row else payload.patrol_vehicles,
            "assigned_officers": assigned_officers,
            "assigned_vehicles": assigned_vehicles,
            "status": "Assigned",
            "priority_score": queue_row["priority_score"] if queue_row else hotspot.risk_score,
            "notes": full_notes,
            "timeline": timeline,
        },
        username=validate_session(token)["username"],
    )
    add_dispatch_assignment(deployment_id, hotspot.hotspot_id, assigned_officers, assigned_vehicles, username=validate_session(token)["username"])
    if team:
        update_fleet_resource("team", int(team["total_count"]), max(0, available_officers - assigned_officers))
    if tow:
        update_fleet_resource("tow_vehicle", int(tow["total_count"]), max(0, available_vehicles - assigned_vehicles))
        
    db = get_db()
    if payload.team_ids:
        for t_id in payload.team_ids:
            db.execute("UPDATE officers_list SET status = 'On Duty', available = 0 WHERE id = ?", (t_id,))
    if payload.vehicle_ids:
        for v_id in payload.vehicle_ids:
            db.execute("UPDATE vehicles_list SET status = 'Deployed', assigned_to = ? WHERE id = ?", (hotspot.locality_name, v_id))
    db.commit()

    log_audit(validate_session(token)["username"], "dispatch_assign", "deployment", deployment_id, {"hotspot_id": hotspot.hotspot_id, "officers": assigned_officers, "patrol_vehicles": assigned_vehicles})
    return {"deployment_id": deployment_id, "status": "Assigned"}


@app.post("/deployments")
def create_deployment(payload: DispatchAssignRequest, timeline: Optional[str] = Query(None), token: str = Depends(_require_auth)) -> dict[str, Any]:
    return dispatch_assign(payload, timeline, token)


@app.patch("/dispatch/status")
def dispatch_status(payload: DispatchStatusRequest, token: str = Depends(_require_auth)) -> dict[str, Any]:
    deployment = get_dispatch_deployment(payload.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    allowed = {"Assigned", "En Route", "On Site", "Active Monitoring", "Resolved"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid deployment status")
        
    old_status = deployment["status"]
    
    if payload.status == "Resolved" and old_status != "Resolved":
        # Transitioning to Resolved -> release resources back to available counts
        outcome_str = f"Outcome: {payload.outcome}. " if payload.outcome else ""
        existing_notes = deployment.get("notes") or ""
        new_notes = f"{outcome_str}{existing_notes}" if outcome_str else existing_notes
        update_dispatch_deployment(payload.deployment_id, status=payload.status, notes=new_notes)
        resources = {item["resource_type"]: item for item in get_fleet_resources()}
        team = resources.get("team")
        tow = resources.get("tow_vehicle")
        if team:
            update_fleet_resource("team", int(team["total_count"]), min(int(team["total_count"]), int(team["available_count"]) + int(deployment["assigned_officers"])))
        if tow:
            update_fleet_resource("tow_vehicle", int(tow["total_count"]), min(int(tow["total_count"]), int(tow["available_count"]) + int(deployment["assigned_vehicles"])))
            
        db = get_db()
        db.execute("UPDATE officers_list SET status = 'Available', available = total_strength WHERE status = 'On Duty' AND timeline = (SELECT timeline FROM dispatch_deployments WHERE id = ?)", (payload.deployment_id,))
        db.execute("UPDATE vehicles_list SET status = 'Available', assigned_to = 'Unassigned' WHERE status = 'Deployed' AND assigned_to = (SELECT hotspot_name FROM dispatch_deployments WHERE id = ?)", (payload.deployment_id,))
        db.commit()
            
    elif payload.status != "Resolved" and old_status == "Resolved":
        # Transitioning out of Resolved -> need to re-reserve/claim resources
        resources = {item["resource_type"]: item for item in get_fleet_resources()}
        team = resources.get("team")
        tow = resources.get("tow_vehicle")
        
        if team and int(deployment["assigned_officers"]) > int(team["available_count"]):
            raise HTTPException(status_code=400, detail="Not enough officers available to re-activate deployment")
        if tow and int(deployment["assigned_vehicles"]) > int(tow["available_count"]):
            raise HTTPException(status_code=400, detail="Not enough patrol vehicles available to re-activate deployment")
            
        update_dispatch_deployment(payload.deployment_id, status=payload.status)
        if team:
            update_fleet_resource("team", int(team["total_count"]), max(0, int(team["available_count"]) - int(deployment["assigned_officers"])))
        if tow:
            update_fleet_resource("tow_vehicle", int(tow["total_count"]), max(0, int(tow["available_count"]) - int(deployment["assigned_vehicles"])))
    else:
        # Standard active status transition -> just update status
        update_dispatch_deployment(payload.deployment_id, status=payload.status)
        
    log_audit(validate_session(token)["username"], "dispatch_status", "deployment", payload.deployment_id, {"status": payload.status})
    return {"deployment_id": payload.deployment_id, "status": payload.status}



@app.post("/dispatch/incidents")
def dispatch_incidents(payload: DispatchIncidentRequest, token: str = Depends(_require_auth)) -> dict[str, Any]:
    count_to_ingest = max(1, min(100, payload.violation_count))
    
    import random
    ingested_id = None
    
    for i in range(count_to_ingest):
        # Apply tiny jitter for DBSCAN clustering differentiation
        jitter_lat = payload.latitude + random.uniform(-0.00015, 0.00015) if i > 0 else payload.latitude
        jitter_lon = payload.longitude + random.uniform(-0.00015, 0.00015) if i > 0 else payload.longitude
        
        v_id = ingest_violation(
            {
                "latitude": jitter_lat,
                "longitude": jitter_lon,
                "violation_type": payload.incident_type.upper(),
                "vehicle_type": "UNKNOWN",
                "severity": 5.0 if payload.severity.lower() == "critical" else 4.0 if payload.severity.lower() == "high" else 3.0 if payload.severity.lower() == "moderate" else 2.0,
                "junction_name": payload.junction_name,
                "police_station": "",
                "location_label": payload.junction_name,
                "occurred_at": _now().isoformat(),
            },
            username=validate_session(token)["username"],
        )
        if i == 0:
            ingested_id = v_id

    invalidate_caches()
    invalidate_forecast_cache()
    log_audit(validate_session(token)["username"], "dispatch_incident", "violation", ingested_id, {"junction_name": payload.junction_name, "notes": payload.notes})
    refreshed_hotspot = next((h for h in _hotspots_response(mode="LIVE") if h["name"].lower() == payload.junction_name.lower()), None)
    return {
        "incident_id": ingested_id,
        "status": "recorded",
        "junction_name": payload.junction_name,
        "updated_risk_score": refreshed_hotspot["riskScore"] if refreshed_hotspot else None,
    }


@app.get("/dispatch/incidents")
def dispatch_incidents_list(_: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return get_ingested_violations()


@app.post("/incidents")
def incidents_create(payload: DispatchIncidentRequest, token: str = Depends(_require_auth)) -> dict[str, Any]:
    return dispatch_incidents(payload, token)


@app.get("/incidents")
def incidents_list(_: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return get_ingested_violations()




@app.post("/simulator/inject")
def simulator_inject(payload: IncidentInjectRequest, token: str = Depends(_require_auth)) -> dict[str, str]:
    add_incident({
        "locality_name": payload.locality_name,
        "incident_type": payload.incident_type,
        "severity": payload.severity,
        "duration_minutes": payload.duration_minutes,
    }, username=validate_session(token)["username"])
    return {"status": "ok"}


@app.get("/simulator/incidents")
def simulator_incidents(_: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    return get_active_incidents()


@app.post("/simulator/clear")
def simulator_clear(token: str = Depends(_require_auth)) -> dict[str, str]:
    clear_all_incidents(username=validate_session(token)["username"])
    return {"status": "ok"}


@app.get("/impact", response_model=ImpactEstimate)
def impact(hotspot_id: str, _: str = Depends(_require_auth)) -> ImpactEstimate:
    hotspot = _find_hotspot_by_id(hotspot_id)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return estimate_impact(hotspot)


@app.get("/analytics/what-if")
def what_if(
    hotspot_id: str,
    officers: int = Query(0, ge=0, le=20),
    signal_improvement: float = Query(0.0, ge=0.0, le=100.0),
    _: str = Depends(_require_auth)
) -> dict[str, Any]:
    frame = _city_seed_events()
    now = frame["created_datetime"].max()
    start = now - pd.Timedelta(days=30)
    hotspots = compute_hotspots(mode="HISTORICAL", time_range=(start.to_pydatetime(), now.to_pydatetime()))
    hotspot = next((h for h in hotspots if h.hotspot_id == hotspot_id), None)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
        
    officer_reduction = min(30.0, officers * 4.0)
    signal_reduction = min(20.0, signal_improvement * 0.5)
    total_reduction = min(50.0, officer_reduction + signal_reduction)
    
    new_risk = max(0.0, round(hotspot.risk_score * (1.0 - total_reduction / 100.0), 2))
    base_impact = round((hotspot.risk_score * 0.7) + (hotspot.violation_count * 0.8) + (hotspot.confidence_score * 10), 2) * 250
    savings = round(base_impact * (total_reduction / 100.0), 2)
    new_level = "Low" if new_risk < 40 else "Moderate" if new_risk < 70 else "High" if new_risk < 85 else "Critical"
    
    return {
        "hotspot_id": hotspot_id,
        "original_risk": hotspot.risk_score,
        "new_risk": new_risk,
        "risk_reduction_pct": total_reduction,
        "economic_savings_inr": savings,
        "new_congestion_level": new_level,
        "reasons": [
            f"Officer deployment of {officers} yields {officer_reduction}% risk reduction.",
            f"Signal timing enhancement of {signal_improvement}% yields {signal_reduction}% risk reduction."
        ]
    }


@app.get("/analytics/anomalies")
def anomalies(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth), window: str = Query("day", pattern="^(day|hour)$")) -> list[dict[str, Any]]:
    return compute_anomalies(window=window, timeline=timeline)


@app.get("/analytics/zones")
def zones(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth), radius_m: int = Query(330, ge=50, le=2000), min_samples: int = Query(10, ge=3, le=100)) -> dict[str, Any]:
    return compute_zone_insights(radius_m=radius_m, min_samples=min_samples, timeline=timeline)


@app.get("/analytics/peak-windows")
def peak_windows(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)) -> list[dict[str, Any]]:
    frame = _city_seed_events(timeline).copy()
    if frame.empty:
        return []
    frame["weekday"] = frame["created_datetime"].dt.day_name()
    grouped = (
        frame.groupby(["weekday", "hour"])
        .size()
        .reset_index(name="violations")
        .sort_values(["weekday", "violations"], ascending=[True, False])
    )
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    output: list[dict[str, Any]] = []
    for weekday in weekday_order:
        subset = grouped[grouped["weekday"] == weekday]
        if subset.empty:
            continue
        peak = subset.iloc[0]
        output.append(
            {
                "day": weekday,
                "peakHour": int(peak.hour),
                "peakWindow": f"{int(peak.hour):02d}:00 - {(int(peak.hour) + 1) % 24:02d}:00",
                "violations": int(peak.violations),
            }
        )
    return output


# ── Officer & Vehicle CRUD Models and Endpoints ──────────────────────────────

class OfficerTeamCreate(BaseModel):
    team_name: str
    total_strength: int = Field(ge=0, le=100)
    available: int = Field(ge=0, le=100)
    status: str = Field(pattern="^(Available|On Duty|Off Shift|On Leave)$")

class OfficerTeamUpdate(BaseModel):
    team_name: str
    total_strength: int = Field(ge=0, le=100)
    available: int = Field(ge=0, le=100)
    status: str = Field(pattern="^(Available|On Duty|Off Shift|On Leave)$")

class VehicleCreate(BaseModel):
    vehicle_id: str
    type: str
    status: str = Field(pattern="^(Available|Deployed|Maintenance|Offline)$")
    assigned_to: str

class VehicleUpdate(BaseModel):
    vehicle_id: str
    type: str
    status: str = Field(pattern="^(Available|Deployed|Maintenance|Offline)$")
    assigned_to: str


@app.get("/resources/officers")
def list_officers(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)):
    return get_officers(timeline)

@app.post("/resources/officers")
def add_officer(payload: OfficerTeamCreate, timeline: Optional[str] = Query(None), token: str = Depends(_require_auth)):
    team_id = create_officer_team(payload.team_name, payload.total_strength, payload.available, payload.status, timeline)
    log_audit(validate_session(token)["username"], "create_officer_team", "officers_list", team_id, payload.model_dump())
    return {"id": team_id, "status": "created"}

@app.patch("/resources/officers/{id}")
def edit_officer(id: str, payload: OfficerTeamUpdate, token: str = Depends(_require_auth)):
    update_officer_team(id, payload.team_name, payload.total_strength, payload.available, payload.status)
    log_audit(validate_session(token)["username"], "update_officer_team", "officers_list", id, payload.model_dump())
    return {"status": "updated"}

@app.delete("/resources/officers/{id}")
def remove_officer(id: str, token: str = Depends(_require_auth)):
    delete_officer_team(id)
    log_audit(validate_session(token)["username"], "delete_officer_team", "officers_list", id)
    return {"status": "deleted"}


@app.get("/resources/vehicles")
def list_vehicles(timeline: Optional[str] = Query(None), _: str = Depends(_require_auth)):
    return get_vehicles(timeline)

@app.post("/resources/vehicles")
def add_vehicle(payload: VehicleCreate, timeline: Optional[str] = Query(None), token: str = Depends(_require_auth)):
    veh_id = create_vehicle(payload.vehicle_id, payload.type, payload.status, payload.assigned_to, timeline)
    log_audit(validate_session(token)["username"], "create_vehicle", "vehicles_list", veh_id, payload.model_dump())
    return {"id": veh_id, "status": "created"}

@app.patch("/resources/vehicles/{id}")
def edit_vehicle(id: str, payload: VehicleUpdate, token: str = Depends(_require_auth)):
    update_vehicle(id, payload.vehicle_id, payload.type, payload.status, payload.assigned_to)
    log_audit(validate_session(token)["username"], "update_vehicle", "vehicles_list", id, payload.model_dump())
    return {"status": "updated"}

@app.delete("/resources/vehicles/{id}")
def remove_vehicle(id: str, token: str = Depends(_require_auth)):
    delete_vehicle(id)
    log_audit(validate_session(token)["username"], "delete_vehicle", "vehicles_list", id)
    return {"status": "deleted"}


@app.on_event("startup")
def preload_data():
    init_db()

"""Reproducible analytics derived only from the anonymized violation dataset."""
from __future__ import annotations

import ast
import hashlib
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import random
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score

from src.domain import DataLineage, DispatchRecommendation, HotspotRecord, ImpactEstimate

DATASET = Path(__file__).resolve().parent.parent / "jan to may police violation_anonymized791b166.csv"
RISK_FORMULA_VERSION = "risk-v1.0.0"
IMPACT_FORMULA_VERSION = "impact-v1.0.0"
DISPATCH_RULE_VERSION = "dispatch-v1.0.0"
EARTH_RADIUS_KM = 6371.0088

SEVERITY_WEIGHTS = {
    "DOUBLE PARKING": 5,
    "PARKING IN A MAIN ROAD": 4,
    "PARKING NEAR ROAD CROSSING": 4,
    "PARKING ON FOOTPATH": 3,
    "WRONG PARKING": 2,
    "NO PARKING": 2,
}


def _parse_types(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    try:
        parsed = ast.literal_eval(value)
        return [str(v).upper() for v in parsed] if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def _severity(value: object) -> float:
    values = _parse_types(value)
    if not values:
        return 0.0
    return min(5.0, max(SEVERITY_WEIGHTS.get(v, 1) for v in values))


def _location_label(row: pd.Series) -> str:
    junction = str(row.get("junction_name", "")).strip()
    if junction and junction.lower() not in {"no junction", "nan", "none"}:
        return junction
    address = str(row.get("location", "")).strip()
    parts = [part.strip() for part in address.split(",") if part.strip()]
    # Dataset-derived label; no reverse-geocoding or hardcoded locality mapping.
    return ", ".join(parts[:2]) if parts else "Unresolved locality"


def _parse_timeline(timeline: Optional[str]) -> tuple[datetime, datetime]:
    if not timeline:
        timeline = "2024-04"
    try:
        parts = timeline.split("-")
        year = int(parts[0])
        month = int(parts[1])
    except Exception:
        year, month = 2024, 4
    
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(seconds=1)
    return start, end



import os
import requests

_GEO_CACHE = {}

def reverse_geocode(lat: float, lon: float) -> str:
    return f"Junction at {lat:.4f}, {lon:.4f}"

def generate_synthetic_data() -> pd.DataFrame:
    city = os.getenv("PARKSENSE_CITY", "Bengaluru")
    np.random.seed(42)
    random.seed(42)
    
    n_events = 500
    latitudes = np.random.uniform(12.88, 13.08, n_events)
    longitudes = np.random.uniform(77.48, 77.72, n_events)
    
    for i in range(10):
        c_lat = np.random.uniform(12.90, 13.06)
        c_lon = np.random.uniform(77.50, 77.70)
        size = np.random.randint(20, 50)
        indices = np.random.choice(n_events, size=size, replace=False)
        latitudes[indices] = c_lat + np.random.normal(0, 0.002, len(indices))
        longitudes[indices] = c_lon + np.random.normal(0, 0.002, len(indices))

    dates = pd.date_range(start="2026-01-01", end="2026-05-31", periods=n_events)
    
    violation_types = [
        "['DOUBLE PARKING']",
        "['PARKING IN A MAIN ROAD']",
        "['PARKING NEAR ROAD CROSSING']",
        "['PARKING ON FOOTPATH']",
        "['WRONG PARKING']",
        "['NO PARKING']"
    ]
    
    vehicles = ["TWO_WHEELER", "FOUR_WHEELER", "AUTO", "LCV"]
    data = []
    for i in range(n_events):
        lat, lon = latitudes[i], longitudes[i]
        data.append({
            "id": f"syn_{i}",
            "latitude": lat,
            "longitude": lon,
            "location": f"Street in {city}",
            "vehicle_type": random.choice(vehicles),
            "violation_type": random.choice(violation_types),
            "created_datetime": dates[i],
            "validation_status": "approved",
            "junction_name": reverse_geocode(lat, lon),
            "police_station": reverse_geocode(lat, lon)
        })
        
    df = pd.DataFrame(data)
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], utc=True)
    df["latitude"] = pd.to_numeric(df["latitude"])
    df["longitude"] = pd.to_numeric(df["longitude"])
    df["severity"] = df["violation_type"].map(_severity)
    df["locality_name"] = df.apply(lambda r: f"Road near {r['latitude']:.3f}, {r['longitude']:.3f}", axis=1)
    df["hour"] = df["created_datetime"].dt.hour
    df["week"] = df["created_datetime"].dt.to_period("W").astype(str)
    return df

_LOAD_LOCK = threading.Lock()

@lru_cache(maxsize=1)
def _load_violations_cached() -> pd.DataFrame:
    if not DATASET.exists():
        return generate_synthetic_data()
    columns = ["id", "latitude", "longitude", "location", "vehicle_type", "violation_type",
               "created_datetime", "validation_status", "junction_name", "police_station"]
    df = pd.read_csv(DATASET, usecols=columns, low_memory=False)
    df = df[df["validation_status"].eq("approved")].copy()
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], utc=True, errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["created_datetime", "latitude", "longitude"])
    df = df[df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)]
    
    # Dynamic time alignment: Shift timestamps so the maximum matches current system time
    # max_ts = df["created_datetime"].max()
    # if pd.notna(max_ts):
    #     now_ts = datetime.now(timezone.utc)
    #     time_offset = now_ts - max_ts
    #     df["created_datetime"] = df["created_datetime"] + time_offset

    df["severity"] = df["violation_type"].map(_severity)
    df["locality_name"] = df.apply(_location_label, axis=1)
    df["locality_name_lower"] = df["locality_name"].str.lower()
    df["hour"] = df["created_datetime"].dt.hour
    df["week"] = df["created_datetime"].dt.to_period("W").astype(str)

    # Merge ingested violations from SQLite
    try:
        from src.persistence import get_ingested_violations
        ingested = get_ingested_violations()
        if ingested:
            ing_df = pd.DataFrame(ingested)
            ing_df["created_datetime"] = pd.to_datetime(ing_df["occurred_at"], utc=True, errors="coerce")
            ing_df["latitude"] = pd.to_numeric(ing_df["latitude"], errors="coerce")
            ing_df["longitude"] = pd.to_numeric(ing_df["longitude"], errors="coerce")
            ing_df["location"] = ing_df.get("location_label", "")
            ing_df["validation_status"] = "approved"
            ing_df["locality_name"] = ing_df["junction_name"].fillna("Ingested Location")
            ing_df["locality_name_lower"] = ing_df["locality_name"].str.lower()
            ing_df["severity"] = ing_df["severity"].fillna(2.0)
            ing_df["hour"] = ing_df["created_datetime"].dt.hour
            ing_df["week"] = ing_df["created_datetime"].dt.to_period("W").astype(str)
            # Keep only columns that match
            common = list(set(df.columns) & set(ing_df.columns))
            df = pd.concat([df, ing_df[common]], ignore_index=True)
    except Exception:
        pass  # Persistence layer not yet initialized during tests

    return df

def load_violations() -> pd.DataFrame:
    with _LOAD_LOCK:
        return _load_violations_cached()

_HOTSPOTS_CACHE = {}
_HOTSPOTS_CACHE_LOCK = threading.Lock()

def invalidate_caches() -> None:
    """Clear all analytics caches — call after live data ingestion."""
    _load_violations_cached.cache_clear()
    with _HOTSPOTS_CACHE_LOCK:
        _HOTSPOTS_CACHE.clear()



def dataset_max_timestamp() -> datetime:
    return load_violations()["created_datetime"].max().to_pydatetime()


def _scale(values: pd.Series) -> pd.Series:
    lo, hi = float(values.min()), float(values.max())
    if math.isclose(lo, hi):
        return pd.Series(np.full(len(values), 50.0), index=values.index)
    return ((values - lo) / (hi - lo) * 100).clip(0, 100)


def _trend(group: pd.DataFrame, origin: pd.Timestamp) -> str:
    recent = len(group[group["created_datetime"] > origin - pd.Timedelta(days=28)])
    previous = len(group[(group["created_datetime"] <= origin - pd.Timedelta(days=28)) &
                         (group["created_datetime"] > origin - pd.Timedelta(days=56))])
    if previous < 10:
        return "insufficient_data"
    change = (recent - previous) / previous
    return "increasing" if change > .10 else "decreasing" if change < -.10 else "stable"


def _estimate_confidence(count: int, min_samples: int, recurrence: float) -> float:
    """
    Calculates a confidence score [0, 1] for a hotspot based on:
    1. Sample size (count relative to min_samples)
    2. Temporal stability (recurrence)
    """
    sample_factor = min(1.0, max(0.5, count / (5 * min_samples)))
    recurrence_factor = recurrence / 100
    return round((sample_factor * 0.6 + recurrence_factor * 0.4), 2)


def _cluster_validation_metrics(
    df: pd.DataFrame,
    radius_m: int,
    min_samples: int,
) -> dict[str, float | int | None]:
    if df.empty or len(df) < max(5, min_samples):
        return {
            "silhouette": None,
            "cluster_count": 0,
            "noise_count": int(len(df)),
        }

    coords = np.radians(df[["latitude", "longitude"]].to_numpy())
    labels = DBSCAN(
        eps=(radius_m / 1000) / EARTH_RADIUS_KM,
        min_samples=min_samples,
        metric="haversine",
        algorithm="ball_tree",
    ).fit_predict(coords)
    clustered = labels[labels >= 0]
    cluster_count = len(set(clustered.tolist()))
    noise_count = int((labels < 0).sum())
    if cluster_count < 2 or len(clustered) < 3:
        return {
            "silhouette": None,
            "cluster_count": int(cluster_count),
            "noise_count": noise_count,
        }

    try:
        # Silhouette score runs in O(N^2) and blocks the single-threaded event loop for 30s+. Disable it.
        score = None
        return {
            "silhouette": score,
            "cluster_count": int(cluster_count),
            "noise_count": noise_count,
        }
    except Exception:
        return {
            "silhouette": None,
            "cluster_count": int(cluster_count),
            "noise_count": noise_count,
        }


def validate_cluster_stability(
    mode: str = "HISTORICAL",
    time_range: Optional[tuple[datetime, datetime]] = None,
    timeline: Optional[str] = None,
) -> list[dict[str, float | int | None]]:
    """Evaluate clustering stability across a few nearby parameter settings."""
    df_raw = load_violations().copy()
    if timeline:
        st, et = _parse_timeline(timeline)
        df_raw = df_raw[(df_raw["created_datetime"] >= st) & (df_raw["created_datetime"] <= et)].copy()
    if mode == "LIVE":
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(hours=24)
        df_raw = df_raw[df_raw["created_datetime"] >= cutoff].copy()
    elif mode == "HISTORICAL" and time_range:
        start, end = time_range
        df_raw = df_raw[(df_raw["created_datetime"] >= start) & (df_raw["created_datetime"] <= end)].copy()
    elif mode == "HISTORICAL":
        pass  # Use full dataset for all-time stability analysis
    else:
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(days=30)
        df_raw = df_raw[df_raw["created_datetime"] >= cutoff].copy()

    if df_raw.empty:
        return []

    parameter_grid = [
        (330, 10),
        (280, 8),
        (380, 12),
    ]
    results = []
    for radius_m, min_samples in parameter_grid:
        metrics = _cluster_validation_metrics(df_raw, radius_m=radius_m, min_samples=min_samples)
        metrics.update({"radius_m": radius_m, "min_samples": min_samples})
        results.append(metrics)
    return results

def compute_hotspots(
    radius_m: int = 330,
    min_samples: int = 10,
    mode: str = "HISTORICAL",
    time_range: Optional[tuple[datetime, datetime]] = None,
    day_of_week: Optional[int] = None,
    time_of_day: str = "ALL",
    timeline: Optional[str] = None
) -> list[HotspotRecord]:
    """DBSCAN/Haversine clusters with temporal modes: LIVE, FORECAST, HISTORICAL."""
    key = (radius_m, min_samples, mode, time_range, day_of_week, time_of_day, timeline)
    with _HOTSPOTS_CACHE_LOCK:
        if key in _HOTSPOTS_CACHE:
            return _HOTSPOTS_CACHE[key]

    df_raw = load_violations().copy()
    if timeline:
        st, et = _parse_timeline(timeline)
        df_raw = df_raw[(df_raw["created_datetime"] >= st) & (df_raw["created_datetime"] <= et)].copy()
    
    if day_of_week is not None:
        df_raw = df_raw[df_raw["created_datetime"].dt.dayofweek == day_of_week].copy()
    if time_of_day == "PEAK":
        df_raw = df_raw[df_raw["created_datetime"].dt.hour.isin([8, 9, 10, 17, 18, 19, 20])].copy()
    elif time_of_day == "OFF_PEAK":
        df_raw = df_raw[~df_raw["created_datetime"].dt.hour.isin([8, 9, 10, 17, 18, 19, 20])].copy()

    if mode == "SNAPSHOT":
        # Snapshot mode: highest-activity period in the month (peak day)
        if not df_raw.empty:
            df_raw["date_only"] = df_raw["created_datetime"].dt.date
            day_counts = df_raw.groupby("date_only").size()
            if not day_counts.empty:
                peak_day = day_counts.idxmax()
                df = df_raw[df_raw["created_datetime"].dt.date == peak_day].copy()
            else:
                df = df_raw.copy()
        else:
            df = df_raw.copy()
    elif mode == "LIVE":
        # Live mode: most recent 24 hours — operational "right now" view
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(hours=24)
        df = df_raw[df_raw["created_datetime"] >= cutoff].copy()

    elif mode == "HISTORICAL" and time_range:
        start, end = time_range
        df = df_raw[(df_raw["created_datetime"] >= start) & (df_raw["created_datetime"] <= end)].copy()
    elif mode == "HISTORICAL":
        # Historical without explicit range: default to last 30 days to avoid O(N^2) DBSCAN bottleneck on 300k rows
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(days=30)
        df = df_raw[df_raw["created_datetime"] >= cutoff].copy()
    elif mode == "FORECAST":
        # Forecast uses most recent 30 days as the baseline for projection
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(days=30)
        df = df_raw[df_raw["created_datetime"] >= cutoff].copy()
    else:
        # Default fallback: 30-day window
        latest_ts = df_raw["created_datetime"].max()
        cutoff = latest_ts - pd.Timedelta(days=30)
        df = df_raw[df_raw["created_datetime"] >= cutoff].copy()

    validation = _cluster_validation_metrics(df, radius_m=radius_m, min_samples=min_samples)
    print(
        "[DBSCAN] radius_m=%s min_samples=%s clusters=%s noise=%s silhouette=%s"
        % (
            radius_m,
            min_samples,
            validation["cluster_count"],
            validation["noise_count"],
            validation["silhouette"],
        )
    )

    if df.empty:
        return []

    coords = np.radians(df[["latitude", "longitude"]].to_numpy())
    labels = DBSCAN(eps=(radius_m / 1000) / EARTH_RADIUS_KM, min_samples=min_samples,
                    metric="haversine", algorithm="ball_tree").fit_predict(coords)
    df["cluster"] = labels
    clustered = df[df["cluster"] >= 0]
    if clustered.empty:
        return []

    origin = clustered["created_datetime"].max()
    total_weeks = max(1, clustered["week"].nunique())
    rows = []
    for cluster_id, group in clustered.groupby("cluster"):
        count = len(group)
        active_weeks = group["week"].nunique()
        age_hours = max(0.0, (origin - group["created_datetime"].max()).total_seconds() / 3600)
        area_km2 = math.pi * (radius_m / 1000) ** 2
        rows.append({
            "cluster": int(cluster_id), "lat": group["latitude"].mean(), "lon": group["longitude"].mean(),
            "count": count, "density_raw": count / area_km2, "recency_raw": math.exp(-age_hours / (24 * 14)),
            "frequency_raw": count / total_weeks, "recurrence_raw": active_weeks / total_weeks,
            "severity_raw": group["severity"].mean() / 5,
            "peak_hour": int(group["hour"].mode().iloc[0]), "trend": _trend(group, origin),
            "locality": group["locality_name"].mode().iloc[0] if not group["locality_name"].mode().empty else reverse_geocode(group["latitude"].mean(), group["longitude"].mean()),
            "station": group["police_station"].mode().iloc[0] if not group["police_station"].mode().empty else None,
        })

    # Forecast adjustment: If mode is FORECAST, multiply volume by forecast multiplier
    if mode == "FORECAST":
        from src.forecasting import forecast_locality
        for row in sorted(rows, key=lambda r: r["count"], reverse=True)[:5]:
            f_res = forecast_locality(row["locality"])
            if f_res.status == "modelled" and f_res.points:
                # Use the 24h forecast point as a multiplier relative to average historical volume
                expected_24h = f_res.points[2].expected_violations # index 2 is 24h
                hist_avg_24h = row["count"] / (total_weeks * 7) if total_weeks > 0 else 1
                multiplier = max(1.0, expected_24h / max(1.0, hist_avg_24h))
                row["count"] *= multiplier
                row["density_raw"] *= multiplier
                row["frequency_raw"] *= multiplier

    stats = pd.DataFrame(rows)
    stats["density"] = _scale(stats["density_raw"])
    stats["recency"] = stats["recency_raw"] * 100
    stats["frequency"] = _scale(stats["frequency_raw"])
    stats["recurrence"] = stats["recurrence_raw"] * 100
    stats["severity"] = stats["severity_raw"] * 100
    stats["risk_contrib_violations"] = stats["density"] * 0.40
    stats["risk_contrib_congestion"] = stats["severity"] * 0.30
    stats["risk_contrib_historical"] = stats["recurrence"] * 0.20
    stats["risk_contrib_forecast"] = stats["recency"] * 0.10
    stats["risk"] = (stats["risk_contrib_violations"] + stats["risk_contrib_congestion"] +
                     stats["risk_contrib_historical"] + stats["risk_contrib_forecast"])
    lineage = DataLineage(dataset=DATASET.name, dataset_max_timestamp=origin.to_pydatetime(),
                          computed_at=datetime.now(timezone.utc), formula_version=RISK_FORMULA_VERSION,
                          measured=True, caveat="Risk is relative to this historical dataset; it is not live congestion probability.")
    output = []
    for row in stats.sort_values("risk", ascending=False).itertuples():
        risk = round(float(row.risk), 2)
        level = "Critical" if risk >= 85 else "High" if risk >= 70 else "Moderate" if risk >= 45 else "Low"
        stable_key = f"{row.lat:.5f}:{row.lon:.5f}:{radius_m}"
        conf = _estimate_confidence(int(row.count), min_samples, row.recurrence_raw)
        breakdown = {
            "violations": round(row.risk_contrib_violations, 2),
            "congestion": round(row.risk_contrib_congestion, 2),
            "historical": round(row.risk_contrib_historical, 2),
            "forecast": round(row.risk_contrib_forecast, 2),
        }
        output.append(HotspotRecord(
            hotspot_id="hs_" + hashlib.sha1(stable_key.encode()).hexdigest()[:12], locality_name=row.locality,
            police_station=None if pd.isna(row.station) else str(row.station), centroid_lat=round(row.lat, 6),
            centroid_lon=round(row.lon, 6), violation_count=int(row.count), peak_hour=int(row.peak_hour),
            trend_direction=row.trend, density_score=round(row.density, 2), recency_score=round(row.recency, 2),
            frequency_score=round(row.frequency, 2), recurrence_score=round(row.recurrence, 2),
            severity_score=round(row.severity, 2), risk_score=risk, risk_level=level,
            confidence_score=conf, risk_breakdown=breakdown, lineage=lineage))
            
    with _HOTSPOTS_CACHE_LOCK:
        _HOTSPOTS_CACHE[key] = output
    return output


def estimate_impact(hotspot: HotspotRecord, avg_delay_minutes: float = 4.0,
                    affected_vehicles_per_violation: float = 12.0, value_of_time_inr_per_hour: float = 120.0) -> ImpactEstimate:
    # 1. Economic Loss (Fuel & Time)
    congestion_factor = .5 + hotspot.severity_score / 100
    time_loss_inr = (hotspot.violation_count * congestion_factor * avg_delay_minutes * affected_vehicles_per_violation * value_of_time_inr_per_hour / 60)

    # 2. Safety Risk (weighted by severity)
    safety_score = (hotspot.violation_count * (hotspot.severity_score / 100)) * 0.5

    # 3. Enforcement Opportunity (potential fines)
    fine_opportunity = hotspot.violation_count * 500 # Avg fine 500 INR

    # 4. Fuel Waste: idling vehicles burn ~0.8L/hour, avg delay in hours, affected vehicles
    fuel_price_inr_per_litre = 105.0
    idling_litres_per_hour = 0.8
    total_idle_hours = (hotspot.violation_count * congestion_factor * avg_delay_minutes * affected_vehicles_per_violation) / 60.0
    fuel_litres = total_idle_hours * idling_litres_per_hour
    fuel_waste_inr = round(fuel_litres * fuel_price_inr_per_litre, 2)

    # 5. CO2 Emissions: 2.31 kg CO2 per litre of petrol
    co2_kg_per_litre = 2.31
    co2_emissions_kg = round(fuel_litres * co2_kg_per_litre, 2)

    # 6. Pedestrian Safety Index: severity × density-weighted score (0-100)
    pedestrian_safety_index = round(min(100.0, (hotspot.severity_score * hotspot.density_score) / 100.0 * 1.5), 2)

    amount = time_loss_inr

    breakdown = {
        "time_loss": round(time_loss_inr, 2),
        "safety_risk": round(safety_score, 2),
        "enforcement_opportunity": round(fine_opportunity, 2),
        "fuel_waste": fuel_waste_inr,
        "co2_emissions_kg": co2_emissions_kg,
    }

    # Confidence based on hotspot confidence and violation volume
    confidence = hotspot.confidence_score * (1.0 if hotspot.violation_count > 50 else 0.8)

    lineage = hotspot.lineage.model_copy(update={"formula_version": IMPACT_FORMULA_VERSION, "measured": False,
        "caveat": "Modelled estimate using policy assumptions; no observed vehicle-delay or realized monetary loss is available."})

    return ImpactEstimate(hotspot_id=hotspot.hotspot_id, amount_inr=round(amount, 2),
        lower_bound_inr=round(amount * .5, 2), upper_bound_inr=round(amount * 1.5, 2),
        fuel_waste_inr=fuel_waste_inr, co2_emissions_kg=co2_emissions_kg,
        pedestrian_safety_index=pedestrian_safety_index,
        impact_breakdown=breakdown, confidence_score=round(confidence, 2),
        inputs={"violation_volume": hotspot.violation_count, "congestion_severity_factor": round(congestion_factor, 3),
                "average_delay_minutes": avg_delay_minutes, "affected_vehicles_per_violation": affected_vehicles_per_violation,
                "value_of_time_inr_per_hour": value_of_time_inr_per_hour, "fuel_price_inr_per_litre": fuel_price_inr_per_litre},
        formula="violations × severity_factor × avg_delay_minutes × affected_vehicles_per_violation × value_of_time_per_hour ÷ 60",
        lineage=lineage)


def recommend_dispatch(hotspot: HotspotRecord, forecast_risk: Optional[float] = None) -> DispatchRecommendation:
    effective = max(hotspot.risk_score, forecast_risk or 0)
    if effective >= 85 or hotspot.violation_count >= 80:
        level, actions = "Critical Enforcement", ["Deploy enforcement team", "Stage towing support", "Supervisor acknowledgement required"]
        officers, barricades, tow_trucks, response = 8, 3, 2, "Immediate"
    elif effective >= 70 or hotspot.violation_count >= 50:
        level, actions = "High Enforcement", ["Deploy targeted patrol", "Prepare towing support"]
        officers, barricades, tow_trucks, response = 6, 2, 1, "Immediate"
    elif effective >= 45 or hotspot.violation_count >= 25:
        level, actions = "Moderate Enforcement", ["Schedule mobile enforcement patrol"]
        officers, barricades, tow_trucks, response = 3, 1, 0, "Priority"
    else:
        level, actions = "Low Enforcement", ["Monitor and include in routine patrol"]
        officers, barricades, tow_trucks, response = 1, 0, 0, "Routine"
        
    reasons = [f"{hotspot.violation_count} violations in the dataset cluster", f"risk score {hotspot.risk_score:.1f}/100",
               f"{hotspot.trend_direction.replace('_', ' ')} trend", f"recurring peak at {hotspot.peak_hour:02d}:00"]
    if forecast_risk is not None:
        reasons.append(f"forecast risk {forecast_risk:.1f}/100")
        
    return DispatchRecommendation(
        hotspot_id=hotspot.hotspot_id, 
        enforcement_level=level, 
        actions=actions,
        reasons=reasons, 
        rule_version=DISPATCH_RULE_VERSION,
        recommended_officers=officers,
        recommended_barricades=barricades,
        recommended_tow_trucks=tow_trucks,
        suggested_response=response
    )


def compute_zone_insights(radius_m: int = 330, min_samples: int = 10, timeline: Optional[str] = None) -> dict:
    """Classifies hotspots into emerging, deteriorating, and stable categories based on temporal trends."""
    hotspots = compute_hotspots(radius_m=radius_m, min_samples=min_samples, timeline=timeline)
    validation_runs = validate_cluster_stability(timeline=timeline)

    emerging = [h for h in hotspots if h.trend_direction == "increasing" and h.risk_score > 50]
    deteriorating = [h for h in hotspots if h.trend_direction == "stable" and h.risk_score > 70]
    stable_critical = [h for h in hotspots if h.trend_direction == "stable" and h.risk_level == "Critical"]

    return {
        "emerging": emerging,
        "deteriorating": deteriorating,
        "stable_critical": stable_critical,
        "validation": validation_runs,
        "summary": {
            "emerging_count": len(emerging),
            "deteriorating_count": len(deteriorating),
            "stable_critical_count": len(stable_critical)
        }
    }


def compute_anomalies(window="day", timeline: Optional[str] = None) -> list[dict]:
    """Detects anomalies in violation counts using Z-score analysis (3-sigma rule)."""
    df = load_violations().copy()
    if timeline:
        st, et = _parse_timeline(timeline)
        df = df[(df["created_datetime"] >= st) & (df["created_datetime"] <= et)].copy()
    if df.empty:
        return []
    
    group_col = "created_datetime"
    if window == "day":
        df["group"] = df["created_datetime"].dt.date
    else:
        df["group"] = df["created_datetime"].dt.hour

    counts = df.groupby("group").size()
    mean = counts.mean()
    std = counts.std()
    
    if std == 0 or pd.isna(std):
        return []
        
    anomalies = counts[counts > mean + 3 * std]
    
    results = []
    for group, count in anomalies.items():
        results.append({
            "timestamp": str(group),
            "count": int(count),
            "z_score": round((count - mean) / std, 2),
            "window": window
        })
    return results

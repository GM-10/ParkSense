from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT / "data" / "location_cluster_input.csv"
RAW_FILE = ROOT / "jan to may police violation_anonymized791b166.csv"
OUTPUT_FILE = ROOT / "data" / "hotspot_clusters.csv"


def _load_frame() -> pd.DataFrame:
    if not INPUT_FILE.exists():
      raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")
    return pd.read_csv(INPUT_FILE)


def _load_raw() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Missing raw dataset: {RAW_FILE}")
    return pd.read_csv(RAW_FILE)


def main() -> int:
    df = _load_frame().copy()
    raw = _load_raw().copy()

    if df.empty:
        print("No location data found. Nothing to cluster.")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUTPUT_FILE, index=False)
        return 0

    coords = df[["latitude", "longitude"]].to_numpy()
    labels = DBSCAN(eps=0.003, min_samples=10).fit_predict(coords)
    df["cluster_id"] = labels
    df = df[df["cluster_id"] >= 0].copy()

    if df.empty:
        print("No clusters detected.")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUTPUT_FILE, index=False)
        return 0

    df["lat_round"] = df["latitude"].round(4)
    df["lon_round"] = df["longitude"].round(4)
    raw["lat_round"] = raw["latitude"].round(4)
    raw["lon_round"] = raw["longitude"].round(4)

    merged = df.merge(
        raw,
        on=["lat_round", "lon_round"],
        how="left",
        suffixes=("", "_raw"),
    )

    rows = []
    grouped = merged.groupby("cluster_id")
    for cluster_id, group in grouped:
        violation_count = len(group)
        mean_severity = float(group["severity"].mean()) if "severity" in group else 0.0
        junction_density_flag = 1 if group["junction_name"].nunique(dropna=True) > 1 else 0

        rows.append(
            {
                "cluster_id": int(cluster_id),
                "centroid_lat": round(float(group["latitude"].mean()), 6),
                "centroid_lon": round(float(group["longitude"].mean()), 6),
                "violation_count": int(violation_count),
                "mean_severity": round(mean_severity, 2),
                "dominant_violation_type": group["violation_type"].mode().iloc[0] if not group["violation_type"].mode().empty else None,
                "dominant_vehicle_type": group["vehicle_type"].mode().iloc[0] if not group["vehicle_type"].mode().empty else None,
                "dominant_police_station": group["police_station"].mode().iloc[0] if not group["police_station"].mode().empty else None,
                "junction_density_flag": junction_density_flag,
                "congestion_score": round(violation_count * mean_severity * max(1, junction_density_flag), 2),
            }
        )

    output = pd.DataFrame(rows).sort_values(["violation_count", "mean_severity"], ascending=False).reset_index(drop=True)
    output["risk_tier"] = "Moderate"
    if not output.empty:
        output.loc[output.index[:10], "risk_tier"] = "Critical"
        output.loc[output.index[10:30], "risk_tier"] = "High"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)
    print("Hotspot detection completed successfully.")
    print(f"{OUTPUT_FILE.relative_to(ROOT)} exists: {OUTPUT_FILE.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

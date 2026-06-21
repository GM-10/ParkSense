import pandas as pd
import json
import os
import ast
import numpy as np

def load_data(file_path):
    return pd.read_csv(file_path)

def calculate_severity(row):
    # Need to handle potential JSON parsing
    try:
        violation_types = json.loads(row['violation_type'].replace("'", "\"")) if isinstance(row['violation_type'], str) else []
    except:
        violation_types = []

    severity_map = {
        'DOUBLE PARKING': 4,
        'PARKING ON FOOTPATH': 3,
        'PARKING IN A MAIN ROAD': 3,
        'WRONG PARKING': 2,
        'NO PARKING': 2
    }

    score = 0
    for v in violation_types:
        score += severity_map.get(v, 0)
    return score

def process_data(df):
    # 3. Filter
    df = df[df['validation_status'] == 'approved'].copy()

    # 2. Clean/Parse
    # Datetime
    df['created_datetime'] = pd.to_datetime(df['created_datetime'])
    df['hour'] = df['created_datetime'].dt.hour
    df['month'] = df['created_datetime'].dt.month
    df['day_of_week'] = df['created_datetime'].dt.day_name()

    # Severity
    df['severity_score'] = df.apply(calculate_severity, axis=1)

    # Junction flag
    df['is_junction_violation'] = df['junction_name'] != 'No Junction'

    return df

def aggregate_data(df):
    # Junction summary
    junction_summary = df.groupby('junction_name').agg(
        total_violations=('violation_type', 'count'),
        approved_violations=('validation_status', 'count'),
        dominant_vehicle=('vehicle_type', lambda x: x.mode()[0] if not x.mode().empty else None),
        dominant_violation=('violation_type', lambda x: x.mode()[0] if not x.mode().empty else None),
        mean_severity=('severity_score', 'mean'),
        peak_hour=('hour', lambda x: x.mode()[0] if not x.mode().empty else None),
        police_station=('police_station', lambda x: x.mode()[0] if not x.mode().empty else None),
        dominant_day_of_week=('day_of_week', lambda x: x.mode()[0] if not x.mode().empty else None)
    ).reset_index()

    # Normalize impact index (0-100) based on severity and volume
    max_sev = 4.0
    junction_summary['impact_index'] = (
        (junction_summary['mean_severity'] / max_sev) *
        np.log1p(junction_summary['total_violations']) * 10
    ).clip(0, 100).round(2)

    junction_summary.to_csv('data/junction_summary.csv', index=False)

    # Police station summary
    station_summary = df.groupby('police_station').agg(
        total_violations=('violation_type', 'count'),
        top_junction=('junction_name', lambda x: x.mode()[0] if not x.mode().empty else None),
        dominant_vehicle=('vehicle_type', lambda x: x.mode()[0] if not x.mode().empty else None),
        mean_severity=('severity_score', 'mean'),
        monthly_trend=('month', lambda x: json.dumps(x.value_counts().to_dict())),
        dominant_day_of_week=('day_of_week', lambda x: x.mode()[0] if not x.mode().empty else None)
    ).reset_index()

    # Normalize station burden
    station_summary['burden_index'] = (
        (station_summary['mean_severity'] / max_sev) *
        np.log1p(station_summary['total_violations']) * 10
    ).clip(0, 100).round(2)

    os.makedirs('data', exist_ok=True)
    station_summary.to_csv('data/police_station_summary.csv', index=False)

    # Location cluster
    location_cluster = df[['latitude', 'longitude', 'severity_score']]
    location_cluster.to_csv('data/location_cluster_input.csv', index=False)

if __name__ == "__main__":
    DATA_FILE = 'jan to may police violation_anonymized791b166.csv'
    if not os.path.exists(DATA_FILE):
        print(f"Error: Raw data file {DATA_FILE} not found in current directory.")
        sys.exit(1)
    
    df = load_data(DATA_FILE)
    df = process_data(df)
    aggregate_data(df)
    print("Pipeline completed successfully.")
    for f in ['data/junction_summary.csv', 'data/police_station_summary.csv', 'data/location_cluster_input.csv']:
        print(f"{f} exists: {os.path.exists(f)}")

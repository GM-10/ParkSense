import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import requests
import os
from dotenv import load_dotenv

load_dotenv()
MAPPLS_API_KEY = os.getenv('MAPPLS_API_KEY')

def get_locality(lat, lon):
    if not MAPPLS_API_KEY or MAPPLS_API_KEY == 'YOUR_KEY_HERE':
        return "Unknown"
    url = f"https://apis.mappls.com/advancedmaps/v1/{MAPPLS_API_KEY}/rev_geocode?lat={lat}&lng={lon}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if 'results' in data and len(data['results']) > 0:
            return data['results'][0].get('formatted_address', 'Unknown')
    except Exception as e:
        print(f"Error fetching locality for {lat}, {lon}: {e}")
    return "Unknown"

def detect_hotspots():
    # Load input
    df_clusters = pd.read_csv('data/location_cluster_input.csv')

    # DBSCAN with Haversine (requires radians)
    coords = df_clusters[['latitude', 'longitude']].values
    rad_coords = np.radians(coords)

    # eps = distance in radians. 0.003 deg approx 330m.
    # 330 / 6371 (earth radius km) approx 0.000052
    db = DBSCAN(eps=0.000052, min_samples=10, metric='haversine').fit(rad_coords)
    df_clusters['cluster'] = db.labels_
    
    # Filter noise
    hotspots = df_clusters[df_clusters['cluster'] != -1].copy()

    # Aggregate cluster metadata
    cluster_stats = hotspots.groupby('cluster').agg(
        centroid_lat=('latitude', 'mean'),
        centroid_lon=('longitude', 'mean'),
        violation_count=('latitude', 'count'),
        mean_severity=('severity_score', 'mean')
    )
    
    # Add locality
    cluster_stats['locality_name'] = cluster_stats.apply(
        lambda row: get_locality(row['centroid_lat'], row['centroid_lon']), axis=1
    )
    
    # Add congestion score
    cluster_stats['congestion_score'] = cluster_stats['violation_count'] * cluster_stats['mean_severity']
    
    # Rank and Assign Tiers
    cluster_stats = cluster_stats.sort_values('congestion_score', ascending=False)
    cluster_stats['risk_tier'] = 'Moderate'
    cluster_stats.iloc[:10, cluster_stats.columns.get_loc('risk_tier')] = 'Critical'
    cluster_stats.iloc[10:30, cluster_stats.columns.get_loc('risk_tier')] = 'High'
    
    cluster_stats.to_csv('data/hotspot_clusters.csv')
    print("Hotspot detection complete. Saved to data/hotspot_clusters.csv")

def calculate_intervention_impact(current_score, units, efficiency_factor=0.05):
    """Models congestion reduction based on patrol units."""
    return current_score / (1 + (units * efficiency_factor))

if __name__ == "__main__":
    detect_hotspots()

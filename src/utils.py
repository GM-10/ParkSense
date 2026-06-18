import os

# Paths
DATA_PATH = "data/incidents.csv"
JUNCTION_RISK_PATH = "data/junction_risk.csv"
CORRIDOR_RISK_PATH = "data/corridor_risk.csv"
HOTSPOT_PATH = "data/hotspots.csv"

# Risk Scoring Weights
PRIORITY_WEIGHTS = {
    "High": 2,
    "Low": 1
}

ROAD_CLOSURE_WEIGHTS = {
    "TRUE": 2,
    "FALSE": 1
}

CAUSE_SEVERITY = {
    "accident": 3,
    "congestion": 3,
    "vehicle_breakdown": 2,
    "others": 1
}

# Default value if not found in mapping
DEFAULT_WEIGHT = 1

# Economic Impact Constants (Bengaluru-specific)
AVG_HOURLY_WAGE_INR = 450  # Average productivity value per person per hour
AVG_VEHICLE_OCCUPANCY = 1.6 
VOL_HIGH_PRIORITY = 800    # Vehicles affected per hour on high-priority routes
VOL_LOW_PRIORITY = 200     # Vehicles affected per hour on low-priority routes

# Delay Estimates (Hours)
DELAY_ESTIMATES = {
    "accident": 1.2,
    "congestion": 0.8,
    "vehicle_breakdown": 0.5,
    "others": 0.3
}

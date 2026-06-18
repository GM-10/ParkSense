# ParkSense Data Pipeline Design

## Architecture
- **Input:** Reads CSV from root directory.
- **Processing:** Uses `pandas` to filter approved violations, parse JSON, calculate severity scores, and extract temporal features.
- **Aggregation:**
  - `junction_summary`: Group by `junction_name` (aggregated metrics).
  - `police_station_summary`: Group by `police_station` (aggregated metrics + monthly trend).
  - `location_cluster_input`: Flattened records for clustering (`latitude`, `longitude`, `severity_score`).
- **Output:** Writes to `data/` directory.

## Components
- `load_data()`: Reads the raw CSV.
- `clean_and_parse()`: Handles JSON, datetime, and severity calculation.
- `aggregate_data()`: Generates the 3 summary files.
- `verify_outputs()`: Validates file existence.

## Error Handling
- Basic validation: filter non-approved.
- JSON parsing: Assume well-formed lists in strings.

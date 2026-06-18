# Dashboard Design Specification

## Overview
A tactical, high-contrast dashboard for parking violation analysis and enforcement dispatch, designed for Bengaluru police.

## Architecture
- **Framework**: Streamlit (Python-based dashboard).
- **Data**: Pre-processed CSVs (`data/junction_summary.csv`, `hotspot_clusters.csv`, `location_cluster_input.csv`).
- **Visualization**: Folium (Maps), Plotly (Charts).

## Layout (Tabs)
### Tab 1: Hotspot Intelligence Map
- **Components**: Folium map, heatmap layer, categorized markers (Red/Orange/Yellow), sidebar filters (station/vehicle/violation), ranked statistics tables.

### Tab 2: Temporal Analysis
- **Charts**: Hourly bar chart, MoM trend lines, vehicle breakdown pie chart.
- **Highlights**: Peak enforcement window.

### Tab 3: AI Enforcement Briefing
- **UI**: Chat interface for tactical queries using a mock or simple LLM interface.

## Aesthetic
- Tactical "War Room" theme: dark mode, high-contrast colors (red/orange/yellow on dark background).
- Standardized UI components (minimalist cards, clear typography).

## Data Flow
1. Load data via Pandas.
2. Filter based on sidebar inputs.
3. Render maps and charts dynamically.

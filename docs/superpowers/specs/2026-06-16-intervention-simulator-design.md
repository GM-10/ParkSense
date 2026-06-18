# Design: Digital Twin Intervention Simulator

## Overview
This design introduces a simulation feature ("What-If" Analysis) to the ParkSense dashboard, allowing users to model the impact of deploying patrol units on congestion hotspots.

## Architecture Changes
1. **Simulation Logic:** Create a new function in `src/hotspot.py` (or a new module) to model the reduction of `congestion_score` based on `patrol_units`.
   - Formula: `predicted_congestion_score = current_congestion_score / (1 + (patrol_units * efficiency_factor))`
2. **Dashboard Integration (`app.py`):**
   - Add a sidebar in the "Hotspot Intelligence Map" tab with numerical inputs for patrol units per junction (for critical hotspots only).
   - Dynamically recalculate and update the map markers when inputs change.

## Components
- `src/hotspot.py`: Add `calculate_intervention_impact(current_score, units)`.
- `app.py`: Add Sidebar input fields and UI state management for simulation.

## Trade-offs
- **Pros:** Empowers police with prescriptive insights (actionable interventions).
- **Cons:** Dependent on an assumed `efficiency_factor` which will need empirical tuning.

## Security
- No new credentials required. Input validation on patrol unit numbers to prevent negative inputs.

# Digital Twin Intervention Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a "What-If" simulator in the dashboard to model the impact of patrol units on congestion hotspots.

**Architecture:** Add impact calculation logic in `src/hotspot.py` and integrate sidebar inputs into `app.py` to dynamically update the map markers.

**Tech Stack:** `pandas`, `streamlit`.

---

### Task 1: Implement Impact Calculation Logic

**Files:**
- Modify: `src/hotspot.py`

- [ ] **Step 1: Add impact function**
Add the following function to `src/hotspot.py`:
```python
def calculate_intervention_impact(current_score, units, efficiency_factor=0.05):
    """Models congestion reduction based on patrol units."""
    return current_score / (1 + (units * efficiency_factor))
```

- [ ] **Step 2: Commit**
```bash
git add src/hotspot.py
git commit -m "feat: add intervention impact calculation"
```

---

### Task 2: Integrate Simulator into Dashboard

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update Dashboard UI**
In `app.py` (Tab 1), import the new function and add `st.sidebar` number inputs for critical hotspots.

```python
from src.hotspot import calculate_intervention_impact

# ... inside tab1 ...
st.sidebar.subheader("Intervention Simulator")
simulated_scores = {}
for idx, row in filtered_hotspots[filtered_hotspots['risk_tier'] == 'Critical'].iterrows():
    units = st.sidebar.number_input(f"Patrol Units for Hotspot {idx}", min_value=0, value=0)
    simulated_scores[idx] = calculate_intervention_impact(row['congestion_score'], units)
```

- [ ] **Step 2: Update map markers**
Modify the Folium marker loop to use `simulated_scores[idx]` if available for the popup and risk tier recalculation.

- [ ] **Step 3: Verify and Commit**
Run `streamlit run app.py`, interact with sidebar, verify map markers update dynamically.
```bash
git add app.py
git commit -m "feat: integrate intervention simulator into dashboard"
```

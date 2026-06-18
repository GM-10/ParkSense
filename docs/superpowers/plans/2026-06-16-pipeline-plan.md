# ParkSense Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the data pipeline to process police violation data and generate summary CSVs.

**Architecture:** Use pandas for data manipulation and aggregation. Save output to `data/`.

**Tech Stack:** pandas, json, os

---

### Task 1: Setup data directory

- [ ] Ensure `data/` exists.

### Task 2: Implement `src/pipeline.py`

**Files:**
- Create: `src/pipeline.py`

- [ ] **Step 1: Write `src/pipeline.py` skeleton and data loading.**

```python
import pandas as pd
import json
import os

def load_data(file_path):
    return pd.read_csv(file_path)

if __name__ == "__main__":
    df = load_data('jan to may police violation_anonymized791b166.csv')
    print(df.head())
```

### Task 3: Implement cleaning and processing

- [ ] **Step 1: Add cleaning logic** (JSON parsing, datetime extraction, severity calculation).

### Task 4: Implement aggregation logic

- [ ] **Step 1: Create `junction_summary.csv`**
- [ ] **Step 2: Create `police_station_summary.csv`**
- [ ] **Step 3: Create `location_cluster_input.csv`**

### Task 5: Verify and Commit

- [ ] Run the script and verify `data/` outputs exist.
- [ ] Commit changes.

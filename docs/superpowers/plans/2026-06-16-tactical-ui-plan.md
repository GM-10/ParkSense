# Tactical Command Center UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the dashboard into a dark-themed, high-contrast "Tactical Command Center."

**Architecture:** Force Streamlit dark theme, inject custom CSS for high-contrast colors, and adjust Plotly/Folium aesthetics.

**Tech Stack:** Streamlit, CSS, Plotly.

---

### Task 1: Streamlit Theme Configuration

**Files:**
- Create: `.streamlit/config.toml`

- [ ] **Step 1: Configure theme**
Create `.streamlit/config.toml` and set the following:
```toml
[theme]
base = "dark"
primaryColor = "#00FF41" # Tactical Green
backgroundColor = "#000000"
secondaryBackgroundColor = "#1A1A1A"
textColor = "#FFFFFF"
font = "sans serif"
```

- [ ] **Step 2: Commit**
```bash
git add .streamlit/config.toml
git commit -m "chore: set streamlit dark theme"
```

---

### Task 2: Custom CSS Injection

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add Custom CSS**
Inject CSS to tighten layouts and enhance contrast. Add this to `app.py`:
```python
st.markdown("""
<style>
    .stApp { background-color: #000000; }
    .stMetric { background-color: #1A1A1A; border: 1px solid #00FF41; padding: 10px; }
    /* Add more specific selectors to improve contrast */
</style>
""", unsafe_allow_html=True)
```

- [ ] **Step 2: Verify and Commit**
Run dashboard to verify theme and contrast.
```bash
git add app.py
git commit -m "feat: add custom high-contrast CSS"
```

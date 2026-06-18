# Officer Feedback Mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feedback mechanism in the dashboard to allow officers to validate AI recommendations.

**Architecture:** Inject feedback buttons below AI responses and log validation data to a CSV.

**Tech Stack:** `streamlit`, `pandas`.

---

### Task 1: Implement Feedback UI and Logging

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Create Feedback Logger**
Implement a helper function in `app.py` to append feedback to `data/feedback_log.csv`.
```python
def log_feedback(user_prompt, agent_response, feedback):
    import csv
    with open('data/feedback_log.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([pd.Timestamp.now(), user_prompt, agent_response, feedback])
```

- [ ] **Step 2: Add Feedback Buttons**
Inside Tab 3 (`app.py`), after displaying the AI response, add columns for "Validate" and "Flag" buttons. If clicked, trigger `log_feedback`.

```python
# Inside the assistant message display loop:
col1, col2 = st.columns(2)
if col1.button("✅ Validate", key=f"val_{i}"):
    log_feedback(prompt, response, "validated")
    st.success("Feedback recorded!")
if col2.button("❌ Flag", key=f"flag_{i}"):
    log_feedback(prompt, response, "flagged")
    st.warning("Feedback recorded!")
```

- [ ] **Step 3: Verify and Commit**
Run dashboard, test feedback interaction, ensure `data/feedback_log.csv` is updated.
```bash
git add app.py
git commit -m "feat: implement officer feedback mechanism"
```

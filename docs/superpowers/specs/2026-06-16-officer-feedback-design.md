# Design: Officer-In-The-Loop Feedback Mechanism

## Overview
This design implements a feedback mechanism in the chat agent interface, allowing officers to validate the AI's recommendations. This data is critical for refining the model and ensuring the system remains aligned with field reality.

## Architecture Changes
1. **Dashboard UI (`app.py`):** Add feedback buttons (e.g., `st.button` for "Validate" and "Flag") under each AI response in the chat interface.
2. **Data Logging:** When feedback is submitted, append the interaction (User Prompt, Agent Response, Feedback) to `data/feedback_log.csv`.

## Components
- `app.py`: UI integration.
- `data/feedback_log.csv`: New file to store interaction feedback.

## Security
- None. This is a local logging feature.

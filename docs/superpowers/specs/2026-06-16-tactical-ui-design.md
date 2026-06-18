# Design: Tactical Command Center UI Overhaul

## Overview
This design outlines the transition of the ParkSense dashboard from a standard UI to a "Tactical Command Center" aesthetic, featuring a dark-themed, high-contrast interface designed for rapid situational awareness, as required by the project's urban mobility mandates.

## Aesthetic Requirements
- **Theme:** Dark mode (deep charcoal/black background).
- **Color Palette:** High-contrast, tactical colors (e.g., neon green for safe, amber for warning, red for critical).
- **Typography:** Monospaced or clean sans-serif for readability.
- **Layout:** Compact, high-information density components.

## Implementation Plan
1. **Streamlit Config:** Configure `.streamlit/config.toml` to force dark theme and set accent colors.
2. **Custom CSS:** Use `st.markdown("<style>...</style>", unsafe_allow_html=True)` to inject CSS for custom background colors, card styling, and high-contrast text.
3. **Component Tuning:** Adjust Plotly charts and Folium map styles to match the new dark-themed aesthetic.

## Security
- None. This is a purely visual/CSS change.

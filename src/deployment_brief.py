import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def add_deployment_brief_page(hotspots, junctions, stations, raw_df):
    st.markdown('<h1 style="text-align:center; color:white;">📋 Tomorrow\'s Deployment Brief</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:#9ca3af;">Auto-generated tactical deployment plan based on current congestion hotspots.</p>', unsafe_allow_html=True)

    # 1. Top 5 Hotspots by Congestion Score
    top_5 = hotspots.sort_values('congestion_score', ascending=False).head(5)

    cards_container = st.container()

    total_units = 0
    tier_counts = {'Critical': 0, 'High': 0, 'Moderate': 0}

    with cards_container:
        for _, row in top_5.iterrows():
            tier = row['risk_tier']
            locality = row['locality_name']
            score = row['congestion_score']

            # Unit Logic - Adaptive Scaling based on congestion score (Tier 1 Suggestion)
            units = int(np.ceil(score / 15000))
            units = max(1, min(units, 5))
            total_units += units
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

            # Color Logic
            color = '#ef4444' if tier == 'Critical' else '#f97316' if tier == 'High' else '#eab308'

            # Find Peak Window from junction_summary (best match by name or general)
            match = junctions[junctions['junction_name'].str.contains(locality, case=False, na=False)]
            if not match.empty:
                peak_h = int(match.iloc[0]['peak_hour'])

                # Proper Time Formatting (Fixes Critical Bug)
                start_t = (datetime.strptime(f"{max(0, peak_h-2)}:00", "%H:%M")).strftime("%I:%M %p")
                end_t = (datetime.strptime(f"{min(23, peak_h+2)}:00", "%H:%M")).strftime("%I:%M %p")
                window = f"{start_t} – {end_t}"
                violation = match.iloc[0]['dominant_violation']
                station = match.iloc[0]['police_station']
            else:
                window = "09:00 AM – 12:00 PM (Estimated)"
                violation = "General Parking"
                station = "Local Station"

            st.markdown(f"""
            <div style="background: #111827; border: 2px solid {color}; border-radius: 10px; padding: 20px; margin-bottom: 20px; color: white; font-family: 'Inter', sans-serif;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1f2937; padding-bottom: 10px; margin-bottom: 15px;">
                    <span style="font-weight: bold; font-size: 1.2rem; color: {color};">
                        🔴 {tier.upper()} — {locality}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.95rem;">
                    <div><b>👮 Deploy:</b> {units} units</div>
                    <div><b>⏰ Peak Window:</b> {window}</div>
                    <div><b>📌 Violation:</b> {violation}</div>
                    <div><b>🏢 Station:</b> {station}</div>
                </div>
                <div style="margin-top: 15px; text-align: right; color: #9ca3af; font-size: 0.8rem;">
                    <b>📊 Impact Index:</b> {score:.1f}/100
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Summary Bar
    st.markdown("---")
    # Estimated preventable violations = count * (mean_severity / 5) as a proxy for impact
    preventable = int(top_5['violation_count'].sum() * (top_5['mean_severity'].mean() / 5))

    st.markdown(f"""
    <div style="background: #1f293 own-fC: #1f2937; padding: 15px; border-radius: 8px; text-align: center; color: white; border: 1px solid #3b82f6;">
        <b>Tomorrow:</b> {tier_counts['Critical']} Critical zones | {tier_counts['High']} High zones |
        <b>Total units recommended:</b> {total_units} |
        <b>Estimated violations preventable:</b> ~{preventable}
    </div>
    """, unsafe_allow_html=True)

    # Export Button
    brief_df = top_5[['locality_name', 'risk_tier', 'congestion_score', 'violation_count']]
    st.download_button("Export Brief as CSV", brief_df.to_csv(index=False), "deployment_brief.csv", "text/csv")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
import requests
import os
from datetime import datetime

# --- API CONFIG ---
API_BASE_URL = "http://localhost:8000"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="ParkGuard | Tactical Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_streamlit_state=None
)

# --- CUSTOM CSS INJECTION ---
def inject_custom_css():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"], .st-emotion-cache-1oaH7B {{
            background-color: #0a0e1a !important;
            font-family: 'Inter', sans-serif !important;
            color: #ffffff !important;
        }}

        [data-testid="stSidebar"] {{
            background-color: #05070f !important;
            border-right: 1px solid #1f2937;
        }}

        .metric-card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-left: 5px solid #3b82f6;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .metric-card:hover {{
            border-color: #3b82f6;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
            transform: translateY(-2px);
        }}
        .metric-label {{
            color: #9ca3af;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .metric-value {{
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 700;
        }}

        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-critical {{ background: #ef4444; color: white; }}
        .badge-high {{ background: #f97316; color: white; }}
        .badge-moderate {{ background: #eab308; color: black; }}
        .badge-safe {{ background: #22c55e; color: white; }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: #0a0e1a; }}
        ::-webkit-scrollbar-thumb {{ background: #1f2937; border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #3b82f6; }}

        .custom-table {{
            width: 100%;
            border-collapse: collapse;
            color: white;
            background: #111827;
        }}
        .custom-table th {{
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #1f2937;
            color: #9ca3af;
        }}
        .custom-table td {{
            padding: 12px;
            border-bottom: 1px solid #1f2937;
        }}

        .header-gradient {{
            background: linear-gradient(90deg, #0a0e1a, #1e293b, #0a0e1a);
            background-size: 200% 100%;
            animation: gradient 5s ease infinite;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
        }}
        @keyframes gradient {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
    </style>
    """, unsafe_allow_html=True)

# --- API DATA WRAPPERS ---
@st.cache_data(ttl=600)
def fetch_api_data(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}")
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except Exception as e:
        st.error(f"API Connection Error ({endpoint}): {e}")
        return pd.DataFrame()

def query_ai_agent(question):
    try:
        response = requests.post(
            f"{API_BASE_URL}/agent/query",
            json={"question": question}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"answer": f"AI Engine Offline: {str(e)}", "confidence": "Error", "sources": []}

def trigger_pipeline_refresh():
    try:
        response = requests.post(f"{API_BASE_URL}/pipeline/refresh")
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Pipeline Refresh Failed: {e}")
        return False

# --- HELPERS ---
def render_metric(label, value, color="#3b82f6"):
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {color}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def get_tier_color(tier):
    mapping = {'Critical': '#ef4444', 'High': '#f97316', 'Moderate': '#eab308', 'Safe': '#22c55e'}
    return mapping.get(tier, '#3b82f6')

# --- NAVIGATION ---
st.sidebar.markdown('<h1 style="color:#ef4444; text-align:center;">PARKGUARD</h1>', unsafe_allow_html=True)
st.sidebar.markdown('<p style="text-align:center; color:#9ca3af; font-size:0.8rem;">Civic Intelligence System</p>', unsafe_allow_html=True)
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigation", [
    "Command Center",
    "Time Intelligence",
    "Deployment Brief",
    "Station Workload",
    "AI Tactical Agent",
    "ℹ️ Architecture"
])

# Data Fetching
hotspots = fetch_api_data("data/hotspots")
junctions = fetch_api_data("data/junctions")
stations = fetch_api_data("data/stations")

# Sidebar Filters
st.sidebar.markdown("### Tactical Filters")
selected_tiers = st.sidebar.multiselect("Risk Tier", hotspots['risk_tier'].unique() if not hotspots.empty else [], default=hotspots['risk_tier'].unique() if not hotspots.empty else [])
selected_station = st.sidebar.multiselect("Police Station", stations['police_station'].unique() if not stations.empty else [], default=stations['police_station'].unique() if not stations.empty else [])

if st.sidebar.button("🔄 Refresh All Data"):
    if trigger_pipeline_refresh():
        st.cache_data.clear()
        st.success("Data Pipeline refreshed!")

# Filter Logic
filtered_hotspots = hotspots[hotspots['risk_tier'].isin(selected_tiers)] if not hotspots.empty else pd.DataFrame()
filtered_stations = stations[stations['police_station'].isin(selected_station)] if not stations.empty else pd.DataFrame()

# --- PAGE 1: COMMAND CENTER ---
if page == "Command Center":
    inject_custom_css()

    st.markdown(f"""
    <div class="header-gradient">
        <h1 style="color: white; margin: 0; font-weight: 700; letter-spacing: 2px;">COMMAND CENTER</h1>
        <p style="color: #9ca3af; margin: 0; font-size: 0.9rem;">Real-time Bengaluru Parking Intelligence | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

    # KPI Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        # Note: Total violations would be a separate API call in full production
        render_metric("Total Violations", "298,450", "#3b82f6")
    with col2:
        crit_count = len(hotspots[hotspots['risk_tier'] == 'Critical']) if not hotspots.empty else 0
        render_metric("Critical Hotspots", str(crit_count), "#ef4444")
    with col3:
        top_zone = hotspots.sort_values('congestion_score', ascending=False).iloc[0]['locality_name'] if not hotspots.empty else "N/A"
        render_metric("Highest Congestion", top_zone, "#f97316")
    with col4:
        render_metric("Peak Window", "10:00 AM", "#eab308")

    # Main Content
    left_col, right_col = st.columns([0.6, 0.4])

    with left_col:
        st.subheader("Tactical Deployment Map")
        m = folium.Map(location=[12.9716, 77.5946], zoom_start=12, tiles='CartoDB dark_matter')
        marker_cluster = MarkerCluster().add_to(m)

        for _, row in filtered_hotspots.iterrows():
            folium.CircleMarker(
                location=[row['centroid_lat'], row['centroid_lon']],
                radius=max(5, row['congestion_score'] / 1000),
                color=get_tier_color(row['risk_tier']),
                fill=True,
                fill_color=get_tier_color(row['risk_tier']),
                fill_opacity=0.7,
                popup=f"<b>Zone:</b> {row['locality_name']}<br><b>Tier:</b> {row['risk_tier']}<br><b>Score:</b> {row['congestion_score']:.1f}"
            ).add_to(marker_cluster)
        st.plotly_chart(st_folium(m, width=800, height=600), use_container_width=True)

    with right_col:
        st.subheader("Top Hotspots")
        top_5 = hotspots.sort_values('congestion_score', ascending=False).head(5) if not hotspots.empty else pd.DataFrame()

        html_table = '<table class="custom-table">'
        html_table += '<tr><th>Zone</th><th>Tier</th><th>Score</th></tr>'
        for _, row in top_5.iterrows():
            badge_class = f"badge-{row['risk_tier'].lower()}"
            html_table += f'<tr><td>{row["locality_name"]}</td><td><span class="badge {badge_class}">{row["risk_tier"]}</span></td><td>{row["congestion_score"]:.1f}</td></tr>'
        html_table += '</table>'
        st.markdown(html_table, unsafe_allow_html=True)

# --- PAGE 2: TIME INTELLIGENCE ---
elif page == "Time Intelligence":
    inject_custom_css()
    st.markdown('<h1 style="text-align:center; color:white;">When Does Bengaluru Choke?</h1>', unsafe_allow_html=True)
    st.info("Temporal analysis is currently processed on the backend for performance.")
    # In a full production version, these would be API calls returning Plotly JSON
    st.markdown("*(Visuals are being migrated to API endpoints)*")

# --- PAGE 3: DEPLOYMENT BRIEF ---
elif page == "Deployment Brief":
    inject_custom_css()
    from src.deployment_brief import add_deployment_brief_page
    # Note: We pass the API-fetched dataframes to the existing logic
    # We need the raw_df for the summary calculation, so we fetch it here.
    raw_df_api = pd.read_csv("jan to may police violation_anonymized791b166.csv")
    add_deployment_brief_page(hotspots, junctions, stations, raw_df_api)

# --- PAGE 4: STATION WORKLOAD ---
elif page == "Station Workload":
    inject_custom_css()
    st.markdown('<h1 style="text-align:center; color:white;">Which Stations Are Overwhelmed?</h1>', unsafe_allow_html=True)
    if not stations.empty:
        workload = stations.sort_values('total_violations', ascending=True)
        fig_workload = px.bar(workload, x='total_violations', y='police_station', orientation='h',
                              title="Hotspot Burden by Station", color_discrete_sequence=['#3b82f6'])
        fig_workload.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_workload, use_container_width=True)

# --- PAGE 5: AI TACTICAL AGENT ---
elif page == "AI Tactical Agent":
    inject_custom_css()
    st.markdown('<h1 style="text-align:center; color:white;">AI Tactical Briefing Agent</h1>', unsafe_allow_html=True)

    demo_qs = [
        "Which junction needs the most urgent patrol this Saturday morning?",
        "Which police station is most overburdened relative to its coverage area?",
        "What is the violation trend at the most critical hotspot over the last 3 months?",
        "ಯಾವ ಜಂಕ್ಷನ್‌ನಲ್ಲಿ ಹೆಚ್ಚು ಉಲ್ಲಂಘನೆಗಳು ನಡೆಯುತ್ತಿವೆ?"
    ]

    st.markdown("### Example Tactical Queries")
    cols = st.columns(2)
    for i, q in enumerate(demo_qs):
        with cols[i % 2]:
            if st.button(q, key=f"demo_{i}"):
                st.session_state.query = q

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "confidence" in message:
                st.caption(f"Confidence: {message['confidence']}")

    if "query" in st.session_state:
        prompt = st.session_state.query
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Querying Tactical API..."):
            res = query_ai_agent(prompt)
            full_response = f"{res['confidence']}\n\n{res['answer']}"
            st.chat_message("assistant").markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": res['answer'], "confidence": res['confidence']})
        del st.session_state.query

    if prompt := st.chat_input("What tactical advice do you need?"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Querying Tactical API..."):
            res = query_ai_agent(prompt)
            full_response = f"{res['confidence']}\n\n{res['answer']}"
            st.chat_message("assistant").markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": res['answer'], "confidence": res['confidence']})
        st.rerun()

# --- PAGE 6: ARCHITECTURE ---
elif page == "ℹ️ Architecture":
    inject_custom_css()
    from src.architecture import add_architecture_page
    add_architecture_page()

import plotly.graph_objects as go
import streamlit as st

def add_architecture_page():
    st.markdown('<h1 style="text-align:center; color:white;">ℹ️ System Architecture</h1>', unsafe_allow_html=True)

    # Define Nodes and Coordinates
    nodes = {
        "Raw CSV": (0, 0),
        "Pipeline": (1, 0),
        "Summaries": (2, 0),
        "DBSCAN": (3, 0),
        "ChromaDB": (4, 0),
        "RAG Agent": (5, 0),
        "Dashboard": (6, 0)
    }

    # Define Edges
    edges = [
        ("Raw CSV", "Pipeline"),
        ("Pipeline", "Summaries"),
        ("Summaries", "DBSCAN"),
        ("DBSCAN", "ChromaDB"),
        ("ChromaDB", "RAG Agent"),
        ("RAG Agent", "Dashboard")
    ]

    # Build Plotly Figure
    edge_x = []
    edge_y = []
    for start, end in edges:
        x0, y0 = nodes[start]
        x1, y1 = nodes[end]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    node_x = [nodes[node][0] for node in nodes]
    node_y = [nodes[node][1] for node in nodes]
    node_text = list(nodes.keys())

    fig = go.Figure()

    # Edges
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='#3b82f6'),
        hoverinfo='none', mode='lines'
    ))

    # Nodes
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=25, color='#ef4444', line_width=2),
        text=node_text,
        textposition="bottom center",
        showlegend=False
    ))

    fig.update_layout(
        title="ParkGuard Data Flow Diagram",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        margin=dict(l=20, r=20, t=40, b=20),
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div style="background: #111827; padding: 20px; border-radius: 10px; border: 1px solid #1f2937; color: white; margin-top: 20px;">
        <h3 style="color: #3b82f6;">Why this architecture?</h3>
        <p>ParkGuard utilizes a <b>multi-stage transformation pipeline</b> to turn unstructured violation logs into tactical intelligence:</p>
        <ul>
            <li><b>DBSCAN Clustering:</b> Identifies high-density violation pockets without needing predefined boundaries.</li>
            <li><b>Weighted Severity:</b> Quantifies impact by prioritizing a "Main Road" violation over a "No Parking" sign.</li>
            <li><b>Hybrid RAG:</b> Combines structural summaries with a Large Language Model to provide operational briefings in both English and Kannada.</li>
            <li><b>Edge-First Visualization:</b> The dashboard translates complex spatial clusters into simple risk tiers (Critical, High, Moderate) for immediate action.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

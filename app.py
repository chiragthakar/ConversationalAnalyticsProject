"""
Streamlit Web Application: Conversational Analytics Agent with Knowledge Catalog & BQGraph.
Connected to Live GCP Project: conversationalanalytics-507815
"""

import os
import json
import streamlit as st
import pandas as pd
from src.agent import ConversationalAnalyticsAgent
from src.knowledge_catalog_service import KnowledgeCatalogService
from src.bq_executor import BigQueryExecutor

# Page Configuration & Modern Styling
st.set_page_config(
    page_title="Live GCP Conversational Analytics | Knowledge Catalog & BQGraph",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium UI / Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%);
        padding: 2rem;
        border-radius: 16px;
        color: #ffffff;
        box-shadow: 0 10px 25px -5px rgba(49, 46, 129, 0.5);
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .gcp-live-badge {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.5px;
    }

    .badge-metric {
        background-color: #0284c7;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    .badge-rootcause {
        background-color: #d97706;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    
    .term-pill {
        display: inline-block;
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid rgba(99, 102, 241, 0.4);
        color: #a5b4fc;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 0.8rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State & Services
if "gcp_project" not in st.session_state:
    st.session_state.gcp_project = os.getenv("GCP_PROJECT", "conversationalanalytics-507815")
if "bq_dataset" not in st.session_state:
    st.session_state.bq_dataset = os.getenv("BQ_DATASET", "supply_chain_analytics")

kc_service = KnowledgeCatalogService(
    project_id=st.session_state.gcp_project,
    dataset_id=st.session_state.bq_dataset
)
agent = ConversationalAnalyticsAgent(
    project_id=st.session_state.gcp_project,
    dataset_id=st.session_state.bq_dataset
)
executor = BigQueryExecutor(project_id=st.session_state.gcp_project)


# Header Banner
st.markdown(f"""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700;">⚡ Conversational Analytics Agent</h1>
        <span class="gcp-live-badge">LIVE GCP CONNECTED</span>
    </div>
    <p style="margin-top: 0.5rem; font-size: 1.1rem; opacity: 0.9;">
        Natural Language to SQL & BigQuery Graph (BQGraph) running live on project <code>{st.session_state.gcp_project}</code>
    </p>
</div>
""", unsafe_allow_html=True)


# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ GCP Settings & Context")
    
    st.session_state.gcp_project = st.text_input("GCP Project ID", value=st.session_state.gcp_project)
    st.session_state.bq_dataset = st.text_input("BigQuery Dataset ID", value=st.session_state.bq_dataset)
    gemini_key = st.text_input("Gemini API Key (Optional)", type="password", help="If empty, Application Default Credentials or direct generator is used.")
    if gemini_key:
        agent.api_key = gemini_key

    st.markdown("---")
    st.subheader("📚 Live Knowledge Catalog")
    with st.expander("📖 Business Glossary Terms", expanded=False):
        for term, meta in kc_service.business_glossary.items():
            st.markdown(f"**{term}** (`{meta['category']}`)")
            st.caption(meta["definition"])
            st.caption(f"*Formula:* `{meta['formula']}`")
            st.markdown("---")

    with st.expander("🏷️ Dataplex / Data Catalog Entries", expanded=False):
        dp_entries = kc_service.fetch_dataplex_glossary()
        if dp_entries:
            for entry in dp_entries:
                st.markdown(f"**{entry['display_name']}** (`{entry['search_result_subtype']}`)")
                st.caption(f"Resource: `{entry['relative_resource_name']}`")
                st.markdown("---")
        else:
            st.caption("No custom Data Catalog entries found for dataset scope.")

    with st.expander("🗄️ Live BigQuery Tables", expanded=True):
        live_tables = kc_service.fetch_live_table_schemas()
        if live_tables:
            for tbl, info in live_tables.items():
                st.markdown(f"**`{tbl}`** ({info.get('num_rows', 0)} rows)")
                for c, d in info['columns'].items():
                    st.caption(f"  • `{c}` ({d})")
        else:
            st.info(f"Target dataset: `{st.session_state.gcp_project}.{st.session_state.bq_dataset}`")


# Main Area: Query Interface
st.subheader("💬 Ask your GCP Data a Question")

sample_queries = [
    "What are our total shipments and delay percentage rate by carrier and region?",
    "Why is order ORD-9001 delayed and what is the root cause path in Chicago?",
    "Which carrier bottlenecks are causing SLA breaches across warehouses?",
    "What is our overall SLA breach percentage across all fulfillment hubs?"
]

selected_sample = st.selectbox("💡 Choose a sample scenario or type your own below:", ["Custom Question"] + sample_queries)

if selected_sample != "Custom Question":
    default_text = selected_sample
else:
    default_text = "Why is order ORD-9001 delayed and what is the root cause?"

user_query = st.text_area("Natural Language Query:", value=default_text, height=90)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    run_query = st.button("🚀 Analyze & Query GCP", type="primary", use_container_width=True)

if run_query and user_query.strip():
    with st.spinner(f"🔍 Querying GCP Knowledge Catalog for `{st.session_state.gcp_project}`..."):
        agent_response = agent.generate_query(user_query)

    intent = agent_response.get("intent", "METRIC_QUERY")
    query_type = agent_response.get("query_type", "SQL")
    generated_code = agent_response.get("generated_query", "")
    explanation = agent_response.get("explanation", "")
    terms_used = agent_response.get("business_terms_used", [])

    # Display Routing & Knowledge Catalog Metadata
    st.markdown("---")
    res_col1, res_col2 = st.columns([1, 2])

    with res_col1:
        st.markdown("### 🎯 Intent & Routing")
        if intent == "ROOT_CAUSE_QUERY":
            st.markdown('<span class="badge-rootcause">ROOT CAUSE / BQGRAPH QUERY</span>', unsafe_allow_html=True)
            st.markdown("**Engine:** BigQuery Property Graph (ISO GQL)")
        else:
            st.markdown('<span class="badge-metric">QUANTITATIVE METRIC QUERY</span>', unsafe_allow_html=True)
            st.markdown("**Engine:** Standard BigQuery GoogleSQL")

        st.markdown("#### 🏷️ Knowledge Catalog Business Context")
        if terms_used:
            for term in terms_used:
                st.markdown(f'<span class="term-pill">📖 {term}</span>', unsafe_allow_html=True)
        else:
            st.caption("Standard schema context applied.")

        st.markdown("#### 💡 Agent Rationale")
        st.info(explanation)

    with res_col2:
        st.markdown(f"### 💻 Generated {query_type}")
        st.code(generated_code, language="sql" if query_type == "SQL" else "sql")

    # Query Execution & Results
    st.markdown("---")
    st.markdown(f"### 📊 Live BigQuery Results (`{st.session_state.gcp_project}`)")
    
    with st.spinner("Executing on GCP BigQuery Engine..."):
        try:
            df_results, graph_meta = executor.execute_query(
                generated_code,
                query_type=query_type,
                dataset_id=st.session_state.bq_dataset
            )

            if graph_meta.get("enterprise_notice"):
                st.info(f"ℹ️ {graph_meta['enterprise_notice']}")

            if query_type == "GQL" and graph_meta.get("nodes"):
                tab_graph, tab_table = st.tabs(["🕸️ Root Cause Graph Topology", "📋 Live Results Table"])
                
                with tab_graph:
                    st.subheader("Interactive Root Cause Traversal (BQGraph)")
                    st.caption("Live BigQuery Path: Order ➔ Shipment ➔ Carrier / Warehouse ➔ Delay Incident")

                    # HTML/JS Interactive Network Graph Rendering
                    nodes_json = json.dumps(graph_meta.get("nodes", []))
                    edges_json = json.dumps(graph_meta.get("edges", []))

                    html_graph_code = f"""
                    <div id="mynetwork" style="height: 480px; width: 100%; border: 1px solid #334155; border-radius: 12px; background-color: #0f172a;"></div>
                    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
                    <script type="text/javascript">
                        var nodes = new vis.DataSet({nodes_json});
                        var edges = new vis.DataSet({edges_json});
                        var container = document.getElementById('mynetwork');
                        var data = {{ nodes: nodes, edges: edges }};
                        var options = {{
                            nodes: {{
                                shape: 'box',
                                margin: 10,
                                font: {{ color: '#ffffff', face: 'Inter' }},
                                borderWidth: 2,
                                shadow: true
                            }},
                            edges: {{
                                arrows: 'to',
                                color: {{ color: '#818cf8', highlight: '#c084fc' }},
                                font: {{ color: '#cbd5e1', size: 11 }},
                                smooth: {{ type: 'cubicBezier' }}
                            }},
                            groups: {{
                                Order: {{ color: {{ background: '#dc2626', border: '#f87171' }} }},
                                Shipment: {{ color: {{ background: '#2563eb', border: '#60a5fa' }} }},
                                Carrier: {{ color: {{ background: '#7c3aed', border: '#a78bfa' }} }},
                                Warehouse: {{ color: {{ background: '#059669', border: '#34d399' }} }},
                                Delay: {{ color: {{ background: '#d97706', border: '#fbbf24' }} }}
                            }},
                            physics: {{
                                barnesHut: {{ gravitationalConstant: -3000, springLength: 120 }}
                            }}
                        }};
                        var network = new vis.Network(container, data, options);
                    </script>
                    """
                    st.components.v1.html(html_graph_code, height=500)

                with tab_table:
                    st.dataframe(df_results, use_container_width=True)
            else:
                st.dataframe(df_results, use_container_width=True)

                # Summary KPIs if applicable
                if "total_shipments" in df_results.columns:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Shipments", int(df_results["total_shipments"].sum()))
                    if "delayed_shipments" in df_results.columns:
                        m2.metric("Delayed Shipments", int(df_results["delayed_shipments"].sum()))
                    if "delay_percentage_rate" in df_results.columns:
                        m3.metric("Avg Delay Rate", f"{df_results['delay_percentage_rate'].mean():.1f}%")

        except Exception as err:
            st.error(f"❌ BigQuery Execution Error: {str(err)}")

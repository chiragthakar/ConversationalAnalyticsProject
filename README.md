# Conversational Analytics Agent: Knowledge Catalog & BQGraph Integration

An enterprise-grade Conversational Analytics Agent built on **Google Cloud Platform (GCP)**. It leverages business context from **GCP Dataplex / Knowledge Catalog** to convert natural language queries into **BigQuery GoogleSQL** for quantitative metrics and **BigQuery Property Graph (BQGraph / ISO GQL)** for root-cause analytics and "why" questions.

---

## Key Features

1. **GCP Knowledge Catalog Context Integration**
   - Incorporates business glossary terms (e.g., *SLA Breach*, *Carrier Bottleneck*, *Warehouse Congestion*), column tags, and metric formulas into the Gemini LLM prompt before query generation.
2. **Dynamic Intent Classifier & Query Router**
   - **`METRIC_QUERY`**: Quantitative questions (*"What is the delay percentage by carrier?"*) produce standard BigQuery GoogleSQL.
   - **`ROOT_CAUSE_QUERY`**: Structural/Why questions (*"Why is order ORD-9001 delayed in Chicago?"*) produce ISO-compliant **BigQuery Property Graph (BQGraph GQL)** queries (`GRAPH project.dataset.graph MATCH ...`).
3. **ISO-Compliant BigQuery GQL Generator**
   - Strictly enforces BigQuery GoogleSQL GQL standards (`GRAPH ... MATCH (s)-[e]->(d)`), avoiding Cypher syntax, handling path variables, and wrapping output elements in `TO_JSON()` for graph visualizers.
4. **Interactive Dashboard UI (Streamlit & vis.js)**
   - Includes a rich Web Application featuring Knowledge Catalog metadata inspection, generated query viewers, and an interactive 2D graph topology renderer to visualize multi-hop supply chain root-cause paths.

---

## Architecture Overview

```
User Query ("Why is order ORD-9001 delayed?")
  │
  ├──> Knowledge Catalog Service (Fetches Glossary & Schemas)
  │
  ├──> Conversational Agent Router (Detects METRIC vs ROOT_CAUSE intent)
  │
  ├──> Gemini LLM Engine (Applies Business Context & Generates Query)
  │       ├──> Quantitative -> BigQuery SQL (SELECT ...)
  │       └──> Root Cause   -> BigQuery GQL (GRAPH ... MATCH ...)
  │
  └──> BigQuery Engine -> Executed & Formatted as Tabular Data or Graph Topology
```

---

## Setup & Running Instructions

### 1. Prerequisites
- Python 3.9+ installed.
- (Optional) GCP Project with BigQuery enabled and `gcloud` authenticated.

### 2. Environment Initialization & Dependency Setup
Run the following commands in your workspace root:

```bash
# Create Python virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
.venv\Scripts\pip install -r requirements.txt
```

### 3. Deploying BigQuery Tables & Property Graph DDL
Deploy the tables and `CREATE PROPERTY GRAPH` schema to your BigQuery dataset:

```bash
# Execute DDL setup script via gcloud or BigQuery Console
bq query --use_legacy_sql=false < sql/ddl_setup.sql
```

### 4. Running the Streamlit Web Application

```bash
.venv\Scripts\streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

---

## Project Structure

```
ConversationalAnalyticsProject/
├── sql/
│   └── ddl_setup.sql               # BigQuery tables & CREATE PROPERTY GRAPH DDL
├── src/
│   ├── __init__.py
│   ├── knowledge_catalog_service.py # Knowledge Catalog & Dataplex context provider
│   ├── agent.py                    # Intent classifier & NL-to-SQL/GQL generator
│   └── bq_executor.py              # BigQuery executor & graph TO_JSON parser
├── app.py                          # Interactive Streamlit Web Application
├── requirements.txt                # Python package requirements
└── README.md                       # Project documentation
```

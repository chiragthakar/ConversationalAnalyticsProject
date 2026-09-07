"""
Live Knowledge Catalog & BigQuery Schema Metadata Provider.

Fetches real table schemas, column data types, field descriptions, and business glossary metadata
directly from Google Cloud BigQuery and Dataplex Catalog APIs.
"""

import os
from typing import Dict, Any, List, Optional

from google.cloud import bigquery

try:
    from google.cloud import dataplex_v1
    DATAPLEX_AVAILABLE = True
except ImportError:
    DATAPLEX_AVAILABLE = False


class KnowledgeCatalogService:
    """Service to retrieve live business glossaries, metric definitions, and BigQuery schema context."""

    def __init__(
        self,
        project_id: str = "conversationalanalytics-507815",
        dataset_id: str = "supply_chain_analytics",
        location: str = "us-central1"
    ):
        self.project_id = os.getenv("GCP_PROJECT", project_id)
        self.dataset_id = os.getenv("BQ_DATASET", dataset_id)
        self.location = os.getenv("GCP_LOCATION", location)
        
        self.bq_client = None
        try:
            self.bq_client = bigquery.Client(project=self.project_id)
        except Exception:
            self.bq_client = None

        # Standard Enterprise Business Glossary Taxonomy (Dataplex / Data Catalog Taxonomies)
        self.business_glossary: Dict[str, Dict[str, str]] = {
            "SLA_Breach": {
                "definition": "A shipment whose delay_hours > 24 or whose delivery date exceeds estimated SLA.",
                "formula": "COUNT(CASE WHEN delay_hours > 24 THEN 1 END) / COUNT(shipment_id)",
                "category": "Key Performance Metric"
            },
            "Carrier_Bottleneck": {
                "definition": "A transport carrier with reliability score < 0.85 or associated with > 3 delay incidents.",
                "formula": "CARRIER where reliability_score < 0.85 OR count(delays) > 3",
                "category": "Root Cause Category"
            },
            "Warehouse_Congestion": {
                "definition": "A warehouse running over 85% capacity or tagged with status CONGESTED.",
                "formula": "capacity_utilization > 0.85 OR status = 'CONGESTED'",
                "category": "Root Cause Category"
            },
            "Root_Cause_Path": {
                "definition": "Multi-hop graph traversal path connecting an Order to Shipment, Carrier, Warehouse, and Delay cause.",
                "formula": "GQL Pattern: MATCH p = (Order)-[:BELONGS_TO_ORDER]-(Shipment)-[:HAS_DELAY]->(Delay)",
                "category": "BQGraph Traversal"
            }
        }

    def fetch_live_table_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Queries BigQuery API directly to inspect table columns and data types."""
        schemas = {}
        if not self.bq_client:
            return schemas

        try:
            dataset_ref = self.bq_client.dataset(self.dataset_id, project=self.project_id)
            tables = list(self.bq_client.list_tables(dataset_ref))

            for table_item in tables:
                table_id = table_item.table_id
                full_table = self.bq_client.get_table(table_item.reference)
                
                cols = {}
                for field in full_table.schema:
                    desc = field.description or f"{field.field_type} field"
                    cols[field.name] = f"{field.field_type} - {desc}"

                schemas[table_id] = {
                    "description": full_table.description or f"BigQuery table `{table_id}`",
                    "num_rows": full_table.num_rows,
                    "columns": cols
                }
        except Exception:
            pass

        return schemas

    def fetch_dataplex_glossary(self) -> List[Dict[str, Any]]:
        """Queries live Business Glossary Term Entries published in GCP Dataplex Catalog."""
        results = []
        if not DATAPLEX_AVAILABLE or not self.project_id:
            return results

        try:
            client = dataplex_v1.CatalogServiceClient()
            entry_group_parent = f"projects/{self.project_id}/locations/{self.location}/entryGroups/supply-chain-glossary-group"
            
            for entry in client.list_entries(parent=entry_group_parent):
                display_name = entry.entry_source.display_name if (entry.entry_source and entry.entry_source.display_name) else entry.name
                desc = entry.entry_source.description if entry.entry_source else ""
                results.append({
                    "relative_resource_name": entry.name,
                    "search_result_subtype": "Dataplex Glossary Term Entry",
                    "display_name": display_name,
                    "description": desc
                })
        except Exception:
            pass

        return results

    def get_full_context_prompt(self, user_query: str) -> str:
        """Constructs live prompt context incorporating BigQuery API schemas and glossaries."""
        glossary_str = "\n".join([
            f"- **{term}**: {data['definition']} (Category: {data['category']})"
            for term, data in self.business_glossary.items()
        ])

        live_schemas = self.fetch_live_table_schemas()
        tables_str = ""
        
        if live_schemas:
            for tbl, info in live_schemas.items():
                tables_str += f"\nLive BigQuery Table `{self.project_id}.{self.dataset_id}.{tbl}` (Rows: {info.get('num_rows', 'N/A')}):\n"
                for col, desc in info['columns'].items():
                    tables_str += f"  - `{col}`: {desc}\n"
        else:
            tables_str = f"""
Table `{self.project_id}.{self.dataset_id}.warehouses`: warehouse_id (STRING), warehouse_name (STRING), region (STRING), capacity (INT64), status (STRING)
Table `{self.project_id}.{self.dataset_id}.orders`: order_id (STRING), customer_id (STRING), order_date (TIMESTAMP), total_amount (NUMERIC), status (STRING)
Table `{self.project_id}.{self.dataset_id}.carriers`: carrier_id (STRING), carrier_name (STRING), transport_type (STRING), reliability_score (FLOAT64)
Table `{self.project_id}.{self.dataset_id}.shipments`: shipment_id (STRING), order_id (STRING), warehouse_id (STRING), carrier_id (STRING), shipped_date (TIMESTAMP), delivery_date (TIMESTAMP), status (STRING)
Table `{self.project_id}.{self.dataset_id}.shipment_delays`: delay_id (STRING), shipment_id (STRING), delay_code (STRING), delay_reason (STRING), delay_hours (INT64), location (STRING)
"""

        graph_str = f"""
BigQuery Property Graph Name: `{self.project_id}.{self.dataset_id}.supply_chain_graph`
Node Labels:
  - :Warehouse (Key: warehouse_id)
  - :Order (Key: order_id) -- Note: Order is a reserved word, always escape as `Order` in DDL/GQL pattern bindings
  - :Carrier (Key: carrier_id)
  - :Shipment (Key: shipment_id)
  - :Delay (Key: delay_id)

Edge Labels:
  - (Shipment)-[:FULFILLED_FROM]->(Warehouse)
  - (Shipment)-[:BELONGS_TO_ORDER]->(`Order`)
  - (Shipment)-[:HANDLED_BY_CARRIER]->(Carrier)
  - (Shipment)-[:HAS_DELAY]->(Delay)
"""

        dataplex_entries = self.fetch_dataplex_glossary()
        dataplex_str = ""
        if dataplex_entries:
            dataplex_str = "GCP DATAPLEX CATALOG GLOSSARY ENTRIES:\n" + "\n".join([
                f"- Term Entry: {item['display_name']} ({item['relative_resource_name']}): {item.get('description', '')}"
                for item in dataplex_entries
            ]) + "\n\n"

        context_block = f"""
================================================================================
LIVE BUSINESS & SCHEMA CONTEXT FROM GCP BIGQUERY / KNOWLEDGE CATALOG
================================================================================
GCP PROJECT: `{self.project_id}`
BIGQUERY DATASET: `{self.dataset_id}`

BUSINESS GLOSSARY & METRIC DEFINITIONS:
{glossary_str}

{dataplex_str}LIVE TABLE SCHEMAS:
{tables_str}

BIGQUERY PROPERTY GRAPH SCHEMA (BQGraph):
{graph_str}
================================================================================
"""
        return context_block

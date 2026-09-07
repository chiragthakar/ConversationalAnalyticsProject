"""
Knowledge Catalog & Dataplex Metadata Context Provider.

This service fetches business glossaries, schema definitions, column tags,
and metric definitions from GCP Dataplex / Knowledge Catalog to enrich
the LLM prompt context before NL-to-SQL or NL-to-GQL conversion.
"""

import os
from typing import Dict, Any, List, Optional
try:
    from google.cloud import datacatalog_v1
    from google.cloud import dataplex_v1
    GCP_CATALOG_AVAILABLE = True
except ImportError:
    GCP_CATALOG_AVAILABLE = False


class KnowledgeCatalogService:
    """Service to retrieve business terms, metric definitions, and schema context."""

    def __init__(self, project_id: str = "my-gcp-project", location: str = "us-central1"):
        self.project_id = os.getenv("GCP_PROJECT", project_id)
        self.location = os.getenv("GCP_LOCATION", location)
        
        # In-memory Business Context & Glossaries (matches GCP Data Catalog / Dataplex taxonomies)
        self.business_glossary: Dict[str, Dict[str, str]] = {
            "SLA_Breach": {
                "definition": "A shipment whose delay_hours > 24 or whose delivery date exceeds estimated delivery.",
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
                "formula": "GQL Pattern: (Order)<-[:BELONGS_TO_ORDER]-(Shipment)-[:HAS_DELAY]->(Delay)",
                "category": "BQGraph Traversal"
            }
        }

        self.table_schemas: Dict[str, Dict[str, Any]] = {
            "warehouses": {
                "description": "Fulfillment center warehouses holding product inventory.",
                "columns": {
                    "warehouse_id": "Primary key for warehouse (STRING)",
                    "warehouse_name": "Full name of fulfillment center (STRING)",
                    "region": "Geographic location e.g. US-WEST, US-MIDWEST (STRING)",
                    "capacity": "Total unit handling capacity (INT64)",
                    "status": "Operational status: ACTIVE, CONGESTED, INACTIVE (STRING)"
                }
            },
            "carriers": {
                "description": "Logistics and shipping carriers handling transport.",
                "columns": {
                    "carrier_id": "Primary key for carrier (STRING)",
                    "carrier_name": "Carrier enterprise name (STRING)",
                    "transport_type": "Mode of transit: AIR, TRUCK, RAIL (STRING)",
                    "reliability_score": "Historical on-time score between 0.0 and 1.0 (FLOAT64)"
                }
            },
            "orders": {
                "description": "Customer purchase orders.",
                "columns": {
                    "order_id": "Primary key for customer order (STRING)",
                    "customer_id": "Unique customer identifier (STRING)",
                    "order_date": "Timestamp when order was placed (TIMESTAMP)",
                    "total_amount": "Total order dollar value (NUMERIC)",
                    "status": "Order state: PENDING, DELIVERED, DELAYED, CANCELLED (STRING)"
                }
            },
            "shipments": {
                "description": "Package shipments associated with orders.",
                "columns": {
                    "shipment_id": "Primary key for shipment (STRING)",
                    "order_id": "Foreign key referencing orders.order_id (STRING)",
                    "warehouse_id": "Foreign key referencing warehouses.warehouse_id (STRING)",
                    "carrier_id": "Foreign key referencing carriers.carrier_id (STRING)",
                    "shipped_date": "Timestamp package left warehouse (TIMESTAMP)",
                    "delivery_date": "Timestamp package reached destination (TIMESTAMP)",
                    "status": "Shipment status: IN_TRANSIT, DELIVERED, DELAYED (STRING)"
                }
            },
            "shipment_delays": {
                "description": "Detailed incident records of logistics and supply chain delays.",
                "columns": {
                    "delay_id": "Primary key for delay record (STRING)",
                    "shipment_id": "Foreign key referencing shipments.shipment_id (STRING)",
                    "delay_code": "Category code e.g. RAIL_CONGESTION, WH_BACKLOG, WEATHER (STRING)",
                    "delay_reason": "Detailed description of delay cause (STRING)",
                    "delay_hours": "Number of impact hours lost (INT64)",
                    "location": "Physical location where delay occurred (STRING)"
                }
            }
        }

        self.property_graph_schema: Dict[str, Any] = {
            "graph_name": "supply_chain_graph",
            "description": "BigQuery Property Graph representing supply chain dependencies for root cause analysis.",
            "nodes": [
                {"label": "Warehouse", "table": "warehouses", "key": "warehouse_id", "properties": ["warehouse_id", "warehouse_name", "region", "status"]},
                {"label": "Order", "table": "orders", "key": "order_id", "properties": ["order_id", "customer_id", "order_date", "status"]},
                {"label": "Carrier", "table": "carriers", "key": "carrier_id", "properties": ["carrier_id", "carrier_name", "transport_type", "reliability_score"]},
                {"label": "Shipment", "table": "shipments", "key": "shipment_id", "properties": ["shipment_id", "shipped_date", "delivery_date", "status"]},
                {"label": "Delay", "table": "shipment_delays", "key": "delay_id", "properties": ["delay_id", "delay_code", "delay_reason", "delay_hours", "location"]}
            ],
            "edges": [
                {"label": "FULFILLED_FROM", "source": "Shipment", "destination": "Warehouse", "properties": []},
                {"label": "BELONGS_TO_ORDER", "source": "Shipment", "destination": "Order", "properties": []},
                {"label": "HANDLED_BY_CARRIER", "source": "Shipment", "destination": "Carrier", "properties": []},
                {"label": "HAS_DELAY", "source": "Shipment", "destination": "Delay", "properties": []}
            ]
        }

    def fetch_dataplex_entry(self, entry_name: str) -> Optional[Dict[str, Any]]:
        """Fetch live entry from GCP Dataplex / Data Catalog if available."""
        if not GCP_CATALOG_AVAILABLE:
            return None
        try:
            client = datacatalog_v1.DataCatalogClient()
            # Construct standard entry path if provided
            request = datacatalog_v1.GetEntryRequest(name=entry_name)
            entry = client.get_entry(request=request)
            return {
                "name": entry.name,
                "display_name": entry.display_name,
                "description": entry.description,
                "schema": entry.schema
            }
        except Exception:
            return None

    def get_full_context_prompt(self, user_query: str) -> str:
        """Constructs a comprehensive Context Block combining Business Glossary and Schemas."""
        glossary_str = "\n".join([
            f"- **{term}**: {data['definition']} (Category: {data['category']})"
            for term, data in self.business_glossary.items()
        ])

        tables_str = ""
        for tbl, info in self.table_schemas.items():
            tables_str += f"\nTable `{tbl}` ({info['description']}):\n"
            for col, desc in info['columns'].items():
                tables_str += f"  - `{col}`: {desc}\n"

        graph_str = f"Property Graph Name: `{self.property_graph_schema['graph_name']}`\n"
        graph_str += "Nodes:\n"
        for n in self.property_graph_schema["nodes"]:
            graph_str += f"  - :{n['label']} (Key: {n['key']}, Table: `{n['table']}`)\n"
        graph_str += "Edges:\n"
        for e in self.property_graph_schema["edges"]:
            graph_str += f"  - ({e['source']}) -[:{e['label']}]-> ({e['destination']})\n"

        context_block = f"""
================================================================================
BUSINESS CONTEXT FROM GCP KNOWLEDGE CATALOG
================================================================================
BUSINESS GLOSSARY & METRIC DEFINITIONS:
{glossary_str}

RELATIONAL SCHEMAS:
{tables_str}

BIGQUERY PROPERTY GRAPH SCHEMA (BQGraph):
{graph_str}
================================================================================
"""
        return context_block

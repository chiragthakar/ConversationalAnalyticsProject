"""
BigQuery & BQGraph Query Executor.

Executes GoogleSQL queries and ISO GQL property graph queries on Google Cloud BigQuery.
Parses query outputs into pandas DataFrames (tabular) or NetworkX/PyVis structures (graph topology).
"""

import os
import json
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional

try:
    from google.cloud import bigquery
    BQ_CLIENT_AVAILABLE = True
except ImportError:
    BQ_CLIENT_AVAILABLE = False


class BigQueryExecutor:
    """Executes SQL and GQL queries on BigQuery, formatting tabular and graph outputs."""

    def __init__(self, project_id: str = "my-gcp-project"):
        self.project_id = os.getenv("GCP_PROJECT", project_id)
        self.client = None
        if BQ_CLIENT_AVAILABLE:
            try:
                self.client = bigquery.Client(project=self.project_id)
            except Exception:
                self.client = None

    def execute_query(self, query: str, query_type: str = "SQL") -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Executes query and returns (dataframe_results, graph_metadata)."""
        if self.client:
            try:
                query_job = self.client.query(query)
                results_df = query_job.to_dataframe()
                
                graph_metadata = {}
                if query_type == "GQL":
                    graph_metadata = self.parse_gql_json_results(results_df)
                    
                return results_df, graph_metadata
            except Exception as e:
                # If execution against GCP fails (e.g., mock project ID), fallback to simulated response
                return self._simulate_execution(query, query_type, str(e))
        else:
            return self._simulate_execution(query, query_type, "No GCP BigQuery client authenticated.")

    def parse_gql_json_results(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Parses TO_JSON() output columns from BQGraph query into nodes and edges."""
        nodes = {}
        edges = []

        for _, row in df.iterrows():
            for col in df.columns:
                val = row[col]
                if pd.isna(val) or not val:
                    continue

                try:
                    if isinstance(val, str):
                        data = json.loads(val)
                    elif isinstance(val, dict):
                        data = val
                    else:
                        continue

                    # Process extracted node/edge elements
                    if isinstance(data, dict):
                        # Node check
                        if "identifier" in data or "id" in data or "labels" in data:
                            node_id = data.get("identifier") or data.get("id") or str(hash(json.dumps(data)))
                            label = data.get("labels", ["Entity"])[0] if isinstance(data.get("labels"), list) else "Entity"
                            props = data.get("properties", data)
                            nodes[node_id] = {
                                "id": node_id,
                                "label": f"{label}: {node_id}",
                                "group": label,
                                "properties": props
                            }
                except Exception:
                    continue

        return {"nodes": list(nodes.values()), "edges": edges}

    def _simulate_execution(
        self,
        query: str,
        query_type: str,
        error_msg: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Simulates dataset query output for local demo and offline testing."""
        if query_type == "GQL":
            # Mock BQGraph response
            raw_data = [
                {
                    "order_node": json.dumps({"labels": ["Order"], "id": "ORD-9001", "properties": {"status": "DELAYED", "amount": 1250.0}}),
                    "shipment_node": json.dumps({"labels": ["Shipment"], "id": "SHP-501", "properties": {"status": "DELAYED"}}),
                    "carrier_node": json.dumps({"labels": ["Carrier"], "id": "CR-03", "properties": {"name": "Coastal Rail & Road", "reliability": 0.81}}),
                    "warehouse_node": json.dumps({"labels": ["Warehouse"], "id": "WH-103", "properties": {"name": "Chicago Express Hub", "status": "CONGESTED"}}),
                    "delay_node": json.dumps({"labels": ["Delay"], "id": "DLY-01", "properties": {"code": "RAIL_CONGESTION", "hours": 36, "reason": "Interchange bottleneck"}}),
                    "root_cause_path": "ORD-9001 -> SHP-501 -> [CR-03 & WH-103] -> DLY-01 (36 hrs)"
                },
                {
                    "order_node": json.dumps({"labels": ["Order"], "id": "ORD-9003", "properties": {"status": "DELAYED", "amount": 3200.0}}),
                    "shipment_node": json.dumps({"labels": ["Shipment"], "id": "SHP-503", "properties": {"status": "DELAYED"}}),
                    "carrier_node": json.dumps({"labels": ["Carrier"], "id": "CR-03", "properties": {"name": "Coastal Rail & Road", "reliability": 0.81}}),
                    "warehouse_node": json.dumps({"labels": ["Warehouse"], "id": "WH-103", "properties": {"name": "Chicago Express Hub", "status": "CONGESTED"}}),
                    "delay_node": json.dumps({"labels": ["Delay"], "id": "DLY-02", "properties": {"code": "WH_BACKLOG", "hours": 24, "reason": "High volume sorting backlog"}}),
                    "root_cause_path": "ORD-9003 -> SHP-503 -> WH-103 -> DLY-02 (24 hrs)"
                }
            ]
            df = pd.DataFrame(raw_data)
            
            nodes = [
                {"id": "ORD-9001", "label": "Order: ORD-9001 (DELAYED)", "group": "Order", "title": "Amount: $1250.00"},
                {"id": "ORD-9003", "label": "Order: ORD-9003 (DELAYED)", "group": "Order", "title": "Amount: $3200.00"},
                {"id": "SHP-501", "label": "Shipment: SHP-501", "group": "Shipment", "title": "Status: DELAYED"},
                {"id": "SHP-503", "label": "Shipment: SHP-503", "group": "Shipment", "title": "Status: DELAYED"},
                {"id": "WH-103", "label": "Warehouse: WH-103 (Chicago)", "group": "Warehouse", "title": "Status: CONGESTED"},
                {"id": "CR-03", "label": "Carrier: CR-03 (Coastal Rail)", "group": "Carrier", "title": "Reliability: 81%"},
                {"id": "DLY-01", "label": "Delay: RAIL_CONGESTION (36h)", "group": "Delay", "title": "Reason: Interchange bottleneck"},
                {"id": "DLY-02", "label": "Delay: WH_BACKLOG (24h)", "group": "Delay", "title": "Reason: Sorting backlog"}
            ]
            edges = [
                {"from": "SHP-501", "to": "ORD-9001", "label": "BELONGS_TO_ORDER"},
                {"from": "SHP-503", "to": "ORD-9003", "label": "BELONGS_TO_ORDER"},
                {"from": "SHP-501", "to": "WH-103", "label": "FULFILLED_FROM"},
                {"from": "SHP-503", "to": "WH-103", "label": "FULFILLED_FROM"},
                {"from": "SHP-501", "to": "CR-03", "label": "HANDLED_BY_CARRIER"},
                {"from": "SHP-503", "to": "CR-03", "label": "HANDLED_BY_CARRIER"},
                {"from": "SHP-501", "to": "DLY-01", "label": "HAS_DELAY"},
                {"from": "SHP-503", "to": "DLY-02", "label": "HAS_DELAY"}
            ]
            return df, {"nodes": nodes, "edges": edges, "simulated": True, "notice": error_msg}
        else:
            # Mock SQL table result
            df = pd.DataFrame([
                {"region": "US-MIDWEST", "carrier_name": "Coastal Rail & Road", "total_shipments": 45, "delayed_shipments": 14, "delay_percentage_rate": 31.11},
                {"region": "US-WEST", "carrier_name": "SwiftFreight Logistics", "total_shipments": 60, "delayed_shipments": 6, "delay_percentage_rate": 10.00},
                {"region": "US-SOUTH", "carrier_name": "Apex Air Cargo", "total_shipments": 30, "delayed_shipments": 1, "delay_percentage_rate": 3.33}
            ])
            return df, {"simulated": True, "notice": error_msg}

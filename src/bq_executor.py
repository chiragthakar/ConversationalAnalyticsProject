"""
Live BigQuery & BQGraph Query Executor.

Executes GoogleSQL queries and ISO GQL property graph queries directly on BigQuery.
Parses live query outputs into pandas DataFrames (tabular) or NetworkX/PyVis structures (graph topology).
"""

import os
import json
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional

import db_dtypes
from google.cloud import bigquery


class BigQueryExecutor:
    """Executes SQL and GQL queries on BigQuery, formatting tabular and graph outputs."""

    def __init__(self, project_id: str = "conversationalanalytics-507815"):
        self.project_id = os.getenv("GCP_PROJECT", project_id)
        self.client = None
        try:
            self.client = bigquery.Client(project=self.project_id)
        except Exception as err:
            self.client = None
            self.init_error = str(err)

    def execute_query(
        self,
        query: str,
        query_type: str = "SQL",
        dataset_id: str = "supply_chain_analytics"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Executes query directly on Google Cloud BigQuery."""
        if not self.client:
            raise RuntimeError(f"BigQuery Client Initialization Error: Could not connect to GCP project '{self.project_id}'.")

        try:
            query_job = self.client.query(query)
            results_df = query_job.to_dataframe()
            
            graph_metadata = {}
            if query_type == "GQL":
                graph_metadata = self.parse_gql_json_results(results_df)
                
            return results_df, graph_metadata
        except Exception as e:
            err_msg = str(e)
            
            # Special handling for BQGraph Enterprise Edition requirement
            if "require a reservation with Enterprise or Enterprise Plus edition" in err_msg:
                # Run equivalent live SQL graph traversal query on live tables to return actual data
                fallback_sql = f"""
                SELECT 
                    o.order_id,
                    o.status AS order_status,
                    s.shipment_id,
                    w.warehouse_name,
                    w.region AS warehouse_region,
                    c.carrier_name,
                    d.delay_code,
                    d.delay_reason,
                    d.delay_hours
                FROM `{self.project_id}.{dataset_id}.orders` o
                JOIN `{self.project_id}.{dataset_id}.shipments` s ON o.order_id = s.order_id
                JOIN `{self.project_id}.{dataset_id}.warehouses` w ON s.warehouse_id = w.warehouse_id
                JOIN `{self.project_id}.{dataset_id}.carriers` c ON s.carrier_id = c.carrier_id
                LEFT JOIN `{self.project_id}.{dataset_id}.shipment_delays` d ON s.shipment_id = d.shipment_id
                WHERE o.status = 'DELAYED' OR s.status = 'DELAYED'
                """
                fallback_job = self.client.query(fallback_sql)
                df = fallback_job.to_dataframe()
                
                # Build graph nodes and edges directly from live BigQuery table rows
                nodes = []
                edges = []
                seen_nodes = set()

                for _, row in df.iterrows():
                    ord_id = str(row["order_id"])
                    shp_id = str(row["shipment_id"])
                    wh_name = str(row["warehouse_name"])
                    car_name = str(row["carrier_name"])
                    dly_code = str(row.get("delay_code") or "DELAY")

                    if ord_id not in seen_nodes:
                        nodes.append({"id": ord_id, "label": f"Order: {ord_id}", "group": "Order", "title": f"Status: {row['order_status']}"})
                        seen_nodes.add(ord_id)
                    
                    if shp_id not in seen_nodes:
                        nodes.append({"id": shp_id, "label": f"Shipment: {shp_id}", "group": "Shipment", "title": "Status: DELAYED"})
                        seen_nodes.add(shp_id)
                        edges.append({"from": shp_id, "to": ord_id, "label": "BELONGS_TO_ORDER"})

                    if wh_name not in seen_nodes:
                        nodes.append({"id": wh_name, "label": f"Warehouse: {wh_name}", "group": "Warehouse", "title": f"Region: {row['warehouse_region']}"})
                        seen_nodes.add(wh_name)
                        edges.append({"from": shp_id, "to": wh_name, "label": "FULFILLED_FROM"})

                    if car_name not in seen_nodes:
                        nodes.append({"id": car_name, "label": f"Carrier: {car_name}", "group": "Carrier", "title": "Transport Carrier"})
                        seen_nodes.add(car_name)
                        edges.append({"from": shp_id, "to": car_name, "label": "HANDLED_BY_CARRIER"})

                    if dly_code not in seen_nodes:
                        nodes.append({"id": dly_code, "label": f"Delay: {dly_code} ({row['delay_hours']}h)", "group": "Delay", "title": str(row['delay_reason'])})
                        seen_nodes.add(dly_code)
                        edges.append({"from": shp_id, "to": dly_code, "label": "HAS_DELAY"})

                return df, {
                    "nodes": nodes,
                    "edges": edges,
                    "enterprise_notice": "Live Property Graph created in BigQuery (`supply_chain_graph`). Direct GQL execution on BigQuery requires an Enterprise/Enterprise Plus reservation. Topology below is dynamically built from live BigQuery table rows."
                }
            else:
                raise RuntimeError(f"BigQuery Query Execution Failed: {err_msg}")

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

                    if isinstance(data, dict):
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

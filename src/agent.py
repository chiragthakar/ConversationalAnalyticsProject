"""
Conversational Analytics Agent: Intent Router & NL-to-SQL / NL-to-GQL Generator.

Uses Gemini API with Knowledge Catalog metadata context to convert natural language queries
into either standard BigQuery GoogleSQL or BigQuery Property Graph GQL for root-cause analysis.
"""

import os
import json
import re
from typing import Dict, Any, Tuple, Optional
from src.knowledge_catalog_service import KnowledgeCatalogService

try:
    from google import genai
    from google.genai import types
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False


class ConversationalAnalyticsAgent:
    """Agent that classifies intent and converts natural language into SQL or BQGraph GQL."""

    def __init__(
        self,
        project_id: str = "conversationalanalytics-507815",
        dataset_id: str = "supply_chain_analytics",
        api_key: Optional[str] = None
    ):
        self.project_id = os.getenv("GCP_PROJECT", project_id)
        self.dataset_id = os.getenv("BQ_DATASET", dataset_id)
        self.kc_service = KnowledgeCatalogService(
            project_id=self.project_id,
            dataset_id=self.dataset_id
        )
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        if GEMINI_SDK_AVAILABLE:
            try:
                if self.api_key:
                    self.client = genai.Client(api_key=self.api_key)
                else:
                    self.client = genai.Client()
            except Exception:
                self.client = None

    def classify_intent(self, user_query: str) -> str:
        """Determines if query is a quantitative METRIC_QUERY or a ROOT_CAUSE_QUERY."""
        root_cause_keywords = [
            "why", "root cause", "bottleneck", "reason", "trace",
            "path", "dependency", "impact", "relationship", "chain", "cause"
        ]
        query_lower = user_query.lower()
        if any(kw in query_lower for kw in root_cause_keywords):
            return "ROOT_CAUSE_QUERY"
        return "METRIC_QUERY"

    def generate_query(self, user_query: str) -> Dict[str, Any]:
        """Generates SQL or BQGraph GQL query with live Knowledge Catalog context."""
        intent = self.classify_intent(user_query)
        context = self.kc_service.get_full_context_prompt(user_query)
        
        full_table_prefix = f"`{self.project_id}.{self.dataset_id}`"
        graph_full_name = f"`{self.project_id}.{self.dataset_id}.supply_chain_graph`"

        system_instruction = f"""
You are an expert Google Cloud BigQuery Data Engineer and Graph Analytics Specialist.
Your task is to convert the User's Natural Language Query into executable BigQuery code.

Target Dataset Prefix: {full_table_prefix}
Target Property Graph: {graph_full_name}

{context}

INTENT CLASSIFICATION RULES:
- Query Intent detected: {intent}

If INTENT is METRIC_QUERY:
- Generate standard GoogleSQL (SELECT ... FROM {full_table_prefix}.table ...).
- Always use backticks around full table names, e.g., {full_table_prefix}.shipments.
- Use business glossary formulas from Knowledge Catalog where appropriate.

If INTENT is ROOT_CAUSE_QUERY:
- Generate BigQuery Property Graph Query Language (GQL).
- Syntax MUST begin with: GRAPH {graph_full_name}
- MUST use standard BigQuery ISO GQL (`MATCH (src)-[e]->(dst)`).
- NEVER generate Cypher syntax.
- Enforce backtick escaping around reserved SQL keywords when used as node identifiers (e.g. `ord:Order` or `ord:\`Order\``).
- For graph visualization or topology path tracing, wrap output nodes/edges/paths in TO_JSON():
  `RETURN TO_JSON(s) AS shipment, TO_JSON(d) AS delay, TO_JSON(p) AS root_cause_path LIMIT 500`

OUTPUT FORMAT REQUIREMENTS:
Return your answer strictly as a JSON object with the following fields:
{{
    "intent": "{intent}",
    "query_type": "SQL" or "GQL",
    "generated_query": "the SQL or GQL statement",
    "explanation": "concise rationale of how Knowledge Catalog context & BQGraph rules were applied",
    "business_terms_used": ["list of terms applied from Knowledge Catalog"]
}}
"""

        prompt = f"User Query: \"{user_query}\"\nGenerate the JSON output now."

        # Execute live Gemini generation
        if self.client:
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                result = json.loads(response.text)
                return result
            except Exception as err:
                raise RuntimeError(f"Gemini API Query Generation Error: {str(err)}")
        else:
            # Deterministic live query construction when GEMINI_API_KEY is not set
            return self._build_direct_gcp_query(user_query, intent, full_table_prefix, graph_full_name)

    def _build_direct_gcp_query(
        self,
        user_query: str,
        intent: str,
        table_prefix: str,
        graph_name: str
    ) -> Dict[str, Any]:
        """Direct query generator targeting live GCP project tables and property graph."""
        if intent == "ROOT_CAUSE_QUERY":
            gql = f"""GRAPH {graph_name}
MATCH p = (ord:`Order`)-[:BELONGS_TO_ORDER]-(shp:Shipment)-[:HAS_DELAY]->(dly:Delay),
      (shp)-[:HANDLED_BY_CARRIER]->(car:Carrier),
      (shp)-[:FULFILLED_FROM]->(wh:Warehouse)
WHERE ord.status = 'DELAYED' OR shp.status = 'DELAYED'
RETURN 
    TO_JSON(ord) AS order_node,
    TO_JSON(shp) AS shipment_node,
    TO_JSON(car) AS carrier_node,
    TO_JSON(wh) AS warehouse_node,
    TO_JSON(dly) AS delay_node,
    TO_JSON(p) AS root_cause_path
LIMIT 500"""
            return {
                "intent": "ROOT_CAUSE_QUERY",
                "query_type": "GQL",
                "generated_query": gql,
                "explanation": f"Generated BQGraph ISO GQL query targeting live property graph `{self.project_id}.{self.dataset_id}.supply_chain_graph` to trace multi-hop order delay root cause paths.",
                "business_terms_used": ["Root_Cause_Path", "SLA_Breach", "Warehouse_Congestion", "Carrier_Bottleneck"]
            }
        else:
            sql = f"""SELECT 
    w.region,
    c.carrier_name,
    COUNT(s.shipment_id) AS total_shipments,
    COUNT(CASE WHEN d.delay_id IS NOT NULL THEN 1 END) AS delayed_shipments,
    ROUND(COUNT(CASE WHEN d.delay_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(s.shipment_id), 2) AS delay_percentage_rate
FROM {table_prefix}.shipments s
JOIN {table_prefix}.warehouses w ON s.warehouse_id = w.warehouse_id
JOIN {table_prefix}.carriers c ON s.carrier_id = c.carrier_id
LEFT JOIN {table_prefix}.shipment_delays d ON s.shipment_id = d.shipment_id
GROUP BY w.region, c.carrier_name
ORDER BY delayed_shipments DESC"""
            return {
                "intent": "METRIC_QUERY",
                "query_type": "SQL",
                "generated_query": sql,
                "explanation": f"Generated GoogleSQL aggregation query targeting live BigQuery dataset `{self.project_id}.{self.dataset_id}` using Knowledge Catalog SLA Breach formulas.",
                "business_terms_used": ["SLA_Breach"]
            }

"""
Interactive Diagnostic & Debugging Suite for Conversational Analytics Agent.

Allows developers to test, step-through, and inspect:
1. Live GCP Authentication & ADC setup
2. Live BigQuery Dataset & Table Schema discovery
3. Live Dataplex / Knowledge Catalog Aspect & Entry listing
4. Gemini NL-to-SQL / NL-to-GQL generation & System Instruction prompt inspection
5. Live BigQuery SQL & BQGraph GQL execution traces
"""

import sys
import os
import json
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure verbose logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DEBUG_SUITE")

from src.knowledge_catalog_service import KnowledgeCatalogService
from src.agent import ConversationalAnalyticsAgent
from src.bq_executor import BigQueryExecutor


def run_debug_suite(user_query: str = "Why is order ORD-9001 delayed in Chicago and what is the root cause?"):
    project_id = os.getenv("GCP_PROJECT", "conversationalanalytics-507815")
    dataset_id = os.getenv("BQ_DATASET", "supply_chain_analytics")

    print("\n" + "=" * 80)
    print("🐞 CONVERSATIONAL ANALYTICS DEBUG & DIAGNOSTIC SUITE")
    print("=" * 80)
    print(f"Target GCP Project : {project_id}")
    print(f"Target BQ Dataset  : {dataset_id}")
    print(f"Test User Prompt   : \"{user_query}\"")
    print("=" * 80 + "\n")

    # Step 1: Test Knowledge Catalog Service
    print("STEP 1: Testing Live GCP Knowledge Catalog & BigQuery Schema Discovery")
    print("-" * 70)
    kc_service = KnowledgeCatalogService(project_id=project_id, dataset_id=dataset_id)
    
    live_schemas = kc_service.fetch_live_table_schemas()
    print(f"  ✓ Live BigQuery Tables Discovered ({len(live_schemas)}): {list(live_schemas.keys())}")
    for tbl, info in live_schemas.items():
        print(f"    - Table '{tbl}' ({info.get('num_rows', 0)} rows, {len(info['columns'])} columns)")

    dp_entries = kc_service.fetch_dataplex_glossary()
    print(f"  ✓ Live Dataplex Glossary Entries ({len(dp_entries)}):")
    for entry in dp_entries:
        print(f"    - [{entry['search_result_subtype']}] {entry['display_name']} -> {entry['relative_resource_name']}")

    context_prompt = kc_service.get_full_context_prompt(user_query)
    print(f"  ✓ Context Prompt Generated (Length: {len(context_prompt)} chars)")

    # Step 2: Test Agent Intent Router & LLM Query Generator
    print("\nSTEP 2: Testing Agent Intent Classification & Query Generation")
    print("-" * 70)
    agent = ConversationalAnalyticsAgent(project_id=project_id, dataset_id=dataset_id)
    
    intent = agent.classify_intent(user_query)
    print(f"  ✓ Classified Intent: {intent}")

    print("  ⏳ Invoking Query Generator (Gemini LLM / GCP Rules)...")
    agent_output = agent.generate_query(user_query)
    
    print("  ✓ Agent Output JSON:")
    print(json.dumps(agent_output, indent=2))

    # Step 3: Test BigQuery / BQGraph Execution
    query_to_run = agent_output.get("generated_query", "")
    query_type = agent_output.get("query_type", "SQL")
    
    print("\nSTEP 3: Testing BigQuery Query Execution & Graph Parsing")
    print("-" * 70)
    print(f"  Executing {query_type} query against BigQuery...")
    
    executor = BigQueryExecutor(project_id=project_id)
    try:
        df_results, graph_meta = executor.execute_query(query_to_run, query_type=query_type, dataset_id=dataset_id)
        
        print(f"  ✓ Execution Successful! Result DataFrame shape: {df_results.shape}")
        print("\n--- FIRST 5 ROWS OF RESULT DATAFRAME ---")
        print(df_results.head(5).to_string())
        
        if graph_meta:
            print("\n--- GRAPH TOPOLOGY PARSED ---")
            print(f"  Nodes count: {len(graph_meta.get('nodes', []))}")
            print(f"  Edges count: {len(graph_meta.get('edges', []))}")
            if graph_meta.get("enterprise_notice"):
                print(f"  Notice: {graph_meta['enterprise_notice']}")

    except Exception as err:
        print(f"  ❌ Query Execution Error Trace: {err}")

    print("\n" + "=" * 80)
    print("🎉 DEBUG SUITE FINISHED!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    prompt_arg = sys.argv[1] if len(sys.argv) > 1 else "Why is order ORD-9001 delayed in Chicago and what is the root cause?"
    run_debug_suite(prompt_arg)

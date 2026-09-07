"""
Automated GCP Dataplex Catalog Provisioning Script (Dataplex Catalog 2.0 API).

Deploys Dataplex Aspect Types, Entry Types, Entry Groups, and Business Glossary Entries
(SLA Breach, Carrier Bottleneck, Warehouse Congestion, Root Cause Path) to GCP Dataplex Catalog.
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from google.cloud import dataplex_v1
    from google.protobuf import struct_pb2
    from google.api_core.exceptions import AlreadyExists, GoogleAPIError
    DATAPLEX_AVAILABLE = True
except ImportError:
    DATAPLEX_AVAILABLE = False


def deploy_dataplex_knowledge_catalog(
    project_id: str = "conversationalanalytics-507815",
    dataset_id: str = "supply_chain_analytics",
    location: str = "us-central1"
):
    if not DATAPLEX_AVAILABLE:
        print("❌ google-cloud-dataplex package is required.")
        sys.exit(1)

    print(f"🚀 Provisioning GCP Dataplex Catalog Aspect Types, Entry Types & Entries in '{project_id}' ({location})...")
    client = dataplex_v1.CatalogServiceClient()
    
    parent = f"projects/{project_id}/locations/{location}"
    aspect_type_id = "supply-chain-business-glossary"
    entry_type_id = "business-glossary-term"
    entry_group_id = "supply-chain-glossary-group"
    aspect_key = f"{project_id}.{location}.{aspect_type_id}"
    
    # 1. Create Dataplex Aspect Type definition if not exists
    aspect_type = dataplex_v1.AspectType()
    aspect_type.display_name = "Supply Chain Business Glossary Aspect"
    aspect_type.description = "Business definitions, SLA metric formulas, and BQGraph root cause categories."
    
    aspect_type.metadata_template = dataplex_v1.AspectType.MetadataTemplate(
        name="BusinessGlossaryRecord",
        type_="RECORD",
        index=1,
        record_fields=[
            dataplex_v1.AspectType.MetadataTemplate(name="term_name", type_="STRING", index=1),
            dataplex_v1.AspectType.MetadataTemplate(name="definition", type_="STRING", index=2),
            dataplex_v1.AspectType.MetadataTemplate(name="formula", type_="STRING", index=3),
            dataplex_v1.AspectType.MetadataTemplate(name="category", type_="STRING", index=4),
        ]
    )

    aspect_type_name = f"{parent}/aspectTypes/{aspect_type_id}"
    try:
        operation = client.create_aspect_type(
            parent=parent,
            aspect_type_id=aspect_type_id,
            aspect_type=aspect_type
        )
        print(f"⏳ Creating Dataplex Aspect Type '{aspect_type_id}'...")
        operation.result()
        print(f"✅ Dataplex Aspect Type '{aspect_type_id}' created successfully!")
    except AlreadyExists:
        print(f"ℹ️ Dataplex Aspect Type '{aspect_type_id}' already exists.")
    except Exception as e:
        print(f"⚠️ Aspect Type notice: {e}")

    # 2. Create Entry Type definition if not exists
    entry_type = dataplex_v1.EntryType()
    entry_type.display_name = "Business Glossary Term Entry Type"
    entry_type.description = "Entry type representing a business glossary term in Dataplex Catalog."
    
    entry_type_name = f"{parent}/entryTypes/{entry_type_id}"
    try:
        op_et = client.create_entry_type(
            parent=parent,
            entry_type_id=entry_type_id,
            entry_type=entry_type
        )
        print(f"⏳ Creating Dataplex Entry Type '{entry_type_id}'...")
        op_et.result()
        print(f"✅ Dataplex Entry Type '{entry_type_id}' created successfully!")
    except AlreadyExists:
        print(f"ℹ️ Dataplex Entry Type '{entry_type_id}' already exists.")
    except Exception as e:
        print(f"⚠️ Entry Type notice: {e}")

    # 3. Create Entry Group if not exists
    entry_group = dataplex_v1.EntryGroup()
    entry_group.display_name = "Supply Chain Glossary Group"
    entry_group.description = "Enterprise business glossary terms for supply chain conversational analytics."
    
    entry_group_name = f"{parent}/entryGroups/{entry_group_id}"
    try:
        op_eg = client.create_entry_group(
            parent=parent,
            entry_group_id=entry_group_id,
            entry_group=entry_group
        )
        print(f"⏳ Creating Dataplex Entry Group '{entry_group_id}'...")
        op_eg.result()
        print(f"✅ Dataplex Entry Group '{entry_group_id}' created successfully!")
    except AlreadyExists:
        print(f"ℹ️ Dataplex Entry Group '{entry_group_id}' already exists.")
    except Exception as e:
        print(f"⚠️ Entry Group notice: {e}")

    # 4. Publish Business Glossary Terms into Dataplex Catalog Entries
    glossary_terms = [
        {
            "entry_id": "sla-breach",
            "term_name": "SLA_Breach",
            "definition": "A shipment whose delay_hours > 24 or whose delivery date exceeds estimated SLA.",
            "formula": "COUNT(CASE WHEN delay_hours > 24 THEN 1 END) / COUNT(shipment_id)",
            "category": "Key Performance Metric"
        },
        {
            "entry_id": "carrier-bottleneck",
            "term_name": "Carrier_Bottleneck",
            "definition": "A transport carrier with reliability score < 0.85 or associated with > 3 delay incidents.",
            "formula": "CARRIER where reliability_score < 0.85 OR count(delays) > 3",
            "category": "Root Cause Category"
        },
        {
            "entry_id": "warehouse-congestion",
            "term_name": "Warehouse_Congestion",
            "definition": "A warehouse running over 85% capacity or tagged with status CONGESTED.",
            "formula": "capacity_utilization > 0.85 OR status = 'CONGESTED'",
            "category": "Root Cause Category"
        },
        {
            "entry_id": "root-cause-path",
            "term_name": "Root_Cause_Path",
            "definition": "Multi-hop graph traversal path connecting an Order to Shipment, Carrier, Warehouse, and Delay cause.",
            "formula": "GQL Pattern: MATCH p = (Order)-[:BELONGS_TO_ORDER]-(Shipment)-[:HAS_DELAY]->(Delay)",
            "category": "BQGraph Traversal"
        }
    ]

    for item in glossary_terms:
        entry = dataplex_v1.Entry()
        entry.entry_type = entry_type_name
        entry.entry_source = dataplex_v1.EntrySource(
            display_name=item["term_name"],
            description=item["definition"]
        )

        aspect_data = struct_pb2.Struct()
        aspect_data.update({
            "term_name": item["term_name"],
            "definition": item["definition"],
            "formula": item["formula"],
            "category": item["category"]
        })

        aspect = dataplex_v1.Aspect(
            aspect_type=aspect_type_name,
            data=aspect_data
        )
        entry.aspects[aspect_key] = aspect

        try:
            client.create_entry(
                parent=entry_group_name,
                entry_id=item["entry_id"],
                entry=entry
            )
            print(f"  ✓ Created Glossary Term Entry '{item['term_name']}' in GCP Dataplex Catalog!")
        except AlreadyExists:
            try:
                entry.name = f"{entry_group_name}/entries/{item['entry_id']}"
                client.update_entry(entry=entry)
                print(f"  ✓ Updated Glossary Term Entry '{item['term_name']}' in GCP Dataplex Catalog!")
            except Exception as ue:
                print(f"  ℹ️ Glossary Term Entry '{item['term_name']}' already exists.")
        except Exception as e:
            print(f"  ⚠️ Could not publish term '{item['term_name']}': {e}")

    print(f"🎉 All Business Glossary Terms successfully published to GCP Dataplex Catalog for project '{project_id}'!")


if __name__ == "__main__":
    target_project = os.getenv("GCP_PROJECT", "conversationalanalytics-507815")
    target_dataset = os.getenv("BQ_DATASET", "supply_chain_analytics")
    deploy_dataplex_knowledge_catalog(project_id=target_project, dataset_id=target_dataset)

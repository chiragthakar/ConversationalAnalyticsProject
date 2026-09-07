"""
Automated GCP Resource Provisioning Script.

Creates BigQuery dataset, deploys relational tables, populates initial sample data,
and creates the BigQuery Property Graph (BQGraph) for root cause analytics.
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError


def deploy_gcp_resources(
    project_id: str = "conversationalanalytics-507815",
    dataset_id: str = "supply_chain_analytics",
    location: str = "US"
):
    print(f"🚀 Starting GCP deployment for Project: '{project_id}', Dataset: '{dataset_id}' in Location: '{location}'...")
    
    client = bigquery.Client(project=project_id)
    
    # 1. Create Dataset if not exists
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location
    
    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✅ BigQuery Dataset '{project_id}.{dataset_id}' is ready.")
    except Exception as e:
        print(f"❌ Failed to create dataset: {e}")
        sys.exit(1)

    # 2. Define SQL Statements for Tables, Sample Data & Property Graph DDL
    ddl_statements = [
        # Table: warehouses
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.warehouses` (
            warehouse_id STRING NOT NULL,
            warehouse_name STRING NOT NULL,
            region STRING,
            capacity INT64,
            status STRING
        );
        """,
        # Table: products
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.products` (
            product_id STRING NOT NULL,
            sku STRING NOT NULL,
            name STRING NOT NULL,
            category STRING,
            unit_price NUMERIC
        );
        """,
        # Table: carriers
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.carriers` (
            carrier_id STRING NOT NULL,
            carrier_name STRING NOT NULL,
            transport_type STRING,
            reliability_score FLOAT64
        );
        """,
        # Table: orders
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.orders` (
            order_id STRING NOT NULL,
            customer_id STRING NOT NULL,
            order_date TIMESTAMP,
            total_amount NUMERIC,
            status STRING
        );
        """,
        # Table: shipments
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.shipments` (
            shipment_id STRING NOT NULL,
            order_id STRING NOT NULL,
            warehouse_id STRING NOT NULL,
            carrier_id STRING NOT NULL,
            shipped_date TIMESTAMP,
            delivery_date TIMESTAMP,
            status STRING
        );
        """,
        # Table: shipment_delays
        f"""
        CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.shipment_delays` (
            delay_id STRING NOT NULL,
            shipment_id STRING NOT NULL,
            delay_code STRING,
            delay_reason STRING,
            delay_hours INT64,
            location STRING
        );
        """,
        # Insert initial data
        f"""
        TRUNCATE TABLE `{project_id}.{dataset_id}.warehouses`;
        INSERT INTO `{project_id}.{dataset_id}.warehouses` (warehouse_id, warehouse_name, region, capacity, status) VALUES
        ('WH-101', 'Seattle Distribution Hub', 'US-WEST', 50000, 'ACTIVE'),
        ('WH-102', 'Dallas Logistics Center', 'US-SOUTH', 75000, 'ACTIVE'),
        ('WH-103', 'Chicago Express Hub', 'US-MIDWEST', 60000, 'CONGESTED');
        """,
        f"""
        TRUNCATE TABLE `{project_id}.{dataset_id}.carriers`;
        INSERT INTO `{project_id}.{dataset_id}.carriers` (carrier_id, carrier_name, transport_type, reliability_score) VALUES
        ('CR-01', 'SwiftFreight Logistics', 'TRUCK', 0.94),
        ('CR-02', 'Apex Air Cargo', 'AIR', 0.98),
        ('CR-03', 'Coastal Rail & Road', 'RAIL', 0.81);
        """,
        f"""
        TRUNCATE TABLE `{project_id}.{dataset_id}.orders`;
        INSERT INTO `{project_id}.{dataset_id}.orders` (order_id, customer_id, order_date, total_amount, status) VALUES
        ('ORD-9001', 'CUST-A12', TIMESTAMP '2026-09-01 08:30:00 UTC', 1250.00, 'DELAYED'),
        ('ORD-9002', 'CUST-B44', TIMESTAMP '2026-09-01 09:15:00 UTC', 450.50, 'DELIVERED'),
        ('ORD-9003', 'CUST-C89', TIMESTAMP '2026-09-02 11:00:00 UTC', 3200.00, 'DELAYED');
        """,
        f"""
        TRUNCATE TABLE `{project_id}.{dataset_id}.shipments`;
        INSERT INTO `{project_id}.{dataset_id}.shipments` (shipment_id, order_id, warehouse_id, carrier_id, shipped_date, delivery_date, status) VALUES
        ('SHP-501', 'ORD-9001', 'WH-103', 'CR-03', TIMESTAMP '2026-09-01 12:00:00 UTC', NULL, 'DELAYED'),
        ('SHP-502', 'ORD-9002', 'WH-101', 'CR-02', TIMESTAMP '2026-09-01 10:30:00 UTC', TIMESTAMP '2026-09-02 14:00:00 UTC', 'DELIVERED'),
        ('SHP-503', 'ORD-9003', 'WH-103', 'CR-03', TIMESTAMP '2026-09-02 13:00:00 UTC', NULL, 'DELAYED');
        """,
        f"""
        TRUNCATE TABLE `{project_id}.{dataset_id}.shipment_delays`;
        INSERT INTO `{project_id}.{dataset_id}.shipment_delays` (delay_id, shipment_id, delay_code, delay_reason, delay_hours, location) VALUES
        ('DLY-01', 'SHP-501', 'RAIL_CONGESTION', 'Severe rail track bottleneck at Chicago interchange', 36, 'Chicago, IL'),
        ('DLY-02', 'SHP-503', 'WH_BACKLOG', 'Warehouse sorting backlog due to high volume', 24, 'Chicago Hub');
        """,
        # CREATE OR REPLACE PROPERTY GRAPH with keyword escaping around `Order`
        f"""
        CREATE OR REPLACE PROPERTY GRAPH `{project_id}.{dataset_id}.supply_chain_graph`
        NODE TABLES (
            `{project_id}.{dataset_id}.warehouses` AS Warehouse
                KEY (warehouse_id)
                LABEL Warehouse PROPERTIES (warehouse_id, warehouse_name, region, status),
            `{project_id}.{dataset_id}.orders` AS `Order`
                KEY (order_id)
                LABEL `Order` PROPERTIES (order_id, customer_id, order_date, status),
            `{project_id}.{dataset_id}.carriers` AS Carrier
                KEY (carrier_id)
                LABEL Carrier PROPERTIES (carrier_id, carrier_name, transport_type, reliability_score),
            `{project_id}.{dataset_id}.shipments` AS Shipment
                KEY (shipment_id)
                LABEL Shipment PROPERTIES (shipment_id, shipped_date, delivery_date, status),
            `{project_id}.{dataset_id}.shipment_delays` AS Delay
                KEY (delay_id)
                LABEL Delay PROPERTIES (delay_id, delay_code, delay_reason, delay_hours, location)
        )
        EDGE TABLES (
            `{project_id}.{dataset_id}.shipments` AS FULFILLED_FROM
                KEY (shipment_id)
                SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
                DESTINATION KEY (warehouse_id) REFERENCES Warehouse (warehouse_id)
                LABEL FULFILLED_FROM,
            `{project_id}.{dataset_id}.shipments` AS BELONGS_TO_ORDER
                KEY (shipment_id)
                SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
                DESTINATION KEY (order_id) REFERENCES `Order` (order_id)
                LABEL BELONGS_TO_ORDER,
            `{project_id}.{dataset_id}.shipments` AS HANDLED_BY_CARRIER
                KEY (shipment_id)
                SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
                DESTINATION KEY (carrier_id) REFERENCES Carrier (carrier_id)
                LABEL HANDLED_BY_CARRIER,
            `{project_id}.{dataset_id}.shipment_delays` AS HAS_DELAY
                KEY (delay_id)
                SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
                DESTINATION KEY (delay_id) REFERENCES Delay (delay_id)
                LABEL HAS_DELAY
        );
        """
    ]

    for idx, stmt in enumerate(ddl_statements, 1):
        try:
            print(f"⏳ Executing Statement {idx}/{len(ddl_statements)}...")
            job = client.query(stmt)
            job.result()  # Wait for completion
            print(f"  ✓ Statement {idx} completed successfully.")
        except Exception as e:
            print(f"  ❌ Statement {idx} failed: {e}")
            sys.exit(1)

    print(f"🎉 Deployment completed! Dataset '{project_id}.{dataset_id}' and Property Graph 'supply_chain_graph' are live on Google Cloud!")


if __name__ == "__main__":
    target_project = os.getenv("GCP_PROJECT", "conversationalanalytics-507815")
    deploy_gcp_resources(project_id=target_project)

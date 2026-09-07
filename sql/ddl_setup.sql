-- ============================================================================
-- Conversational Analytics DDL Setup: Relational Tables & BigQuery Property Graph
-- Project / Dataset: <PROJECT_ID>.<DATASET_ID>
-- ============================================================================

-- 1. Create Datasets (Adjust Region as needed, e.g., US or europe-west1)
-- CREATE SCHEMA IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>`
-- OPTIONS(location="US");

-- ----------------------------------------------------------------------------
-- Relational Tables
-- ----------------------------------------------------------------------------

-- Table: Warehouses
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.warehouses` (
    warehouse_id STRING NOT NULL,
    warehouse_name STRING NOT NULL,
    region STRING,
    capacity INT64,
    status STRING
);

-- Table: Products
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.products` (
    product_id STRING NOT NULL,
    sku STRING NOT NULL,
    name STRING NOT NULL,
    category STRING,
    unit_price NUMERIC
);

-- Table: Carriers
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.carriers` (
    carrier_id STRING NOT NULL,
    carrier_name STRING NOT NULL,
    transport_type STRING,
    reliability_score FLOAT64
);

-- Table: Orders
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.orders` (
    order_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    order_date TIMESTAMP,
    total_amount NUMERIC,
    status STRING
);

-- Table: Shipments
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.shipments` (
    shipment_id STRING NOT NULL,
    order_id STRING NOT NULL,
    warehouse_id STRING NOT NULL,
    carrier_id STRING NOT NULL,
    shipped_date TIMESTAMP,
    delivery_date TIMESTAMP,
    status STRING
);

-- Table: Shipment Delays
CREATE TABLE IF NOT EXISTS `<PROJECT_ID>.<DATASET_ID>.shipment_delays` (
    delay_id STRING NOT NULL,
    shipment_id STRING NOT NULL,
    delay_code STRING,
    delay_reason STRING,
    delay_hours INT64,
    location STRING
);

-- ----------------------------------------------------------------------------
-- BQGraph: Property Graph Definition for Root Cause Analytics
-- Note: BigQuery property graph DDL syntax enforces keys and explicit node/edge bindings.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE PROPERTY GRAPH `<PROJECT_ID>.<DATASET_ID>.supply_chain_graph`
NODE TABLES (
    `<PROJECT_ID>.<DATASET_ID>.warehouses` AS Warehouse
        KEY (warehouse_id)
        LABEL Warehouse PROPERTIES (warehouse_id, warehouse_name, region, status),
    `<PROJECT_ID>.<DATASET_ID>.orders` AS Order
        KEY (order_id)
        LABEL Order PROPERTIES (order_id, customer_id, order_date, status),
    `<PROJECT_ID>.<DATASET_ID>.carriers` AS Carrier
        KEY (carrier_id)
        LABEL Carrier PROPERTIES (carrier_id, carrier_name, transport_type, reliability_score),
    `<PROJECT_ID>.<DATASET_ID>.shipments` AS Shipment
        KEY (shipment_id)
        LABEL Shipment PROPERTIES (shipment_id, shipped_date, delivery_date, status),
    `<PROJECT_ID>.<DATASET_ID>.shipment_delays` AS Delay
        KEY (delay_id)
        LABEL Delay PROPERTIES (delay_id, delay_code, delay_reason, delay_hours, location)
)
EDGE TABLES (
    `<PROJECT_ID>.<DATASET_ID>.shipments` AS FULFILLED_FROM
        KEY (shipment_id)
        SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
        DESTINATION KEY (warehouse_id) REFERENCES Warehouse (warehouse_id)
        LABEL FULFILLED_FROM,
    `<PROJECT_ID>.<DATASET_ID>.shipments` AS BELONGS_TO_ORDER
        KEY (shipment_id)
        SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
        DESTINATION KEY (order_id) REFERENCES Order (order_id)
        LABEL BELONGS_TO_ORDER,
    `<PROJECT_ID>.<DATASET_ID>.shipments` AS HANDLED_BY_CARRIER
        KEY (shipment_id)
        SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
        DESTINATION KEY (carrier_id) REFERENCES Carrier (carrier_id)
        LABEL HANDLED_BY_CARRIER,
    `<PROJECT_ID>.<DATASET_ID>.shipment_delays` AS HAS_DELAY
        KEY (delay_id)
        SOURCE KEY (shipment_id) REFERENCES Shipment (shipment_id)
        DESTINATION KEY (delay_id) REFERENCES Delay (delay_id)
        LABEL HAS_DELAY
);

-- ----------------------------------------------------------------------------
-- Sample Mock Data Ingestion Script (For quick local testing)
-- ----------------------------------------------------------------------------

INSERT INTO `<PROJECT_ID>.<DATASET_ID>.warehouses` (warehouse_id, warehouse_name, region, capacity, status) VALUES
('WH-101', 'Seattle Distribution Hub', 'US-WEST', 50000, 'ACTIVE'),
('WH-102', 'Dallas Logistics Center', 'US-SOUTH', 75000, 'ACTIVE'),
('WH-103', 'Chicago Express Hub', 'US-MIDWEST', 60000, 'CONGESTED');

INSERT INTO `<PROJECT_ID>.<DATASET_ID>.carriers` (carrier_id, carrier_name, transport_type, reliability_score) VALUES
('CR-01', 'SwiftFreight Logistics', 'TRUCK', 0.94),
('CR-02', 'Apex Air Cargo', 'AIR', 0.98),
('CR-03', 'Coastal Rail & Road', 'RAIL', 0.81);

INSERT INTO `<PROJECT_ID>.<DATASET_ID>.orders` (order_id, customer_id, order_date, total_amount, status) VALUES
('ORD-9001', 'CUST-A12', TIMESTAMP '2026-09-01 08:30:00 UTC', 1250.00, 'DELAYED'),
('ORD-9002', 'CUST-B44', TIMESTAMP '2026-09-01 09:15:00 UTC', 450.50, 'DELIVERED'),
('ORD-9003', 'CUST-C89', TIMESTAMP '2026-09-02 11:00:00 UTC', 3200.00, 'DELAYED');

INSERT INTO `<PROJECT_ID>.<DATASET_ID>.shipments` (shipment_id, order_id, warehouse_id, carrier_id, shipped_date, delivery_date, status) VALUES
('SHP-501', 'ORD-9001', 'WH-103', 'CR-03', TIMESTAMP '2026-09-01 12:00:00 UTC', NULL, 'DELAYED'),
('SHP-502', 'ORD-9002', 'WH-101', 'CR-02', TIMESTAMP '2026-09-01 10:30:00 UTC', TIMESTAMP '2026-09-02 14:00:00 UTC', 'DELIVERED'),
('SHP-503', 'ORD-9003', 'WH-103', 'CR-03', TIMESTAMP '2026-09-02 13:00:00 UTC', NULL, 'DELAYED');

INSERT INTO `<PROJECT_ID>.<DATASET_ID>.shipment_delays` (delay_id, shipment_id, delay_code, delay_reason, delay_hours, location) VALUES
('DLY-01', 'SHP-501', 'RAIL_CONGESTION', 'Severe rail track bottleneck at Chicago interchange', 36, 'Chicago, IL'),
('DLY-02', 'SHP-503', 'WH_BACKLOG', 'Warehouse sorting backlog due to high volume', 24, 'Chicago Hub');

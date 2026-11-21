-- ============================================================================
-- 01_create_tables.sql
-- Registro de tablas externas (Parquet) en AWS Glue Data Catalog / Athena
-- Reemplazar <TU_BUCKET> por el nombre de tu bucket S3 antes de ejecutar.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS retail_lakehouse_db;

-- 1. Maestro de productos (Silver)
CREATE EXTERNAL TABLE IF NOT EXISTS retail_lakehouse_db.maestro_productos (
    sku_id              STRING,
    nombre_producto     STRING,
    categoria           STRING,
    precio_catalogo_pen DOUBLE
)
STORED AS PARQUET
LOCATION 's3://<TU_BUCKET>/silver/maestro_productos/';

-- 2. Ventas POS limpias (Silver - particionado por fecha)
CREATE EXTERNAL TABLE IF NOT EXISTS retail_lakehouse_db.ventas_pos_silver (
    ticket_id       STRING,
    fecha_venta     STRING,
    timestamp_venta TIMESTAMP,
    tienda_id       STRING,
    formato         STRING,
    sku_id          STRING,
    cantidad        BIGINT,
    precio_unitario DOUBLE,
    monto_total     DOUBLE,
    medio_pago      STRING
)
PARTITIONED BY (
    anio STRING,
    mes  STRING,
    dia  STRING
)
STORED AS PARQUET
LOCATION 's3://<TU_BUCKET>/silver/ventas_pos/';

-- 3. Cierre contable ERP (Silver - particionado por año/mes)
CREATE EXTERNAL TABLE IF NOT EXISTS retail_lakehouse_db.cierre_erp_silver (
    fecha_cierre      STRING,
    tienda_id         STRING,
    monto_total_erp   DOUBLE,
    total_tickets_erp BIGINT,
    estado_cierre     STRING
)
PARTITIONED BY (
    anio STRING,
    mes  STRING
)
STORED AS PARQUET
LOCATION 's3://<TU_BUCKET>/silver/cierre_erp/';

-- 4. Registros rechazados (Quarantine - particionado por fecha)
CREATE EXTERNAL TABLE IF NOT EXISTS retail_lakehouse_db.ventas_pos_quarantine (
    ticket_id       STRING,
    fecha_venta     STRING,
    timestamp_venta STRING,
    tienda_id       STRING,
    formato         STRING,
    sku_id          STRING,
    cantidad        BIGINT,
    precio_unitario DOUBLE,
    monto_total     DOUBLE,
    medio_pago      STRING,
    motivo_rechazo  STRING
)
PARTITIONED BY (
    anio STRING,
    mes  STRING,
    dia  STRING
)
STORED AS PARQUET
LOCATION 's3://<TU_BUCKET>/quarantine/ventas_pos_rechazadas/';

-- Descubrimiento automático de particiones en AWS Glue Data Catalog
MSCK REPAIR TABLE retail_lakehouse_db.ventas_pos_silver;
MSCK REPAIR TABLE retail_lakehouse_db.cierre_erp_silver;
MSCK REPAIR TABLE retail_lakehouse_db.ventas_pos_quarantine;
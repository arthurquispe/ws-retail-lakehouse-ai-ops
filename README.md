# 🛒 AWS Retail Lakehouse & AI-Assisted DataOps

Arquitectura **Lakehouse (Medallion)** en **AWS** orientada al sector retail para la ingesta de ventas diarias, validación automatizada de calidad de datos, conciliación financiera (**POS vs. ERP**) y diagnóstico asistido de incidencias mediante un **Agente de IA con MCP y Amazon Bedrock** bajo supervisión humana (*Human-in-the-Loop*).

---

## 🎯 Problema de Negocio
En operaciones de retail de alto volumen, las cargas diarias de transacciones suelen presentar duplicados, SKUs no catalogados o descalces entre los sistemas de punto de venta (POS) y el cierre contable (ERP). Este proyecto automatiza:
1. La ingestión, estandarización a formato columnar (**Parquet**) y aislamiento de registros corruptos (*Quarantine*).
2. La conciliación diaria entre fuentes en **Amazon Athena** y la generación de alertas serverless con **AWS Lambda**.
3. El diagnóstico inicial de causas raíz mediante un **Agente IA** conectado a herramientas **MCP de solo lectura**, reduciendo el tiempo operativo de atención de incidencias sin comprometer la seguridad de los datos.

---

## 🏗️ Arquitectura del Sistema

```mermaid
flowchart LR
    A[Fuentes Retail<br/>POS / ERP / Maestro] --> B[(AWS S3<br/>Bronze / Raw)]
    B --> C[ETL Python + DQ<br/>Validación y Limpieza]
    C -->|Válidos| D[(AWS S3<br/>Silver / Parquet)]
    C -->|Anómalos| Q[(AWS S3<br/>Quarantine)]
    D --> E[AWS Glue Data Catalog]
    Q --> E
    E --> F[Amazon Athena<br/>Vistas Gold y Conciliación]
    F --> G[AWS Lambda<br/>Monitoreo y Alertas]
    G --> H[Servidor MCP<br/>Herramientas Solo Lectura]
    H --> I[Agente IA<br/>Amazon Bedrock]
    I --> J{Supervisión Humana<br/>HITL}
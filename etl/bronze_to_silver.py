"""
Pipeline ETL: Capa Bronze (CSV) -> Capa Silver (Parquet particionado) + Quarantine.

Uso local:
    python etl/bronze_to_silver.py

Uso con carga directa a AWS S3 (requiere credenciales AWS y .env configurado):
    python etl/bronze_to_silver.py --upload-s3
"""

import argparse
import os
import sys
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv

# Permite importar dq_rules ejecutando desde la raíz del proyecto
sys.path.append(str(Path(__file__).resolve().parent))
from dq_rules import validate_pos_sales  # noqa: E402

BRONZE_DIR = Path("data/bronze")
SILVER_DIR = Path("data/silver")
QUARANTINE_DIR = Path("data/quarantine")


def add_partition_columns(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """Agrega columnas de partición anio/mes/dia para optimizar consultas en Athena."""
    dt = pd.to_datetime(df[date_col])
    df = df.copy()
    df["anio"] = dt.dt.year.astype(str)
    df["mes"] = dt.dt.strftime("%m")
    df["dia"] = dt.dt.strftime("%d")
    return df


def upload_directory_to_s3(local_dir: Path, bucket: str, s3_prefix: str, region: str) -> int:
    """Sube recursivamente una carpeta local a un prefijo de AWS S3."""
    s3_client = boto3.client("s3", region_name=region)
    uploaded = 0
    for file_path in local_dir.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_dir).as_posix()
            s3_key = f"{s3_prefix}/{relative_path}"
            s3_client.upload_file(str(file_path), bucket, s3_key)
            uploaded += 1
    return uploaded


def run_etl(upload_s3: bool = False) -> None:
    print("Iniciando pipeline ETL Bronze -> Silver...")

    # 1. Lectura de capa Bronze
    products = pd.read_csv(BRONZE_DIR / "maestro_productos.csv")
    pos_raw = pd.read_csv(BRONZE_DIR / "ventas_pos.csv")
    erp_raw = pd.read_csv(BRONZE_DIR / "cierre_erp.csv")

    # 2. Validación de calidad de datos sobre ventas_pos
    pos_valid, pos_quarantine = validate_pos_sales(pos_raw, products)

    # 3. Tipificación y columnas de partición
    pos_valid["timestamp_venta"] = pd.to_datetime(pos_valid["timestamp_venta"])
    pos_valid = add_partition_columns(pos_valid, "fecha_venta")
    erp_clean = add_partition_columns(erp_raw, "fecha_cierre")

    # 4. Escritura en formato Parquet (compresión Snappy por defecto)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Escritura en formato Parquet (compresión Snappy por defecto)
    (SILVER_DIR / "maestro_productos").mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    products.to_parquet(SILVER_DIR / "maestro_productos" / "maestro_productos.parquet", index=False)

    products.to_parquet(SILVER_DIR / "maestro_productos" / "maestro_productos.parquet", index=False)
    pos_valid.to_parquet(
        SILVER_DIR / "ventas_pos",
        index=False,
        partition_cols=["anio", "mes", "dia"],
        existing_data_behavior="delete_matching",
    )
    erp_clean.to_parquet(
        SILVER_DIR / "cierre_erp",
        index=False,
        partition_cols=["anio", "mes"],
        existing_data_behavior="delete_matching",
    )

    if not pos_quarantine.empty:
        pos_quarantine = add_partition_columns(pos_quarantine, "fecha_venta")
        pos_quarantine.to_parquet(
            QUARANTINE_DIR / "ventas_pos_rechazadas",
            index=False,
            partition_cols=["anio", "mes", "dia"],
            existing_data_behavior="delete_matching",
        )

    # 5. Reporte de métricas de calidad
    total_raw = len(pos_raw)
    total_valid = len(pos_valid)
    total_quarantine = len(pos_quarantine)
    dq_rate = (total_valid / total_raw) * 100

    print("\n--- Resumen de Calidad de Datos (ventas_pos) ---")
    print(f"Total registros Bronze    : {total_raw:,}")
    print(f"Registros válidos Silver  : {total_valid:,} ({dq_rate:.2f}%)")
    print(f"Registros en Quarantine   : {total_quarantine:,}")
    if not pos_quarantine.empty:
        print("\nDesglose por motivo de rechazo:")
        print(pos_quarantine["motivo_rechazo"].value_counts().to_string())

    # 6. Carga opcional a AWS S3
    if upload_s3:
        load_dotenv()
        bucket = os.getenv("S3_BUCKET_NAME")
        region = os.getenv("AWS_REGION", "us-east-1")
        if not bucket:
            raise ValueError("Define S3_BUCKET_NAME en tu archivo .env antes de usar --upload-s3.")

        print(f"\nSubiendo capas del Lakehouse a s3://{bucket}/ ...")
        n_bronze = upload_directory_to_s3(BRONZE_DIR, bucket, "bronze", region)
        n_silver = upload_directory_to_s3(SILVER_DIR, bucket, "silver", region)
        n_quarantine = upload_directory_to_s3(QUARANTINE_DIR, bucket, "quarantine", region)
        print(f"Carga completa -> bronze: {n_bronze}, silver: {n_silver}, quarantine: {n_quarantine} archivos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL Bronze a Silver en formato Parquet.")
    parser.add_argument(
        "--upload-s3",
        action="store_true",
        help="Sube las capas bronze, silver y quarantine al bucket definido en .env",
    )
    args = parser.parse_args()
    run_etl(upload_s3=args.upload_s3)
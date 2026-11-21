"""
Reglas de Calidad de Datos (Data Quality) para transacciones POS.
Separa registros válidos (capa Silver) de registros anómalos (capa Quarantine)
registrando el motivo exacto de rechazo para trazabilidad y diagnóstico.
"""

from typing import Tuple
import pandas as pd


def validate_pos_sales(
    pos_df: pd.DataFrame, products_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aplica reglas de calidad sobre ventas_pos y retorna (valid_df, quarantine_df).
    """
    df = pos_df.copy()
    valid_skus = set(products_df["sku_id"].dropna().unique())

    # 1. ticket_id nulo
    rule_null_ticket = df["ticket_id"].isna() | (df["ticket_id"].astype(str).str.strip() == "")

    # 2. ticket_id duplicado (solo sobre no nulos; conserva la primera aparición)
    rule_dup_ticket = (~rule_null_ticket) & df.duplicated(subset=["ticket_id"], keep="first")

    # 3. Precios, cantidades o montos no positivos
    rule_invalid_values = (
        (df["precio_unitario"] <= 0)
        | (df["cantidad"] <= 0)
        | (df["monto_total"] <= 0)
    )

    # 4. Integridad referencial: SKU inexistente en maestro_productos
    rule_invalid_sku = ~df["sku_id"].isin(valid_skus)

    # 5. Consistencia aritmética: monto_total vs precio_unitario * cantidad
    expected_amount = (df["precio_unitario"] * df["cantidad"]).round(2)
    rule_math_mismatch = (df["monto_total"] - expected_amount).abs() > 0.01

    # Construcción de columna motivo_rechazo (permite detectar múltiples fallos por fila)
    reasons = pd.Series("", index=df.index, dtype="object")
    rules = [
        (rule_null_ticket, "TICKET_ID_NULO"),
        (rule_dup_ticket, "TICKET_DUPLICADO"),
        (rule_invalid_values, "PRECIO_CANTIDAD_O_MONTO_INVALIDO"),
        (rule_invalid_sku, "SKU_NO_CATALOGADO"),
        (rule_math_mismatch, "INCONSISTENCIA_CALCULO_MONTO"),
    ]

    for mask, label in rules:
        reasons = reasons.where(~mask, reasons.where(reasons == "", reasons + "|") + label)

    is_invalid = reasons != ""

    quarantine_df = df.loc[is_invalid].copy()
    quarantine_df["motivo_rechazo"] = reasons.loc[is_invalid]

    valid_df = df.loc[~is_invalid].copy()

    return valid_df, quarantine_df
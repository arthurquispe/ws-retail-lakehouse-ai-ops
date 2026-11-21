"""
Generador de datos sintéticos para el Retail Lakehouse (Capa Bronze).

Genera 3 tablas CSV en data/bronze/:
  1. maestro_productos.csv : Catálogo de SKUs y categorías retail.
  2. ventas_pos.csv        : Transacciones de punto de venta (con anomalías DQ inyectadas).
  3. cierre_erp.csv        : Totales diarios contables por tienda (con brecha de conciliación).
"""

from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
OUTPUT_DIR = Path("data/bronze")
START_DATE = "2026-10-16"
NUM_DAYS = 30
DAILY_TX_PER_STORE = 500  # 30 días * 6 tiendas * 500 = 90,000 registros base


def build_product_master() -> pd.DataFrame:
    """Crea un catálogo realista de productos de supermercado."""
    products = [
        ("SKU-1001", "Leche Evaporada Entera 400g", "Lácteos", 4.50),
        ("SKU-1002", "Yogurt Griego Natural 1kg", "Lácteos", 14.90),
        ("SKU-1003", "Queso Edam Tajado 200g", "Lácteos", 11.50),
        ("SKU-2001", "Arroz Extra Costeño 5kg", "Abarrotes", 24.90),
        ("SKU-2002", "Aceite Vegetal Primor 1L", "Abarrotes", 9.80),
        ("SKU-2003", "Azúcar Rubia Cartavio 1kg", "Abarrotes", 4.20),
        ("SKU-2004", "Fideos Spaghetti Don Vittorio 500g", "Abarrotes", 3.60),
        ("SKU-3001", "Pechuga de Pollo Fresca 1kg", "Carnes y Aves", 18.50),
        ("SKU-3002", "Bife Angosto Nacional 1kg", "Carnes y Aves", 46.90),
        ("SKU-3003", "Filete de Salmón 500g", "Pescados", 38.00),
        ("SKU-4001", "Agua Mineral Sin Gas 2.5L", "Bebidas", 3.50),
        ("SKU-4002", "Gaseosa Inca Kola 1.5L", "Bebidas", 7.20),
        ("SKU-4003", "Vino Malbec Reserva 750ml", "Bebidas", 42.00),
        ("SKU-5001", "Detergente Líquido Ariel 2L", "Limpieza", 32.90),
        ("SKU-5002", "Papel Higiénico Elite 12un", "Limpieza", 19.50),
        ("SKU-6001", "Palta Hass 1kg", "Frutas y Verduras", 11.90),
        ("SKU-6002", "Manzana Israel 1kg", "Frutas y Verduras", 6.40),
        ("SKU-6003", "Pan Integral Artesanal 500g", "Panadería", 8.90),
    ]
    return pd.DataFrame(
        products,
        columns=["sku_id", "nombre_producto", "categoria", "precio_catalogo_pen"],
    )


def build_stores() -> pd.DataFrame:
    """Catálogo interno de tiendas y formatos retail."""
    return pd.DataFrame(
        [
            ("T01", "Wong Miraflores", "Supermercado Premium"),
            ("T02", "Wong La Molina", "Supermercado Premium"),
            ("T03", "Wong San Isidro", "Supermercado Premium"),
            ("T04", "Metro Surco", "Hipermercado"),
            ("T05", "Metro San Miguel", "Hipermercado"),
            ("T06", "Metro Independencia", "Hipermercado"),
        ],
        columns=["tienda_id", "nombre_tienda", "formato"],
    )


def generate_clean_pos_sales(
    products: pd.DataFrame, stores: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Genera transacciones limpias de POS para 30 días."""
    dates = pd.date_range(start=START_DATE, periods=NUM_DAYS, freq="D")
    n_rows = NUM_DAYS * len(stores) * DAILY_TX_PER_STORE

    # Combinaciones fecha x tienda
    date_grid = np.repeat(dates.strftime("%Y-%m-%d"), len(stores) * DAILY_TX_PER_STORE)
    store_idx = np.tile(np.repeat(np.arange(len(stores)), DAILY_TX_PER_STORE), NUM_DAYS)

    # Selección aleatoria de productos, cantidades y medios de pago
    prod_idx = rng.integers(0, len(products), size=n_rows)
    quantities = rng.choice([1, 2, 3, 4, 5], size=n_rows, p=[0.48, 0.27, 0.14, 0.07, 0.04])
    payment_methods = rng.choice(
        ["Tarjeta Crédito", "Tarjeta Débito", "Efectivo", "Billetera Digital"],
        size=n_rows,
        p=[0.38, 0.32, 0.15, 0.15],
    )

    # Horas aleatorias entre 08:00 y 22:00
    seconds_offset = rng.integers(8 * 3600, 22 * 3600, size=n_rows)
    timestamps = pd.to_datetime(date_grid) + pd.to_timedelta(seconds_offset, unit="s")

    prices = products["precio_catalogo_pen"].to_numpy()[prod_idx]
    amounts = np.round(prices * quantities, 2)

    df = pd.DataFrame(
        {
            "ticket_id": [f"TCK-{i:07d}" for i in range(1, n_rows + 1)],
            "fecha_venta": date_grid,
            "timestamp_venta": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
            "tienda_id": stores["tienda_id"].to_numpy()[store_idx],
            "formato": stores["formato"].to_numpy()[store_idx],
            "sku_id": products["sku_id"].to_numpy()[prod_idx],
            "cantidad": quantities,
            "precio_unitario": prices,
            "monto_total": amounts,
            "medio_pago": payment_methods,
        }
    )
    return df


def build_erp_closing(clean_pos: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el cierre diario del ERP a partir de las ventas limpias
    e inyecta una brecha contable controlada el 2026-11-12 en la tienda T04.
    """
    erp = (
        clean_pos.groupby(["fecha_venta", "tienda_id"], as_index=False)
        .agg(
            monto_total_erp=("monto_total", "sum"),
            total_tickets_erp=("ticket_id", "nunique"),
        )
        .rename(columns={"fecha_venta": "fecha_cierre"})
    )
    erp["monto_total_erp"] = erp["monto_total_erp"].round(2)
    erp["estado_cierre"] = "CERRADO"

    # Inyección de brecha intencional: S/ 15,400 de diferencia en T04 el 2026-11-12
    mask_brecha = (erp["fecha_cierre"] == "2026-11-12") & (erp["tienda_id"] == "T04")
    erp.loc[mask_brecha, "monto_total_erp"] = (
        erp.loc[mask_brecha, "monto_total_erp"] + 15400.00
    ).round(2)

    return erp


def inject_pos_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Inyecta anomalías controladas de calidad de datos en fechas específicas."""
    corrupted = df.copy()

    # Anomalía 1 (2026-11-10, T02): 12 registros con precios/cantidades negativas
    mask_t02 = (corrupted["fecha_venta"] == "2026-11-10") & (corrupted["tienda_id"] == "T02")
    idx_t02 = corrupted.index[mask_t02]
    corrupted.loc[idx_t02[:6], "precio_unitario"] *= -1
    corrupted.loc[idx_t02[:6], "monto_total"] *= -1
    corrupted.loc[idx_t02[6:12], "cantidad"] = 0
    corrupted.loc[idx_t02[6:12], "monto_total"] = 0.0

    # Anomalía 2 (2026-11-10, T02): 15 tickets duplicados exactos
    duplicates = corrupted.loc[idx_t02[20:35]].copy()

    # Anomalía 3 (2026-11-12, T04): 20 SKUs inexistentes y 10 ticket_id nulos
    mask_t04 = (corrupted["fecha_venta"] == "2026-11-12") & (corrupted["tienda_id"] == "T04")
    idx_t04 = corrupted.index[mask_t04]
    corrupted.loc[idx_t04[:20], "sku_id"] = "SKU-9999"
    corrupted.loc[idx_t04[20:30], "ticket_id"] = np.nan

    return pd.concat([corrupted, duplicates], ignore_index=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    products = build_product_master()
    stores = build_stores()
    clean_pos = generate_clean_pos_sales(products, stores, rng)
    erp_closing = build_erp_closing(clean_pos)
    pos_with_anomalies = inject_pos_anomalies(clean_pos)

    products.to_csv(OUTPUT_DIR / "maestro_productos.csv", index=False)
    pos_with_anomalies.to_csv(OUTPUT_DIR / "ventas_pos.csv", index=False)
    erp_closing.to_csv(OUTPUT_DIR / "cierre_erp.csv", index=False)

    print("Archivos generados exitosamente en:", OUTPUT_DIR.resolve())
    print(f"  - maestro_productos.csv : {len(products):,} filas")
    print(f"  - ventas_pos.csv        : {len(pos_with_anomalies):,} filas (incluye anomalías DQ)")
    print(f"  - cierre_erp.csv        : {len(erp_closing):,} filas (incluye brecha T04 2026-11-12)")


if __name__ == "__main__":
    main()
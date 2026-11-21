-- ============================================================================
-- 02_gold_views.sql
-- Capa Gold: KPIs diarios de ventas retail para áreas usuarias y BI
-- ============================================================================

CREATE OR REPLACE VIEW retail_lakehouse_db.vw_gold_ventas_diarias AS
SELECT
    v.fecha_venta,
    v.tienda_id,
    v.formato,
    p.categoria,
    COUNT(DISTINCT v.ticket_id)                       AS total_tickets,
    SUM(v.cantidad)                                   AS unidades_vendidas,
    ROUND(SUM(v.monto_total), 2)                      AS venta_total_pen,
    ROUND(SUM(v.monto_total) / NULLIF(COUNT(DISTINCT v.ticket_id), 0), 2) AS ticket_promedio_pen
FROM retail_lakehouse_db.ventas_pos_silver v
INNER JOIN retail_lakehouse_db.maestro_productos p
    ON v.sku_id = p.sku_id
GROUP BY
    v.fecha_venta,
    v.tienda_id,
    v.formato,
    p.categoria;
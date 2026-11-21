-- ============================================================================
-- 03_reconciliation.sql
-- Conciliación diaria POS vs. ERP y monitoreo de calidad de datos (Quarantine)
-- ============================================================================

CREATE OR REPLACE VIEW retail_lakehouse_db.vw_conciliacion_pos_erp AS
WITH pos_diario AS (
    SELECT
        fecha_venta,
        tienda_id,
        ROUND(SUM(monto_total), 2) AS monto_total_pos,
        COUNT(DISTINCT ticket_id)  AS total_tickets_pos
    FROM retail_lakehouse_db.ventas_pos_silver
    GROUP BY fecha_venta, tienda_id
),
quarantine_diario AS (
    SELECT
        fecha_venta,
        tienda_id,
        COUNT(*) AS registros_en_cuarentena
    FROM retail_lakehouse_db.ventas_pos_quarantine
    GROUP BY fecha_venta, tienda_id
)
SELECT
    COALESCE(p.fecha_venta, e.fecha_cierre) AS fecha_operacion,
    COALESCE(p.tienda_id, e.tienda_id)      AS tienda_id,
    COALESCE(p.monto_total_pos, 0.0)        AS monto_total_pos,
    COALESCE(e.monto_total_erp, 0.0)        AS monto_total_erp,
    ROUND(COALESCE(e.monto_total_erp, 0.0) - COALESCE(p.monto_total_pos, 0.0), 2) AS brecha_pen,
    ROUND(
        ABS(COALESCE(e.monto_total_erp, 0.0) - COALESCE(p.monto_total_pos, 0.0))
        / NULLIF(e.monto_total_erp, 0.0) * 100,
        2
    ) AS brecha_pct,
    COALESCE(p.total_tickets_pos, 0)        AS total_tickets_pos,
    COALESCE(e.total_tickets_erp, 0)        AS total_tickets_erp,
    COALESCE(q.registros_en_cuarentena, 0)  AS registros_en_cuarentena,
    CASE
        WHEN ABS(COALESCE(e.monto_total_erp, 0.0) - COALESCE(p.monto_total_pos, 0.0))
             / NULLIF(e.monto_total_erp, 0.0) > 0.01
             OR COALESCE(q.registros_en_cuarentena, 0) > 0
        THEN 'ALERTA'
        ELSE 'OK'
    END AS estado_conciliacion
FROM pos_diario p
FULL OUTER JOIN retail_lakehouse_db.cierre_erp_silver e
    ON p.fecha_venta = e.fecha_cierre
   AND p.tienda_id   = e.tienda_id
LEFT JOIN quarantine_diario q
    ON COALESCE(p.fecha_venta, e.fecha_cierre) = q.fecha_venta
   AND COALESCE(p.tienda_id, e.tienda_id)      = q.tienda_id;


CREATE OR REPLACE VIEW retail_lakehouse_db.vw_resumen_calidad AS
SELECT
    fecha_venta,
    tienda_id,
    motivo_rechazo,
    COUNT(*)                     AS cantidad_registros,
    ROUND(SUM(monto_total), 2)   AS monto_impactado_pen
FROM retail_lakehouse_db.ventas_pos_quarantine
GROUP BY
    fecha_venta,
    tienda_id,
    motivo_rechazo
ORDER BY
    fecha_venta DESC,
    cantidad_registros DESC;
-- ============================================================
-- Dining Bot — Analytics query cookbook (SQLite)
-- Every query below is tested against dining_bot.db.
-- These are the read-only SELECTs the Analytics subgraph produces.
-- Rule: numbers come from here; document questions go to RAG.
-- ============================================================

-- 1. Total revenue (paid orders only) ------------------------
SELECT ROUND(SUM(total), 2) AS revenue_aed
FROM orders
WHERE status = 'paid';

-- 2. Revenue for a specific date range -----------------------
SELECT ROUND(SUM(total), 2) AS revenue_aed
FROM orders
WHERE status = 'paid'
  AND created_at >= '2026-08-17'
  AND created_at <  '2026-08-24';

-- 3. Daily revenue trend (for a line chart) ------------------
SELECT date(created_at) AS day, ROUND(SUM(total), 2) AS revenue_aed
FROM orders
WHERE status = 'paid'
GROUP BY day
ORDER BY day;

-- 4. Weekly revenue ------------------------------------------
SELECT strftime('%Y-W%W', created_at) AS week, ROUND(SUM(total), 2) AS revenue_aed
FROM orders
WHERE status = 'paid'
GROUP BY week
ORDER BY week;

-- 5. Top 5 selling items by quantity -------------------------
SELECT m.name, SUM(oi.qty) AS qty_sold
FROM order_items oi
JOIN menu_items m ON m.id = oi.menu_item_id
JOIN orders o     ON o.id = oi.order_id AND o.status = 'paid'
GROUP BY m.id
ORDER BY qty_sold DESC
LIMIT 5;

-- 6. Revenue by category (for a bar chart) -------------------
SELECT m.category, ROUND(SUM(oi.line_total), 2) AS revenue_aed
FROM order_items oi
JOIN menu_items m ON m.id = oi.menu_item_id
JOIN orders o     ON o.id = oi.order_id AND o.status = 'paid'
GROUP BY m.category
ORDER BY revenue_aed DESC;

-- 7. Average order value -------------------------------------
SELECT ROUND(AVG(total), 2) AS avg_order_value_aed
FROM orders
WHERE status = 'paid';

-- 8. Order count by status -----------------------------------
SELECT status, COUNT(*) AS orders
FROM orders
GROUP BY status;

-- 9. Payment method split ------------------------------------
SELECT method, COUNT(*) AS txns, ROUND(SUM(amount), 2) AS total_aed
FROM payments
WHERE status = 'paid'
GROUP BY method
ORDER BY total_aed DESC;

-- 10. Busiest hours of the day -------------------------------
SELECT strftime('%H', created_at) AS hour, COUNT(*) AS orders
FROM orders
WHERE status = 'paid'
GROUP BY hour
ORDER BY orders DESC;

-- 11. Ingredients at or below reorder level ------------------
SELECT name, stock, reorder_level, unit
FROM ingredients
WHERE stock <= reorder_level
ORDER BY (reorder_level - stock) DESC;

-- 12. Current active menu with prices ------------------------
SELECT category, name, price, CASE is_veg WHEN 1 THEN 'veg' ELSE 'non-veg' END AS type
FROM menu_items
WHERE active = 1
ORDER BY category, name;

-- 13. Dine-in vs takeaway vs delivery revenue ----------------
SELECT order_type, COUNT(*) AS orders, ROUND(SUM(total), 2) AS revenue_aed
FROM orders
WHERE status = 'paid'
GROUP BY order_type
ORDER BY revenue_aed DESC;

-- 14. Total discounts given ----------------------------------
SELECT ROUND(SUM(discount), 2) AS total_discount_aed
FROM orders
WHERE status = 'paid' AND discount > 0;

-- 15. Refunds -------------------------------------------------
SELECT COUNT(*) AS refund_count, ROUND(SUM(amount), 2) AS refunded_aed
FROM payments
WHERE status = 'refunded';

---
name: weekly-ops-plan
description: Build a multi-step weekly restaurant ops plan from sales, stock, weather, and policies. Use when the manager asks to plan the week, prepare a briefing, or combine several signals into one document.
---

# Weekly ops plan skill

1. Call `run_readonly_sql` with this exact pattern for revenue (do not invent table names):

```sql
SELECT date(created_at) AS day, SUM(total) AS revenue
FROM orders
WHERE status = 'paid' AND restaurant_id = 1
  AND date(created_at) >= date('now', '-7 days')
GROUP BY day ORDER BY day
```

2. Call `run_readonly_sql` for low stock:

```sql
SELECT name, stock, reorder_level, unit FROM ingredients
WHERE restaurant_id = 1 AND stock <= reorder_level ORDER BY stock
```

3. Call `search_policies` with query `opening hours service hours`.
4. Call `get_weather` with days=3.
5. Write `/plans/weekly_plan.md` with:
   - Headline revenue numbers (from SQL rows only — if SQL failed, say so and retry once)
   - Stock risks
   - Weather note
   - Opening hours (from policies)
   - Exactly 3 recommended manager actions (no DB writes)
6. Keep the file under ~40 lines.

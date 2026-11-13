# Eval report

Extraction model: `anthropic:claude-haiku-5-5`; planning model: `anthropic:claude-sonnet-5-5`; today = 2026-11-12.

## Summary

| Stage | Dimension | Passed |
|---|---|---|
| extraction | fields | 8/9 |
| extraction | routing | 9/9 |
| planner | outcome | 9/9 |
| planner | adherence | 9/9 |
| planner | caveats | 8/9 |

## Extraction (raw request → TripConstraints)

| Case | fields | routing |
|---|---|---|
| beach-jfk-tight-budget | ✅ 8/8 | ✅ plan |
| europe-long-weekend-sfo | ✅ 7/7 | ✅ plan |
| family-spring-break-pool | ✅ 8/8 | ✅ plan |
| anniversary-not-santorini | ✅ 5/5 | ✅ plan |
| lisbon-wedding-add-on | ❌ 2/4; origin=None (want 'LIS'); timeframe.start.month=None (want 10) | ✅ plan |
| tokyo-repeat-visit | ✅ 5/5 | ✅ plan |
| cheap | ✅ 3/3 | ✅ clarify |
| contradictory-luxury-on-shoestring | ✅ 4/4 | ✅ plan |
| destination-without-data | ✅ 4/4 | ✅ plan |

## Planner (gold constraints → TripResult)

| Case | outcome | adherence | caveats |
|---|---|---|---|
| beach-jfk-tight-budget | ✅ infeasible | ✅ n/a (no plan) | ✅ ok |
| europe-long-weekend-sfo | ✅ suggestion | ✅ OPO/H-OPO-3 $2,165 | ❌ missing NO_BUDGET |
| family-spring-break-pool | ✅ suggestion | ✅ PUJ/H-PUJ-1 $2,210 | ✅ ok |
| anniversary-not-santorini | ✅ suggestion | ✅ TIV/H-TIV-3 $1,145 | ✅ ok |
| lisbon-wedding-add-on | ✅ suggestion | ✅ FNC/H-FNC-2 $1,865 | ✅ ok |
| tokyo-repeat-visit | ✅ suggestion | ✅ HND/H-HND-1 $2,230 | ✅ ok |
| cheap | ✅ clarification | ✅ n/a (no plan) | ✅ ok |
| contradictory-luxury-on-shoestring | ✅ infeasible | ✅ n/a (no plan) | ✅ ok |
| destination-without-data | ✅ infeasible | ✅ n/a (no plan) | ✅ ok |

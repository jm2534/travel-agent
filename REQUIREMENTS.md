# Trip Idea Agent

## Summary
A single-turn CLI agent: one natural-language travel request in, one typed response out. That response is either a `TripSuggestion` (one option: destination, flight, hotel, code-computed cost, reasoning, and caveats), a `ClarificationRequest` (the specific questions that block planning), or an `Infeasible` (the closest option and the constraint it breaks). An LLM turns the request into a `TripConstraints` object. Code decides whether that is enough to plan. A planner agent then calls mock flight, hotel and destination tools, and code enforces the business rules (budget, exclusions, IDs that really exist) by sending `ModelRetry` back to the planner. Success means the eval harness, which scores the extractor and the planner separately on 9 cases, passes on the example prompts, including "Cheap." and contradictory or underspecified inputs.

## Terms
- **TripConstraints**: what the LLM extracted from the request, with nothing invented. Fields it can't find are `None`.
- **Critical gap**: a missing field that makes planning meaningless (see R3). It produces a `ClarificationRequest`.
- **Soft gap**: a missing field we can default. It produces an `Assumption` attached to the suggestion.
- **Hard cap / soft cap**: a hard budget is enforced by retry. A soft budget ("flexible but flag past $4k") is reported as a caveat, never enforced.
- **Today**: a date injected by code (`--today`, defaulting to the system date), so relative dates resolve the same way every time in evals.

## Requirements

### R1: Constraint extraction (MUST)
An LLM extracts `TripConstraints` from the request: origin (IATA), destination or the region and vibe preferences, excluded destinations, date window or month/season, nights, travellers (adults/children), budget (amount, scope: total / excl. flights / per-night hotel, hard or soft), and hotel requirements (pool, boutique, rating).
- Handled by: LLM (schema validated by code)
- Examples: "Tokyo for 8 days in November, two adults, $6k budget excluding flights" → destination=Tokyo, nights≈8, adults=2, budget 6000 excluding flights, origin=None
- On failure: schema-invalid output is retried by pydantic-ai, then the run returns an `AgentError` result (no crash, no traceback).
- Status: todo
- Code: src/travel_agent/extract.py, models.py (TripConstraints)

### R2: Date resolution against Today (MUST)
Code resolves month or season phrases to a concrete future window relative to Today. An explicit start date that has already passed rolls forward to next year, with `DATES_ROLLED_FORWARD`. A month alone means its next occurrence, which is not a roll-forward. Whenever there is no explicit start, the dates are a guess and get `DATES_ASSUMED`. No timeframe at all departs 30 days out.
- Handled by: code
- Examples: Today=2026-11-12, "Oct 10–13" → 2027-10-10..13, plus `DATES_ROLLED_FORWARD`; "February" → depart 2027-02-01; "November" (the current month) → depart tomorrow, 2026-11-13; start + end with no nights → nights = end − start; start + end + nights that disagree → nights wins, plus `END_DATE_IGNORED`
- On failure: an impossible start (e.g. Feb 30) falls back to that month. An end with no start is ignored (`timeframe.month` if set, else 30 days out). Both add `DATES_ASSUMED`. Never an exception.
- Status: done
- Code: src/travel_agent/gate.py (resolve_dates)

### R3: Sufficiency gate (MUST)
Code, not the LLM, decides between planning and asking. A critical gap means no destination and no preferences, **and** no timeframe. In that case the response is a `ClarificationRequest` that lists the missing fields, with one question for each drawn from a code template (no LLM). Every other gap is soft and gets a stated default.
- Handled by: code
- Examples: "Cheap." → ClarificationRequest(missing=[destination_or_preferences, timeframe]); missing origin and no `--from` → plan without flights, with caveat `FLIGHTS_NOT_PRICED`; missing origin with `--from JFK` → origin=JFK plus caveat `ORIGIN_FROM_DEVICE`; missing travellers → assume 2 adults, recorded as an assumption; missing budget → caveat `NO_BUDGET`; only origin, budget, exclusions or hotel requirements given → still a ClarificationRequest (none of them says what or when)
- On failure: n/a (pure function)
- Status: done
- Code: src/travel_agent/gate.py (assess)

### R4: Mock tools (MUST)
Three tools, each a thin wrapper over static JSON:
- `find_destinations(preferences, month, near)` returns candidate cities with tags, weather by month, and a touristiness score.
- `search_flights(origin, destination, depart_date, return_date)` returns all fares, with the price adjusted for season by code.
- `search_hotels(city, check_in, nights)` returns all properties: nightly rate, amenities, style.

Each result carries a stable ID. An empty result is a normal return (`[]`, whose meaning each tool's docstring states), never an exception. `find_destinations` also filters by `region`, and by `name` (a city name or IATA code, ignoring the other filters). With preferences given, destinations matching none of them are dropped.
- Handled by: code
- Examples: search_flights("JFK","CUN",...) → ≥2 fares, cheapest first; search_flights("JFK","XXX",...) → []; search_hotels for 4 guests in a hotel whose rooms sleep 2 → priced as 2 rooms; find_destinations(near="LIS") → only destinations within 1500 km
- On failure: an unknown city or route returns [], and the planner must handle it.
- Status: done
- Code: src/travel_agent/tools.py, catalog.py (records price themselves), pricing.py (trip cost and checks); fixtures in data/ (repo root)

### R5: Planner with code-enforced rules (MUST)
The planner LLM picks options by **ID only**. An output validator recomputes cost from the mock data and raises `ModelRetry` when any of these hold: an ID is unknown; IDs disagree (the hotel isn't in the destination, or the flight is the wrong route); a flight is missing while the brief has an origin; an excluded destination is chosen (an exact IATA code, or a case-insensitive name substring); a hard cap is exceeded (`total` checks flights + hotel, `excluding_flights` checks the hotel, `hotel_per_night` checks the room-night rate; approximate allows 10%); or a stated hotel requirement (amenity, min stars, style) is unmet. Soft budgets never trigger a retry. The model never does the arithmetic.
- Handled by: LLM (choices) + code (validation, pricing)
- Examples: "under $2000 for two" with the cheapest option at $2400 → retry → eventually `Infeasible`
- On failure: when retries run out (N=3), code builds `Infeasible` from the last attempt the validator rejected (re-priced, with the violated constraint kinds). The planner may also return `Infeasible` directly when the tools show nothing fits. It must include its closest option's IDs, and code prices them. A constraint is never violated silently.
- A 4th tool, `quote_trip(flight_id, hotel_id, nights)`, calls the same pricing function as the validator, so the model can check before it commits.
- Status: done
- Code: src/travel_agent/plan.py (enforce_constraints, plan_trip), pricing.py (check_proposal)

### R6: Typed response (MUST)
`TripResult = TripSuggestion | ClarificationRequest | Infeasible | AgentError`, all pydantic. TripSuggestion has a single `option` (destination, reasoning, flight_id?, hotel_id, nights, cost breakdown computed by code), assumptions[], and caveats[]. Each caveat has a `kind` enum and text.
- Handled by: code
- Examples: see R3, R5
- On failure: n/a
- Status: done
- Code: src/travel_agent/models.py

### R7: CLI (MUST)
`uv run travel-agent` (or `python -m travel_agent`) shows the example prompts to pick from, or `travel-agent "free text"`. Optional `--from IATA` simulates a device location (as a browser would provide with permission) and is used only when no origin was extracted. Optional `--today YYYY-MM-DD`. It prints the result as JSON (and a short human summary).
- Handled by: code
- On failure: a missing or invalid API key prints a one-line actionable error and exits with code 2. This check runs before any LLM call.
- Status: done
- Code: src/travel_agent/cli.py, __main__.py

### R8: Configurable provider (MUST)
Models are set per stage with pydantic-ai model strings: `TRAVEL_AGENT_EXTRACTION_MODEL` (default `anthropic:claude-haiku-5-5`) and `TRAVEL_AGENT_PLANNING_MODEL` (default `anthropic:claude-sonnet-5-5`). The key is read from the provider's standard env var through `.env`, which is git-ignored. `.env.example` is committed.
- Handled by: code
- Status: done
- Code: src/travel_agent/config.py, .env.example

### R9: Eval harness (MUST)
`uv run travel-agent-eval` runs 9 cases: the 7 assignment examples, a contradictory one ($500 5-star Paris week), and a destination with no data. Each case carries:
  - `expected_constraints`: a partial field match, scoring the **extractor**.
  - `gold_constraints` + `planner_checks`: the planner runs on gold input, not on the extractor's output, so the two stages fail independently. Dimensions: (1) **outcome type**, (2) **constraint adherence** (budget, exclusions, amenities, origin), (3) **expected caveat kinds** present.

  All scoring is deterministic (no LLM-as-judge). It writes `evals/report.md` with one table per stage. The gate (R3) is covered by unit tests, not the eval.
- Handled by: code
- On failure: a case that errors scores 0 and is reported; the run continues.
- Status: tested
- Code: src/travel_agent/eval_harness.py, evals/

### R10: README / PROCESS (MUST)
Setup in under 5 minutes; the decision log; known gaps.
- Status: done
- Code: README.md, PROCESS.md, DECISIONS.md

## Out of scope
- Real travel APIs, pagination, fuzzy search: the assignment says so. Tools return every match.
- Multi-turn: a ClarificationRequest is terminal. The user re-runs with more detail.
- Multi-city itineraries: one destination per option.
- Production retries, caching, observability: the assignment says so.

## Assumptions
- A2: Mock data is static JSON (17 destinations to start, so every example plus Santorini is covered; origins JFK, SFO, LIS), generated once by a committed Haiku script, with Santorini included so the exclusion can be tested. Seasonal pricing is a code multiplier, so data isn't stored per date. (confirmed)
- A3: Defaults for soft gaps: 2 adults; nights from phrasing (long weekend=3, week=7), else 5; no timeframe → depart Today + 30 days. (confirmed)

## Decisions
See `DECISIONS.md`.

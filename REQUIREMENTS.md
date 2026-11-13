# Trip Idea Agent

## Summary
A single-turn CLI agent: one natural-language travel request in, one typed response out. That response is either a `TripSuggestion` (1–3 ranked options, each with destination, flight, hotel, code-computed cost, reasoning, and caveats) or a `ClarificationRequest` (the specific questions that block planning). An LLM turns the request into a `TripConstraints` object. Code decides whether that is enough to plan. A planner agent then calls mock flight, hotel and destination tools, and code enforces the business rules (budget, exclusions, IDs that really exist) by sending `ModelRetry` back to the planner. Success means the bundled eval harness (7 or more cases, at least 2 scored dimensions) passes on the example prompts, including "Cheap." and contradictory or underspecified inputs.

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

### R2: Date resolution against Today (MUST)
Code resolves month or season phrases to a concrete future window relative to Today. A window that has already passed rolls forward to next year, and a caveat is attached.
- Handled by: code
- Examples: Today=2026-11-12, "Oct 10–13" → 2027-10-10..13, plus caveat; "February" → Feb 2027
- On failure: if the phrase can't be resolved, treat it as a soft gap and attach an assumption.
- Status: todo

### R3: Sufficiency gate (MUST)
Code, not the LLM, decides between planning and asking. A critical gap means no destination and no preferences, **and** no timeframe. In that case the response is a `ClarificationRequest` that lists the missing fields and one question for each. Every other gap is soft and gets a stated default.
- Handled by: code
- Examples: "Cheap." → ClarificationRequest(missing=[destination_or_preferences, timeframe]); missing origin → plan without flights, with caveat `FLIGHTS_NOT_PRICED`; missing travellers → assume 2 adults, recorded as an assumption
- On failure: n/a (pure function)
- Status: todo

### R4: Mock tools (MUST)
Three tools, each a thin wrapper over static JSON:
- `find_destinations(preferences, month, near)` returns candidate cities with tags, weather by month, and a touristiness score.
- `search_flights(origin, destination, depart_date, return_date)` returns all fares, with the price adjusted for season by code.
- `search_hotels(city, check_in, nights)` returns all properties: nightly rate, amenities, style.

Each result carries a stable ID. An empty result is a normal return (an empty list plus a reason), never an exception.
- Handled by: code
- Examples: search_flights("JFK","CUN",...) → ≥2 fares; search_flights("JFK","XXX",...) → []
- On failure: an unknown city or route returns [], and the planner must handle it.
- Status: todo

### R5: Planner with code-enforced rules (MUST)
The planner LLM picks options by **ID only**. An output validator recomputes cost from the mock data and raises `ModelRetry` when any of these hold: an ID is unknown, an excluded destination is chosen, a hard cap is exceeded, or a required hotel amenity is missing. The model never does the arithmetic.
- Handled by: LLM (choices) + code (validation, pricing)
- Examples: "under $2000 for two" with the cheapest option at $2400 → retry → eventually `Infeasible`
- On failure: when retries run out (N=3), the result is `Infeasible` with the cheapest option found and why it failed, never a hallucinated plan.
- Status: todo

### R6: Typed response (MUST)
`TripResult = TripSuggestion | ClarificationRequest | Infeasible | AgentError`, all pydantic. TripSuggestion has options[1..3] (destination, reasoning, flight_id?, hotel_id, nights, cost breakdown computed by code), assumptions[], and caveats[]. Each caveat has a `kind` enum and text.
- Handled by: code
- Examples: see R3, R5
- On failure: n/a
- Status: todo

### R7: CLI (MUST)
`uv run travel-agent` shows the example prompts to pick from, or `travel-agent "free text"`. It prints the result as JSON (and a short human summary).
- Handled by: code
- On failure: a missing or invalid API key prints a one-line actionable error and exits with code 2. This check runs before any LLM call.
- Status: todo

### R8: Configurable provider (MUST)
The model is set by the `TRAVEL_AGENT_MODEL` env var (a pydantic-ai model string). The key is read from the provider's standard env var through `.env`, which is git-ignored. `.env.example` is committed.
- Handled by: code
- Status: todo

### R9: Eval harness (MUST)
`uv run travel-agent-eval` runs at least 7 cases (the assignment examples plus contradictory and past-date cases). Each case declares its expected outcome type and checks for that case. Scores cover at least these dimensions: (1) **outcome**: the right result type; (2) **constraint adherence**: budget, exclusions, amenities, and the expected caveat kinds present. It writes a summary table to `evals/report.md`.
- Handled by: code
- On failure: a case that errors scores 0 and is reported; the run continues.
- Status: todo

### R10: README / PROCESS (MUST)
Setup in under 5 minutes; the decision log; known gaps.
- Status: todo

## Out of scope
- Real travel APIs, pagination, fuzzy search: the assignment says so. Tools return every match.
- Multi-turn: a ClarificationRequest is terminal. The user re-runs with more detail.
- Multi-city itineraries: one destination per option.
- Production retries, caching, observability: the assignment says so.

## Assumptions
- A1: Default model is Anthropic Claude Haiku, because it is cheap, fast, and reliable at tool calling. (unconfirmed)
- A2: Mock data is static JSON (about 15 destinations; origins JFK, SFO, LIS). Seasonal pricing is a code multiplier, so data isn't stored per date. (unconfirmed)
- A3: Defaults for soft gaps: 2 adults, nights from phrasing (long weekend=3, week=7), else 5. (unconfirmed)

## Decisions
- Two LLM stages (extract → code gate → plan) rather than one agent, because the ask-vs-plan decision is a business rule and must be testable without an LLM. Tradeoff: two model calls.
- The model returns IDs and code computes prices, because LLM arithmetic is unreliable and budget is a hard rule. Tradeoff: the schema is less natural for the model.

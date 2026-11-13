# Decisions

One line each: X over Y because Z.

## Orchestration
- A two-stage pipeline (extractor → code gate → planner) over a single agent, because "ask vs. plan" is policy and must be a unit-tested pure function, and because the stages can then be evaluated separately.
- Haiku for extraction over one model for both, because extraction is narrow and high-volume; Sonnet for planning because it's multi-step tool use.
- A ReAct-style tool loop with an output validator over a fixed workflow, because choosing destinations is the open-ended part and the validator still guarantees the rules.
- `ModelRetry` from the output validator over prompt instructions for business rules (budget, exclusions, amenities, stars), because prompts are guidance and code is the contract.
- Up to 3 output retries, then a typed `Infeasible` built from the last rejected proposal, over a best-effort plan or a raw error, because a silent constraint violation is the worst outcome.

## Tools and data
- The planner returns IDs and code computes cost, over having the model report prices, because LLM arithmetic is unreliable and budget is a hard rule.
- Four tools (`find_destinations`, `search_flights`, `search_hotels`, `quote_trip`) over a single combined search, because they mirror how separate travel APIs are actually shaped. `quote_trip` shares its code with the validator, so the model can check a proposal before it commits.
- Model-facing wrappers that bind origin, dates, party size and nights from the brief, over exposing the full `tools.py` signatures, because the model can't query the wrong dates if it never supplies them. **Limitation:** the planner can't explore alternative dates.
- The gate fixes nights, over letting the planner choose them, for the same reason.
- Closed vocabularies (`Tag`, `Region`, `Amenity`, `HotelStyle` as `Literal`s) over free text, because `find_destinations` then filters deterministically and evals can assert on exact values. **Limitation:** any preference outside the vocabulary ("ski", "wine region", "pet-friendly") is lost at extraction, silently and without a caveat.
- Static JSON plus a seasonal multiplier in code over fixtures stored per date, because any date then works and the fixtures stay small. **Limitation:** there are only two price levels (peak at 1.3x, and off-peak).
- Fixtures written by Haiku in a one-off committed script and validated against the catalog models, over hand-written data, because 17 destinations × hotels × routes is tedious and the schema check catches bad generations. Unit tests use a small hand-written catalog instead, so they don't depend on generated data.
- Fixtures live in `data/` at the repo root rather than inside the package, because they're reviewable inputs rather than code. Tradeoff: a wheel install wouldn't include them, which doesn't matter for a source checkout run with `uv run`.
- Typed ID aliases (`DestinationId`, `FlightId`, `HotelId`, `AirportCode`) with patterns over bare `str`, because signatures say what they operate on, and a malformed ID fails schema validation before it ever reaches the validator.
- Hotel style (e.g. "boutique") is a hard requirement like amenities and min stars, rather than a soft preference, because the user stated it and enforcing all three the same way is consistent.
- `near` resolves through a small table of origin-airport coordinates in `tools.py`, rather than requiring every origin to also be a destination, because users say "near Lisbon" where Lisbon is where they already are.
- `find_destinations` drops destinations that match none of the stated preferences, rather than returning everything ranked, because a zero-overlap pick is never what the user asked for. Tradeoff: a narrow vocabulary match can return nothing; the planner then falls back to `NoFeasiblePlan`.
- Exclusions match an exact IATA code or a case-insensitive name substring, rather than exact names only, so "Madeira" matches "Madeira (Funchal)". Tradeoff: a short term could over-match.
- Pricing rules: children pay full fare and rooms = ⌈party / room capacity⌉, over modelling child fares and room types, because the mock data doesn't justify more.

## Missing information
- Clarify only when both "what" and "when" are missing, over asking about every gap, because most of the examples omit something (origin, budget) and are still worth planning with caveats.
- Code-template clarifying questions over LLM-phrased ones, because the gate is code and its output should be deterministic.
- A `--from` device-location fallback for origin over always degrading to hotel-only, because a real client (a browser) would often have this. It's used only when the request names no origin, and it adds the `ORIGIN_FROM_DEVICE` caveat.
- Budget as `{amount, scope, hard, approximate}` over a single number, because the examples mix total, excluding-flights, per-night and "flexible, but flag it".
- When a stated end date conflicts with stated nights, nights win over the end date, because "tack on 5 days" phrasing makes nights the more deliberate signal. This is never silent: it adds the `END_DATE_IGNORED` caveat.
- One option per suggestion over 1–3 ranked options, because ranking is overbuilding for now.

## Evals
- Deterministic scoring over LLM-as-judge, because it gives a real, repeatable signal within the time budget. **Limitation:** reasoning quality isn't scored.
- The planner is evaluated on gold constraints rather than the extractor's output, because a bad extraction would otherwise hide or fake planner failures.

## Deferred at the deadline
- Keeping `ClarificationRequest.missing` and the per-field `CLARIFYING_QUESTIONS` over collapsing them to one question, because they support partial clarification later. Today the gate always asks about everything missing.
- Recording these review findings as debt over refactoring in the last minutes, because a green build mattered more than tidiness: one "retry budget exhausted" message covers both proposal rejections and tool-retry exhaustion; `PlannerDeps.last_rejected` stores unused violations; name/id matching is duplicated in `tools.find_destinations` and `pricing._exclusion_violations` (it belongs in `Destination.matches`); `gate.assess` is long (`_resolve_origin`/`_resolve_nights` would split it); some public models lack Google-style docstrings.

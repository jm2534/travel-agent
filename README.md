# Trip Idea Agent

One natural-language travel request in, one typed answer out: a priced **suggestion**, a **clarification** request, an honest **infeasible**, or a typed **error**. Travel data is mocked (`data/*.json`).

## Run it (under 2 minutes)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14 (uv installs it if missing).

```bash
cp .env.example .env          # then set ANTHROPIC_API_KEY
uv sync
uv run travel-agent           # pick one of the 7 example prompts
uv run travel-agent "Long weekend in Europe from SFO, great food" --today 2026-11-12
uv run travel-agent "Somewhere warm in March" --from JFK   # --from = device-location fallback for origin
uv run travel-agent-eval      # runs evals/cases.yaml, writes evals/report.md
uv run pytest -q              # 100 tests, no network (models are faked)
```

`python -m travel_agent` works too.

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Read from the environment or `.env` (git-ignored). |
| `TRAVEL_AGENT_EXTRACTION_MODEL` | `anthropic:claude-haiku-5-5` | Any [pydantic-ai model string](https://ai.pydantic.dev/models/). |
| `TRAVEL_AGENT_PLANNING_MODEL` | `anthropic:claude-sonnet-5-5` | Multi-step tool use, so it gets the stronger model. |

Other providers work by changing the model string (`openai:…`, `openrouter:…`) and setting that provider's key.

**When credentials fail:**
- **Missing key:** the run stops before any LLM call, with a one-line fix and exit code 2.
- **Invalid key:** you get `{"outcome": "error", "kind": "auth"}` and exit code 2.
- **Other API failures:** you get `kind: "model_api"`, or `"model_behavior"` if the model never produced valid output after retries, and exit code 1.

The CLI never shows a traceback for model failures.

## How it works

```
request ─▶ extract (Haiku) ─▶ TripConstraints ─▶ gate (pure code) ─┬─▶ ClarificationRequest
                                                                  └─▶ PlanningBrief ─▶ planner (Sonnet + tools)
                                                                                         │  Proposal (IDs only)
                                                                      output validator ◀─┘  ModelRetry ×3 on violation
                                                                         │
                                                         TripSuggestion | Infeasible (priced by code)
```

1. **Extract** (`extract.py`): the LLM records only what the user said (`models.TripConstraints`). Field descriptions in the schema are the prompt.
2. **Gate** (`gate.py`): code decides between asking and planning. It clarifies only when both *what* (destination, region, near or preferences) and *when* are missing ("Cheap."). Every other gap gets a default, recorded as an `Assumption`, or a typed `Caveat` (e.g. `FLIGHTS_NOT_PRICED` when there's no origin, `DATES_ROLLED_FORWARD` when the dates have passed).
3. **Plan** (`plan.py`): the planner has four tools: `find_destinations`, `search_flights`, `search_hotels` and `quote_trip`. It returns **IDs only**. The output validator recomputes the cost (`pricing.py`) and sends violations back as `ModelRetry`: unknown or mismatched IDs, an excluded destination, a hard budget, the nightly cap, or an amenity, star or style requirement. After 3 retries the result is `Infeasible` with the closest option, so a constraint is never broken silently.

The tools bind origin, dates and party size from the brief, so the model chooses only where to go and which flight and hotel. The reasoning behind each choice is in [`DECISIONS.md`](DECISIONS.md), and the spec, with each requirement's status, is in [`REQUIREMENTS.md`](REQUIREMENTS.md).

## Evals

`evals/cases.yaml` has 9 cases: the 7 assignment prompts, a contradictory one (5-star Barcelona for $800) and one with no data (Reykjavik). Each case is scored in **two independent stages**:

| Stage | Input | Dimensions |
|---|---|---|
| Extraction | raw request | `fields`: expected fields match (partial, lists as subsets); `routing`: the real gate on the extracted constraints agrees on ask vs. plan |
| Planner | **gold** constraints, so extraction errors can't leak in | `outcome` type; `adherence` to case-level hard checks (budget, nightly cap, amenities, style, allowed or forbidden destinations, region); expected `caveats` present |

All scoring is deterministic. Expected outcomes were checked against `data/`; for example, the beach-under-$2k case is *expected* to be infeasible, because no 4-star beach week costs less than about $3.1k. Latest results: [`evals/report.md`](evals/report.md).

## Known gaps

- **Vocabulary:** preferences outside the `Tag` list ("ski", "wine", "pet-friendly") are dropped at extraction, without a caveat.
- **Fixed dates:** the planner can't try other dates or trip lengths to fit a budget.
- **One option:** no ranked alternatives.
- **Reasoning quality isn't evaluated:** there's no LLM-as-judge. Figures in the model's free-text `reason` or `reasoning` aren't validated. `cost` is authoritative.
- **Quality words become hard requirements:** "nice hotel" → `min_stars=4`, which can make a request infeasible when a 3-star option would have satisfied the user.
- **Mock data:** generated once by Haiku (`scripts/generate_fixtures.py`). Prices have two levels (peak 1.3×, off-peak 1×), and children pay full fare.
- **Single run, nothing saved:** the eval runs each case once, with no variance across repeated runs.
- **No origin, `total` cap:** with no origin, flights aren't priced, so a hard `total` budget is checked against the hotel cost only. Only the `FLIGHTS_NOT_PRICED` caveat signals this.
- **Unknown provider prefix:** a model string whose provider isn't in `PROVIDER_KEY_VARS` skips the API key pre-check. A missing key then fails later, when that provider's SDK builds its client or makes its first call.
- **Invalid API key output:** the CLI prints the provider's full JSON error before its one-line error, where R7 implies just the one line.
- **Thin harness tests:** the eval scoring functions, the errored-case path (scores 0, run continues) and planner tool wrappers have no model-free unit tests yet. A real eval run exercises them.

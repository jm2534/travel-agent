"""Eval harness (R9): scores the extractor and the planner separately.

The planner runs on gold constraints, so the two stages fail independently.
`uv run travel-agent-eval` reads evals/cases.yaml and writes evals/report.md.
"""

import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, Field

from travel_agent.catalog import Catalog
from travel_agent.config import Config, ConfigError, load_config
from travel_agent.extract import extract_constraints
from travel_agent.gate import assess
from travel_agent.models import (
    AirportCode,
    Amenity,
    CaveatKind,
    ClarificationRequest,
    DestinationId,
    HotelStyle,
    Region,
    TripConstraints,
    TripResult,
    TripSuggestion,
)
from travel_agent.plan import plan_trip

CASES_PATH = Path("evals/cases.yaml")
REPORT_PATH = Path("evals/report.md")
EVAL_TODAY = date(2026, 11, 12)


class PlannerChecks(BaseModel):
    """What a planner result must satisfy. Unset checks are skipped."""

    outcome: Literal["suggestion", "clarification", "infeasible"]
    max_total_usd: float | None = None
    max_hotel_usd: float | None = None
    max_nightly_usd: float | None = None
    required_amenities: list[Amenity] = []
    required_style: HotelStyle | None = None
    forbidden_destinations: list[DestinationId] = []
    allowed_destinations: list[DestinationId] = []
    allowed_regions: list[Region] = []
    expected_caveats: list[CaveatKind] = []


class EvalCase(BaseModel):
    id: str
    request: str
    today: date = EVAL_TODAY
    device_origin: AirportCode | None = None
    expected_constraints: dict[str, Any] = Field(
        description="Partial match on the extractor output; dotted paths; lists match as subsets."
    )
    gold_constraints: TripConstraints
    planner_checks: PlannerChecks

    @classmethod
    def load_all(cls, path: Path = CASES_PATH) -> list[Self]:
        """Parse every case in a YAML file."""
        return [cls.model_validate(raw) for raw in yaml.safe_load(path.read_text())]


class DimensionScore(BaseModel):
    dimension: str
    passed: bool
    detail: str = ""


class CaseResult(BaseModel):
    case_id: str
    scores: list[DimensionScore] = []
    error: str | None = None

    def passed(self, dimension: str) -> bool:
        """Whether this case passed a dimension; an errored case fails every dimension."""
        return self.error is None and any(
            s.dimension == dimension and s.passed for s in self.scores
        )


def score_extraction(case: EvalCase, actual: TripConstraints) -> list[DimensionScore]:
    """Dimensions: `fields` (every expected field matches) and `routing` (ask vs. plan agrees).

    Routing runs the real gate on the extractor's output, since that's the decision a bad
    extraction would actually change.
    """
    mismatches = []
    for path, expected in case.expected_constraints.items():
        got = _resolve_path(actual, path)
        if not _matches(expected, got):
            mismatches.append(f"{path}={got!r} (want {expected!r})")
    total = len(case.expected_constraints)
    fields = DimensionScore(
        dimension="fields",
        passed=not mismatches,
        detail=f"{total - len(mismatches)}/{total}"
        + (f"; {'; '.join(mismatches)}" * bool(mismatches)),
    )

    gate_result = assess(actual, case.today, case.device_origin)
    wants_clarification = case.planner_checks.outcome == "clarification"
    asked = isinstance(gate_result, ClarificationRequest)
    routing = DimensionScore(
        dimension="routing",
        passed=asked == wants_clarification,
        detail="clarify" if asked else "plan",
    )
    return [fields, routing]


def score_planner(case: EvalCase, result: TripResult, catalog: Catalog) -> list[DimensionScore]:
    """Dimensions: `outcome` type, `adherence` to the case's hard checks, `caveats` present."""
    checks = case.planner_checks
    outcome = DimensionScore(
        dimension="outcome",
        passed=result.outcome == checks.outcome,
        detail=result.outcome + (f": {result.message}" if result.outcome == "error" else ""),
    )

    if isinstance(result, TripSuggestion):
        failures = _adherence_failures(checks, result, catalog)
        option = result.option
        picked = f"{option.proposal.destination_id}/{option.proposal.hotel_id}"
        summary = f"{picked} ${option.cost.total_usd:,.0f}"
        adherence = DimensionScore(
            dimension="adherence",
            passed=not failures,
            detail="; ".join(failures) or summary,
        )
    else:
        adherence = DimensionScore(dimension="adherence", passed=True, detail="n/a (no plan)")

    actual_kinds = {c.kind for c in getattr(result, "caveats", [])}
    missing = [k.value for k in checks.expected_caveats if k not in actual_kinds]
    caveats = DimensionScore(
        dimension="caveats",
        passed=not missing,
        detail=f"missing {', '.join(missing)}" if missing else "ok",
    )
    return [outcome, adherence, caveats]


def run_extraction_case(case: EvalCase, config: Config) -> CaseResult:
    """Extract from the raw request and score it. Any failure scores 0 and is reported."""
    try:
        actual = extract_constraints(case.request, config.extraction_model)
        return CaseResult(case_id=case.id, scores=score_extraction(case, actual))
    except Exception as e:  # noqa: BLE001 - the eval reports every failure and keeps going (R9)
        return CaseResult(case_id=case.id, error=f"{type(e).__name__}: {e}")


def run_planner_case(case: EvalCase, config: Config, catalog: Catalog) -> CaseResult:
    """Gate and plan from the gold constraints, then score. Any failure scores 0 and is reported."""
    try:
        brief = assess(case.gold_constraints, case.today, case.device_origin)
        if isinstance(brief, ClarificationRequest):
            result = brief
        else:
            result = plan_trip(brief, config.planning_model, catalog)
        return CaseResult(case_id=case.id, scores=score_planner(case, result, catalog))
    except Exception as e:  # noqa: BLE001 - the eval reports every failure and keeps going (R9)
        return CaseResult(case_id=case.id, error=f"{type(e).__name__}: {e}")


def render_report(config: Config, extraction: list[CaseResult], planner: list[CaseResult]) -> str:
    """Markdown: a summary of pass rates, then one table per stage."""
    lines = [
        "# Eval report",
        "",
        f"Extraction model: `{config.extraction_model}`; "
        f"planning model: `{config.planning_model}`; today = {EVAL_TODAY}.",
        "",
        "## Summary",
        "",
        "| Stage | Dimension | Passed |",
        "|---|---|---|",
    ]
    for stage, results, dims in [
        ("extraction", extraction, ["fields", "routing"]),
        ("planner", planner, ["outcome", "adherence", "caveats"]),
    ]:
        for dim in dims:
            passed = sum(r.passed(dim) for r in results)
            lines.append(f"| {stage} | {dim} | {passed}/{len(results)} |")
    for title, results, dims in [
        ("Extraction (raw request → TripConstraints)", extraction, ["fields", "routing"]),
        ("Planner (gold constraints → TripResult)", planner, ["outcome", "adherence", "caveats"]),
    ]:
        lines += ["", f"## {title}", "", "| Case | " + " | ".join(dims) + " |"]
        lines.append("|---" * (len(dims) + 1) + "|")
        for r in results:
            if r.error:
                lines.append(f"| {r.case_id} | ERROR: {r.error[:150]} |" + " |" * (len(dims) - 1))
                continue
            by_dim = {s.dimension: s for s in r.scores}
            cells = [
                f"{'✅' if by_dim[d].passed else '❌'} {by_dim[d].detail}".replace("|", "/")
                for d in dims
            ]
            lines.append(f"| {r.case_id} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run cases through both stages; `travel-agent-eval [case-id ...]` runs a subset.

    Only a full run writes evals/report.md, so the committed report always covers every case.
    """
    try:
        config = load_config()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    selected = sys.argv[1:]
    cases = [c for c in EvalCase.load_all() if not selected or c.id in selected]
    catalog = Catalog.load()
    extraction, planner = [], []
    for case in cases:
        print(f"[{case.id}] extracting...", file=sys.stderr)
        extraction.append(run_extraction_case(case, config))
        print(f"[{case.id}] planning...", file=sys.stderr)
        planner.append(run_planner_case(case, config, catalog))

    report = render_report(config, extraction, planner)
    if not selected:
        REPORT_PATH.write_text(report)
    print(report)


def _adherence_failures(
    checks: PlannerChecks, result: TripSuggestion, catalog: Catalog
) -> list[str]:
    """Each case-level hard check the suggestion breaks, as a human-readable line."""
    proposal, cost = result.option.proposal, result.option.cost
    destination = catalog.destinations[proposal.destination_id]
    hotel = catalog.hotels[proposal.hotel_id]
    failures = []
    if checks.max_total_usd is not None and cost.total_usd > checks.max_total_usd:
        failures.append(f"total ${cost.total_usd:,.0f} > ${checks.max_total_usd:,.0f}")
    if checks.max_hotel_usd is not None and cost.hotel_usd > checks.max_hotel_usd:
        failures.append(f"hotel ${cost.hotel_usd:,.0f} > ${checks.max_hotel_usd:,.0f}")
    if checks.max_nightly_usd is not None and cost.hotel_nightly_usd > checks.max_nightly_usd:
        failures.append(f"nightly ${cost.hotel_nightly_usd:,.0f} > ${checks.max_nightly_usd:,.0f}")
    if missing := [a for a in checks.required_amenities if a not in hotel.amenities]:
        failures.append(f"hotel lacks {', '.join(missing)}")
    if checks.required_style is not None and hotel.style != checks.required_style:
        failures.append(f"hotel is {hotel.style}, not {checks.required_style}")
    if destination.id in checks.forbidden_destinations:
        failures.append(f"forbidden destination {destination.id}")
    if checks.allowed_destinations and destination.id not in checks.allowed_destinations:
        failures.append(f"{destination.id} not in {checks.allowed_destinations}")
    if checks.allowed_regions and destination.region not in checks.allowed_regions:
        failures.append(f"region {destination.region} not in {checks.allowed_regions}")
    return failures


def _resolve_path(obj: Any, path: str) -> Any:
    """Follow a dotted path through attributes; None as soon as a step is missing."""
    for step in path.split("."):
        if obj is None:
            return None
        obj = getattr(obj, step, None)
    return obj


def _matches(expected: Any, actual: Any) -> bool:
    """Equality, except a non-empty expected list only needs to be a subset of the actual one."""
    if isinstance(expected, list) and expected:
        return isinstance(actual, list) and all(item in actual for item in expected)
    if isinstance(expected, list):
        return not actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    return expected == actual

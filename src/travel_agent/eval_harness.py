"""Eval harness (R9): scores the extractor and the planner separately.

The planner runs on gold constraints, so the two stages fail independently.

`uv run travel-agent-eval` reads evals/cases.yaml and writes evals/report.md.
"""

from pathlib import Path

from pydantic import BaseModel

from travel_agent.models import CaveatKind, TripConstraints

CASES_PATH = Path("evals/cases.yaml")
REPORT_PATH = Path("evals/report.md")


class PlannerChecks(BaseModel):
    outcome: str  # "suggestion" | "clarification" | "infeasible"
    max_total_usd: float | None = None
    forbidden_destinations: list[str] = []
    required_amenities: list[str] = []
    expected_caveats: list[CaveatKind] = []


class EvalCase(BaseModel):
    id: str
    request: str
    today: str
    device_origin: str | None = None
    expected_constraints: (
        dict  # partial match against the extractor's TripConstraints (dotted paths allowed)
    )
    gold_constraints: TripConstraints
    planner_checks: PlannerChecks


class DimensionScore(BaseModel):
    dimension: str
    passed: bool
    detail: str = ""


def score_extraction(case: EvalCase, actual: TripConstraints) -> list[DimensionScore]:
    """One score per expected field: exact match, with order-insensitive comparison for lists."""
    raise NotImplementedError


def score_planner(case: EvalCase, result) -> list[DimensionScore]:
    """Dimensions: outcome type, constraint adherence, expected caveat kinds present."""
    raise NotImplementedError


def main() -> None:
    raise NotImplementedError

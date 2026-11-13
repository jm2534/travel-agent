"""The eval harness's own scoring, without calling any model."""

import pytest

from travel_agent.eval_harness import EvalCase, score_extraction
from travel_agent.gate import assess
from travel_agent.models import CaveatKind, ClarificationRequest

CASES = EvalCase.load_all()


def test_all_cases_load():
    """R9: at least 9 cases, the 7 assignment examples plus contradictory and no-data ones."""
    assert len(CASES) >= 9


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_gold_constraints_satisfy_their_own_expectations(case):
    """The gold input for the planner must be a correct extraction, or the stages disagree."""
    scores = {s.dimension: s for s in score_extraction(case, case.gold_constraints)}

    assert scores["fields"].passed, scores["fields"].detail
    assert scores["routing"].passed, scores["routing"].detail


GATE_CAVEATS = {
    CaveatKind.FLIGHTS_NOT_PRICED,
    CaveatKind.ORIGIN_FROM_DEVICE,
    CaveatKind.DATES_ROLLED_FORWARD,
    CaveatKind.DATES_ASSUMED,
    CaveatKind.NO_BUDGET,
    CaveatKind.END_DATE_IGNORED,
}


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_expected_gate_caveats_are_exactly_what_the_gate_produces(case):
    """The gate is deterministic, so a case's expected gate caveats must match it exactly.

    Catches a wrong expectation (eval run 1: NO_BUDGET expected on a case with a nightly cap)
    without spending a model call. Planner-produced caveats (SOFT_BUDGET_EXCEEDED) are excluded.
    """
    brief = assess(case.gold_constraints, case.today, case.device_origin)
    produced = set() if isinstance(brief, ClarificationRequest) else {c.kind for c in brief.caveats}
    expected = set(case.planner_checks.expected_caveats) & GATE_CAVEATS

    assert expected == produced


def test_wrong_extraction_fails_fields_with_detail():
    """R9: a mismatched field fails the `fields` dimension and names the field."""
    case = next(c for c in CASES if c.id == "beach-jfk-tight-budget")
    wrong = case.gold_constraints.model_copy(update={"nights": 8, "origin": "SFO"})

    fields = score_extraction(case, wrong)[0]

    assert not fields.passed
    assert "nights=8" in fields.detail and "origin='SFO'" in fields.detail

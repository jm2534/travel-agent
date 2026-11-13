"""plan_trip with a scripted model: validation, retries, exhaustion and the result contract.

Baseline (see conftest): JFK -> Cancun, peak February, 7 nights, 2 adults.
F-JFK-CUN-1 + H-CUN-1 = $2600; F-JFK-CUN-1 + H-CUN-2 = $3965.
"""

import pytest
from conftest import make_brief
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from travel_agent.models import (
    Assumption,
    Budget,
    Caveat,
    CaveatKind,
    Infeasible,
    TripSuggestion,
    ViolationKind,
)
from travel_agent.plan import PLANNER_OUTPUT_RETRIES, plan_trip

models.ALLOW_MODEL_REQUESTS = False

VALID = {"destination_id": "CUN", "flight_id": "F-JFK-CUN-1", "hotel_id": "H-CUN-1",
         "reasoning": "Beach, in budget."}  # fmt: skip
PRICEY = {**VALID, "hotel_id": "H-CUN-2"}


class ScriptedPlanner:
    """A fake model that answers each request with the next scripted output (the last repeats)."""

    def __init__(self, *outputs: tuple[str, dict]):
        self.outputs = outputs
        self.requests: list[list] = []

    def __call__(self, messages: list, info: AgentInfo) -> ModelResponse:
        self.requests.append(messages)
        kind, args = self.outputs[min(len(self.requests), len(self.outputs)) - 1]
        tool = next(t for t in info.output_tools if t.name.endswith(kind))
        return ModelResponse(parts=[ToolCallPart(tool.name, args)])

    def saw_retry_mentioning(self, text: str) -> bool:
        """Whether the latest request fed a rejection containing `text` back to the model."""
        parts = [p for m in self.requests[-1] for p in getattr(m, "parts", [])]
        return any(
            "rejected" in str(getattr(p, "content", "")) and text in str(p.content) for p in parts
        )


def run(catalog, brief, script: ScriptedPlanner):
    return plan_trip(brief, FunctionModel(script), catalog)


def test_valid_proposal_becomes_priced_suggestion(catalog):
    """R6: TripSuggestion has a single option with a cost breakdown computed by code."""
    brief = make_brief(budget=Budget(amount_usd=3000, scope="total", hard=True))

    result = run(catalog, brief, ScriptedPlanner(("Proposal", VALID)))

    assert isinstance(result, TripSuggestion)
    assert result.option.proposal.hotel_id == "H-CUN-1"
    assert result.option.cost.total_usd == pytest.approx(2600)
    assert (result.depart_date, result.return_date) == (brief.depart_date, brief.return_date)


def test_gate_assumptions_and_caveats_carry_through(catalog):
    """R6: assumptions[] and caveats[] from the gate reach the user."""
    brief = make_brief(origin=None)
    brief.caveats.append(Caveat(kind=CaveatKind.FLIGHTS_NOT_PRICED, text="No origin."))
    brief.assumptions.append(Assumption(field="nights", value="5", reason="Not stated."))
    no_flight = {**VALID, "flight_id": None}

    result = run(catalog, brief, ScriptedPlanner(("Proposal", no_flight)))

    assert CaveatKind.FLIGHTS_NOT_PRICED in {c.kind for c in result.caveats}
    assert [a.field for a in result.assumptions] == ["nights"]
    assert result.option.cost.flights_usd is None


def test_soft_budget_overrun_is_flagged_not_retried(catalog):
    """R5: soft budgets never trigger a retry; over one -> SOFT_BUDGET_EXCEEDED caveat."""
    brief = make_brief(budget=Budget(amount_usd=2000, scope="total", hard=False))
    script = ScriptedPlanner(("Proposal", VALID))

    result = run(catalog, brief, script)

    assert isinstance(result, TripSuggestion)
    assert len(script.requests) == 1
    assert CaveatKind.SOFT_BUDGET_EXCEEDED in {c.kind for c in result.caveats}


def test_rejected_proposal_is_retried_with_the_reason(catalog):
    """R5: a broken hard constraint goes back to the model as ModelRetry."""
    brief = make_brief(budget=Budget(amount_usd=3000, scope="total", hard=True))
    script = ScriptedPlanner(("Proposal", PRICEY), ("Proposal", VALID))

    result = run(catalog, brief, script)

    assert isinstance(result, TripSuggestion)
    assert result.option.proposal.hotel_id == "H-CUN-1"
    assert script.saw_retry_mentioning("OVER_BUDGET")


def test_exhausted_retries_return_infeasible_with_closest(catalog):
    """R5: retries run out (N=3) -> Infeasible from the last rejected attempt, re-priced."""
    brief = make_brief(budget=Budget(amount_usd=3000, scope="total", hard=True))
    script = ScriptedPlanner(("Proposal", PRICEY))

    result = run(catalog, brief, script)

    assert isinstance(result, Infeasible)
    assert len(script.requests) == 1 + PLANNER_OUTPUT_RETRIES == 4
    assert result.closest.proposal.hotel_id == "H-CUN-2"
    assert result.closest.cost.total_usd == pytest.approx(3965)
    assert [v.kind for v in result.violations] == [ViolationKind.OVER_BUDGET]


def test_planner_infeasible_is_priced_by_code(catalog):
    """R5: the planner returns Infeasible directly; code prices its closest option's IDs."""
    brief = make_brief(budget=Budget(amount_usd=3000, scope="total", hard=True))
    script = ScriptedPlanner(("NoFeasiblePlan", {"closest": PRICEY, "reason": "Too pricey."}))

    result = run(catalog, brief, script)

    assert isinstance(result, Infeasible)
    assert result.closest.cost.total_usd == pytest.approx(3965)
    assert [v.kind for v in result.violations] == [ViolationKind.OVER_BUDGET]
    assert result.reason == "Too pricey."


def test_no_data_at_all_is_infeasible_without_closest(catalog):
    """R5: nothing matched -> Infeasible with no closest option, never a hallucinated plan."""
    script = ScriptedPlanner(("NoFeasiblePlan", {"closest": None, "reason": "No data."}))

    result = run(catalog, make_brief(), script)

    assert isinstance(result, Infeasible)
    assert result.closest is None
    assert [v.kind for v in result.violations] == [ViolationKind.NO_DATA]

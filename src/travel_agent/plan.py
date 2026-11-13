"""Stage 3: the planner agent. The LLM explores with tools and picks IDs; code prices and enforces.

The tool wrappers bind what the brief already fixes (origin, dates, party size) from deps, so the
model only chooses what is actually its call: where to go, and which flight and hotel.
"""

from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext

from travel_agent import tools
from travel_agent.catalog import Catalog
from travel_agent.models import (
    AirportCode,
    DestinationId,
    Infeasible,
    NoFeasiblePlan,
    PlanningBrief,
    Proposal,
    Region,
    Tag,
    TripSuggestion,
    Violation,
)
from travel_agent.pricing import check_proposal
from travel_agent.prompts import PLANNER_INSTRUCTIONS

PLANNER_OUTPUT_RETRIES = 3


@dataclass
class PlannerDeps:
    """Per-run state for the planner.

    Attributes:
        catalog: Inventory the tools query.
        brief: The constraints being planned against.
        last_rejected: The most recent proposal the validator rejected, and why. It becomes
            Infeasible.closest once retries run out.
    """

    catalog: Catalog
    brief: PlanningBrief
    last_rejected: tuple[Proposal, list[Violation]] | None = None


planner = Agent(
    deps_type=PlannerDeps,
    output_type=[Proposal, NoFeasiblePlan],
    instructions=PLANNER_INSTRUCTIONS,
    retries={"output": PLANNER_OUTPUT_RETRIES},
)


@planner.tool
def find_destinations(
    ctx: RunContext[PlannerDeps],
    preferences: list[Tag],
    region: Region | None = None,
    near: AirportCode | None = None,
    name: str | None = None,
) -> list[tools.DestinationMatch]:
    """Find candidate destinations for the brief's travel month.

    Args:
        ctx: Run context.
        preferences: Tags to match; more overlap ranks higher.
        region: Restrict to one region.
        near: IATA code; only destinations within ~1500 km of it.
        name: Look up one specific city by name or IATA code instead of filtering.
    """
    month = ctx.deps.brief.depart_date.month
    return tools.find_destinations(ctx.deps.catalog, month, preferences, region, near, name)


@planner.tool
def search_flights(
    ctx: RunContext[PlannerDeps], destination: DestinationId
) -> list[tools.FlightQuote]:
    """Round-trip fares from the brief's origin on its dates, priced for the whole party.

    An empty list means no route, or the brief has no origin.

    Args:
        ctx: Run context.
        destination: Destination id from find_destinations.
    """
    brief = ctx.deps.brief
    if brief.origin is None:
        return []
    return tools.search_flights(
        ctx.deps.catalog, brief.origin, destination, brief.depart_date, _party_size(brief)
    )


@planner.tool
def search_hotels(ctx: RunContext[PlannerDeps], city: DestinationId) -> list[tools.HotelQuote]:
    """Hotels for the brief's stay, priced for the whole party. [] means no data for that city.

    Args:
        ctx: Run context.
        city: Destination id from find_destinations.
    """
    brief = ctx.deps.brief
    return tools.search_hotels(
        ctx.deps.catalog, city, brief.depart_date, brief.nights, _party_size(brief)
    )


@planner.tool
def quote_trip(ctx: RunContext[PlannerDeps], proposal: Proposal) -> tools.TripQuote:
    """Price a candidate and list its hard-constraint violations, exactly as the final check will.

    Args:
        ctx: Run context.
        proposal: The candidate to check.
    """
    return tools.quote_trip(ctx.deps.catalog, ctx.deps.brief, proposal)


@planner.output_validator
def enforce_constraints(
    ctx: RunContext[PlannerDeps], output: Proposal | NoFeasiblePlan
) -> Proposal | NoFeasiblePlan:
    """Business rules live here, not in the prompt; a violation goes back to the model to retry."""
    if isinstance(output, NoFeasiblePlan):
        return output
    violations = check_proposal(ctx.deps.catalog, ctx.deps.brief, output)
    if violations:
        ctx.deps.last_rejected = (output, violations)
        details = "; ".join(f"{v.kind}: {v.detail}" for v in violations)
        raise ModelRetry(f"Proposal rejected: {details}")
    return output


def _party_size(brief: PlanningBrief) -> int:
    """Total travellers, adults plus children."""
    return brief.travellers.adults + len(brief.travellers.children_ages)


def plan_trip(brief: PlanningBrief, model: str, catalog: Catalog) -> TripSuggestion | Infeasible:
    """Run the planner and turn its output into a priced, user-facing result.

    A Proposal becomes a TripSuggestion (adding SOFT_BUDGET_EXCEEDED if over a soft budget). A
    NoFeasiblePlan becomes an Infeasible, with `closest` priced by code. If retries run out, the
    Infeasible is built from deps.last_rejected.

    Args:
        brief: Resolved constraints from the gate.
        model: pydantic-ai model string.
        catalog: Inventory for the tools and pricing.

    Raises:
        pydantic_ai.ModelAPIError: Provider failures; agent.py maps them to AgentError.
    """
    raise NotImplementedError

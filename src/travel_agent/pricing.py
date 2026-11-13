"""The single source of truth for cost, used by the tools (quotes) and the planner's validator."""

from travel_agent.catalog import Catalog, Destination, Hotel
from travel_agent.models import (
    Budget,
    CostBreakdown,
    PlanningBrief,
    Proposal,
    Violation,
    ViolationKind,
)

APPROXIMATE_TOLERANCE = 0.10


def price_proposal(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> CostBreakdown:
    """Full cost of a proposal: flights for everyone plus enough hotel rooms for everyone.

    Args:
        catalog: Inventory to look the IDs up in.
        brief: Supplies the dates, nights and party size.
        proposal: The IDs to price.

    Raises:
        KeyError: If any ID isn't in the catalog. Call check_proposal first.
    """
    destination = catalog.destinations[proposal.destination_id]
    hotel = catalog.hotels[proposal.hotel_id]
    nightly = hotel.nightly_rate(destination, brief.depart_date)
    rooms = hotel.rooms_for(brief.party_size)
    hotel_usd = hotel.stay_total(destination, brief.depart_date, brief.nights, brief.party_size)

    flights_usd = None
    if proposal.flight_id is not None:
        flight = catalog.flights[proposal.flight_id]
        flights_usd = flight.price_for(destination, brief.depart_date, brief.party_size)

    return CostBreakdown(
        flights_usd=flights_usd,
        hotel_usd=hotel_usd,
        total_usd=round(hotel_usd + (flights_usd or 0), 2),
        hotel_nightly_usd=nightly,
        rooms=rooms,
    )


def check_proposal(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> list[Violation]:
    """Every hard constraint a proposal breaks. An empty list means it's valid.

    Checks: the IDs exist and agree with each other, the destination isn't excluded, the hard
    budget holds (10% tolerance when approximate), plus the hotel nightly cap, required amenities,
    min stars and style. A soft budget is never a violation. If the IDs are bad, only those
    violations are returned, since nothing else can be checked.

    Args:
        catalog: Inventory to look the IDs up in.
        brief: The constraints to check against.
        proposal: The planner's pick.
    """
    id_violations = _id_violations(catalog, brief, proposal)
    if id_violations:
        return id_violations

    destination = catalog.destinations[proposal.destination_id]
    hotel = catalog.hotels[proposal.hotel_id]
    return (
        _exclusion_violations(brief, destination)
        + _hotel_requirement_violations(brief, hotel)
        + _budget_violations(brief, price_proposal(catalog, brief, proposal))
    )


def _id_violations(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> list[Violation]:
    """Unknown IDs, IDs that disagree with each other or the brief, or a missing flight."""
    violations = []
    destination_id = proposal.destination_id
    for kind, id_, known in [
        ("destination", destination_id, catalog.destinations),
        ("hotel", proposal.hotel_id, catalog.hotels),
        ("flight", proposal.flight_id, catalog.flights),
    ]:
        if id_ is not None and id_ not in known:
            violations.append(_violation(ViolationKind.UNKNOWN_ID, f"No {kind} with id {id_}."))
    if violations:
        return violations

    hotel = catalog.hotels[proposal.hotel_id]
    if hotel.city != destination_id:
        detail = f"Hotel {hotel.id} is in {hotel.city}, not {destination_id}."
        violations.append(_violation(ViolationKind.ID_MISMATCH, detail))

    if proposal.flight_id is not None:
        flight = catalog.flights[proposal.flight_id]
        if (flight.origin, flight.destination) != (brief.origin, destination_id):
            detail = (
                f"Flight {flight.id} is {flight.origin}->{flight.destination}, "
                f"not {brief.origin}->{destination_id}."
            )
            violations.append(_violation(ViolationKind.ID_MISMATCH, detail))
    elif brief.origin is not None:
        detail = f"The trip starts at {brief.origin}, so a flight is required."
        violations.append(_violation(ViolationKind.MISSING_FLIGHT, detail))
    return violations


def _exclusion_violations(brief: PlanningBrief, destination: Destination) -> list[Violation]:
    """The destination matches a place the user ruled out (by id, or by name, ignoring case)."""
    for excluded in brief.constraints.excluded_destinations:
        term = excluded.casefold()
        if term == destination.id.casefold() or term in destination.name.casefold():
            detail = f"The user ruled out {excluded}."
            return [_violation(ViolationKind.EXCLUDED_DESTINATION, detail)]
    return []


def _hotel_requirement_violations(brief: PlanningBrief, hotel: Hotel) -> list[Violation]:
    """Stated hotel requirements the hotel doesn't meet."""
    required = brief.constraints.hotel
    violations = []
    missing = [a for a in required.amenities if a not in hotel.amenities]
    if missing:
        detail = f"{hotel.id} lacks {', '.join(missing)}."
        violations.append(_violation(ViolationKind.MISSING_AMENITY, detail))
    if required.min_stars is not None and hotel.stars < required.min_stars:
        detail = f"{hotel.id} is {hotel.stars}-star; at least {required.min_stars} required."
        violations.append(_violation(ViolationKind.BELOW_MIN_STARS, detail))
    if required.style is not None and hotel.style != required.style:
        detail = f"{hotel.id} is a {hotel.style} hotel; {required.style} required."
        violations.append(_violation(ViolationKind.WRONG_STYLE, detail))
    return violations


def spend_against(budget: Budget, cost: CostBreakdown) -> tuple[float, str]:
    """What a budget's scope measures in this cost, and a label for it.

    Args:
        budget: The user's budget; only its scope matters here.
        cost: A priced proposal.

    Returns:
        (amount spent under that scope, human label), e.g. (2600.0, "Total").
    """
    if budget.scope == "total":
        return cost.total_usd, "Total"
    if budget.scope == "excluding_flights":
        return cost.hotel_usd, "Hotel total"
    return cost.hotel_nightly_usd, "Nightly rate"


def _budget_violations(brief: PlanningBrief, cost: CostBreakdown) -> list[Violation]:
    """A hard budget exceeded for its scope. Soft budgets are reported as caveats by plan.py."""
    budget = brief.constraints.budget
    if budget is None or not budget.hard:
        return []

    cap = budget.amount_usd * (1 + APPROXIMATE_TOLERANCE if budget.approximate else 1)
    spent, label = spend_against(budget, cost)
    if spent <= cap:
        return []
    is_nightly = budget.scope == "hotel_per_night"
    kind = ViolationKind.OVER_NIGHTLY_CAP if is_nightly else ViolationKind.OVER_BUDGET
    return [_violation(kind, f"{label} ${spent:,.0f} exceeds the ${cap:,.0f} limit.")]


def _violation(kind: ViolationKind, detail: str) -> Violation:
    """Shorthand for building a Violation."""
    return Violation(kind=kind, detail=detail)

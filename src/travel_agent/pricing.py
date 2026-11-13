"""The single source of truth for cost, used by the tools (quotes) and the planner's validator."""

import math
from datetime import date

from travel_agent.catalog import Catalog, Destination, Flight, Hotel
from travel_agent.models import (
    CostBreakdown,
    PlanningBrief,
    Proposal,
    Violation,
    ViolationKind,
)

PEAK_MULTIPLIER = 1.3
APPROXIMATE_TOLERANCE = 0.10


def season_multiplier(destination: Destination, on: date) -> float:
    """Price multiplier for a date: PEAK_MULTIPLIER in the destination's peak months, else 1.0."""
    return PEAK_MULTIPLIER if on.month in destination.peak_months else 1.0


def flight_price(flight: Flight, destination: Destination, depart: date, travellers: int) -> float:
    """Round-trip fare for the whole party, adjusted for season at departure.

    Args:
        flight: The fare.
        destination: Its destination, for the season.
        depart: Departure date.
        travellers: Party size; children pay full fare.
    """
    return round(flight.base_fare_usd * season_multiplier(destination, depart) * travellers, 2)


def hotel_nightly(hotel: Hotel, destination: Destination, check_in: date) -> float:
    """Price per room-night, adjusted for season at check-in."""
    return round(hotel.base_nightly_usd * season_multiplier(destination, check_in), 2)


def rooms_needed(hotel: Hotel, guests: int) -> int:
    """Enough rooms for everyone, given the hotel's per-room capacity."""
    return math.ceil(guests / hotel.sleeps)


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
    nightly = hotel_nightly(hotel, destination, brief.depart_date)
    rooms = rooms_needed(hotel, brief.party_size)
    hotel_usd = round(nightly * rooms * brief.nights, 2)

    flights_usd = None
    if proposal.flight_id is not None:
        flight = catalog.flights[proposal.flight_id]
        flights_usd = flight_price(flight, destination, brief.depart_date, brief.party_size)

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


def _budget_violations(brief: PlanningBrief, cost: CostBreakdown) -> list[Violation]:
    """A hard budget exceeded for its scope. Soft budgets are reported later as caveats."""
    budget = brief.constraints.budget
    if budget is None or not budget.hard:
        return []

    cap = budget.amount_usd * (1 + APPROXIMATE_TOLERANCE if budget.approximate else 1)
    if budget.scope == "total":
        spent, kind, label = cost.total_usd, ViolationKind.OVER_BUDGET, "Total"
    elif budget.scope == "excluding_flights":
        spent, kind, label = cost.hotel_usd, ViolationKind.OVER_BUDGET, "Hotel total"
    else:
        spent, kind, label = cost.hotel_nightly_usd, ViolationKind.OVER_NIGHTLY_CAP, "Nightly rate"

    if spent > cap:
        return [_violation(kind, f"{label} ${spent:,.0f} exceeds the ${cap:,.0f} limit.")]
    return []


def _violation(kind: ViolationKind, detail: str) -> Violation:
    """Shorthand for building a Violation."""
    return Violation(kind=kind, detail=detail)

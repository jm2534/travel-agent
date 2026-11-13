"""Code-computed cost and hard-constraint checks for planner proposals.

Baseline: JFK -> Cancun in peak February, 7 nights, 2 adults, F-JFK-CUN-1 ($780) + H-CUN-1
($260/night, 1 room, $1820) = $2600.
"""

import pytest
from conftest import make_brief

from travel_agent.models import Budget, HotelRequirements, Proposal, Travellers, ViolationKind
from travel_agent.pricing import check_proposal, price_proposal
from travel_agent.tools import quote_trip

OVER_BUDGET = [ViolationKind.OVER_BUDGET]
OVER_NIGHTLY_CAP = [ViolationKind.OVER_NIGHTLY_CAP]


def proposal(destination="CUN", flight="F-JFK-CUN-1", hotel="H-CUN-1") -> Proposal:
    return Proposal(destination_id=destination, flight_id=flight, hotel_id=hotel, reasoning="r")


def violation_kinds(catalog, brief, prop) -> list[ViolationKind]:
    return [v.kind for v in check_proposal(catalog, brief, prop)]


def test_price_includes_flights_for_party_and_hotel_rooms(catalog):
    """R5: code computes cost from the mock data; the model never does the arithmetic."""
    cost = price_proposal(catalog, make_brief(), proposal())

    assert (cost.flights_usd, cost.hotel_usd, cost.total_usd) == pytest.approx((780, 1820, 2600))
    assert (cost.hotel_nightly_usd, cost.rooms) == (pytest.approx(260), 1)


def test_price_without_flight_is_hotel_only(catalog):
    """R3/R5: no origin -> flights not priced; total is the hotel."""
    cost = price_proposal(catalog, make_brief(origin=None), proposal(flight=None))

    assert cost.flights_usd is None
    assert cost.total_usd == pytest.approx(1820)


def test_valid_proposal_has_no_violations(catalog):
    """R5: a proposal meeting every hard constraint passes."""
    brief = make_brief(budget=Budget(amount_usd=2600, scope="total", hard=True))

    assert violation_kinds(catalog, brief, proposal()) == []


@pytest.mark.parametrize(
    ("budget", "expected"),
    [
        (Budget(amount_usd=2500, scope="total", hard=True), OVER_BUDGET),
        (Budget(amount_usd=2400, scope="total", hard=True, approximate=True), []),
        (Budget(amount_usd=2300, scope="total", hard=True, approximate=True), OVER_BUDGET),
        (Budget(amount_usd=1000, scope="total", hard=False), []),
        (Budget(amount_usd=1800, scope="excluding_flights", hard=True), OVER_BUDGET),
        (Budget(amount_usd=1900, scope="excluding_flights", hard=True), []),
        (Budget(amount_usd=250, scope="hotel_per_night", hard=True), OVER_NIGHTLY_CAP),
        (Budget(amount_usd=260, scope="hotel_per_night", hard=True), []),
        (Budget(amount_usd=240, scope="hotel_per_night", hard=True, approximate=True), []),
    ],
    ids=[
        "total-over", "approximate-within-10pct", "approximate-beyond-10pct", "soft-never-violates",
        "excl-flights-over", "excl-flights-ignores-airfare", "nightly-over", "nightly-at-cap",
        "nightly-approximate-within-10pct",
    ],
)  # fmt: skip
def test_hard_budget_caps(catalog, budget, expected):
    """R5: a hard cap exceeded -> retry; approximate allows 10%; soft budgets never trigger one."""
    assert violation_kinds(catalog, make_brief(budget=budget), proposal()) == expected


@pytest.mark.parametrize(
    ("requirements", "hotel", "expected"),
    [
        (HotelRequirements(amenities=["pool"]), "H-CUN-2", ViolationKind.MISSING_AMENITY),
        (HotelRequirements(min_stars=5), "H-CUN-1", ViolationKind.BELOW_MIN_STARS),
        (HotelRequirements(style="boutique"), "H-CUN-1", ViolationKind.WRONG_STYLE),
    ],
    ids=["amenity", "stars", "style"],
)
def test_unmet_hotel_requirement(catalog, requirements, hotel, expected):
    """R5: a stated hotel requirement (amenity, min stars, style) unmet -> retry."""
    brief = make_brief(hotel=requirements)

    assert violation_kinds(catalog, brief, proposal(hotel=hotel)) == [expected]


def test_excluded_destination_rejected_case_insensitively(catalog):
    """R5: an excluded destination is chosen -> retry ("We hated Santorini")."""
    brief = make_brief(origin=None, excluded_destinations=["santorini"])

    kinds = violation_kinds(catalog, brief, proposal("JTR", flight=None, hotel="H-JTR-1"))

    assert kinds == [ViolationKind.EXCLUDED_DESTINATION]


@pytest.mark.parametrize(
    ("prop", "origin", "expected"),
    [
        (proposal(hotel="H-CUN-9"), "JFK", ViolationKind.UNKNOWN_ID),
        (proposal(flight="F-JFK-CUN-9"), "JFK", ViolationKind.UNKNOWN_ID),
        (proposal(destination="XXX"), "JFK", ViolationKind.UNKNOWN_ID),
        (proposal(hotel="H-OPO-1"), "JFK", ViolationKind.ID_MISMATCH),
        (proposal(flight="F-JFK-OPO-1"), "JFK", ViolationKind.ID_MISMATCH),
        (proposal(), "SFO", ViolationKind.ID_MISMATCH),
        (proposal(flight=None), "JFK", ViolationKind.MISSING_FLIGHT),
    ],
    ids=[
        "unknown-hotel", "unknown-flight", "unknown-destination", "hotel-in-other-city",
        "flight-to-other-city", "flight-from-other-origin", "no-flight-despite-origin",
    ],
)  # fmt: skip
def test_ids_must_exist_and_agree(catalog, prop, origin, expected):
    """R5: an ID is unknown, IDs disagree, or a flight is missing while the brief has an origin."""
    assert expected in violation_kinds(catalog, make_brief(origin=origin), prop)


def test_family_needs_two_rooms_in_small_hotel(catalog):
    """R5: rooms for everyone; a family of 4 in rooms sleeping 2 pays for 2 rooms."""
    brief = make_brief(travellers=Travellers(adults=2, children_ages=[6, 9]))

    cost = price_proposal(catalog, brief, proposal(hotel="H-CUN-2"))

    assert cost.rooms == 2
    assert cost.flights_usd == pytest.approx(1560)


def test_quote_trip_reports_unknown_ids_instead_of_raising(catalog):
    """R5: quote_trip matches the validator; tools return typed errors, never raw exceptions."""
    quote = quote_trip(catalog, make_brief(), proposal(hotel="H-CUN-9"))

    assert quote.cost is None
    assert [v.kind for v in quote.violations] == [ViolationKind.UNKNOWN_ID]


def test_quote_trip_prices_valid_proposal(catalog):
    """R5: quote_trip returns exactly what the validator computes."""
    quote = quote_trip(catalog, make_brief(), proposal())

    assert quote.cost.total_usd == pytest.approx(2600)
    assert quote.violations == []


def test_nightly_cap_is_per_room_not_per_party(catalog):
    """R5: `hotel_per_night` checks the room-night rate; 4 guests in 2 rooms at $455 fit $500."""
    brief = make_brief(
        travellers=Travellers(adults=2, children_ages=[6, 9]),
        budget=Budget(amount_usd=500, scope="hotel_per_night", hard=True),
    )

    assert violation_kinds(catalog, brief, proposal(hotel="H-CUN-2")) == []


def test_met_hotel_requirements_pass(catalog):
    """R5: a hotel meeting every stated requirement (amenity, min stars, style) passes."""
    brief = make_brief(hotel=HotelRequirements(amenities=["pool"], min_stars=4, style="resort"))

    assert violation_kinds(catalog, brief, proposal(hotel="H-CUN-1")) == []


def test_exclusion_matches_iata_code(catalog):
    """R5: an exclusion matches an exact IATA code as well as a name."""
    brief = make_brief(origin=None, excluded_destinations=["JTR"])

    kinds = violation_kinds(catalog, brief, proposal("JTR", flight=None, hotel="H-JTR-1"))

    assert kinds == [ViolationKind.EXCLUDED_DESTINATION]


def test_non_excluded_destination_passes(catalog):
    """R5: exclusions only reject the places named."""
    brief = make_brief(excluded_destinations=["Santorini"])

    assert violation_kinds(catalog, brief, proposal()) == []

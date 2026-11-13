"""The single source of truth for cost, used by the tools (quotes) and the planner's validator."""

from datetime import date

from travel_agent.catalog import Catalog, Destination, Flight, Hotel
from travel_agent.models import CostBreakdown, PlanningBrief, Proposal, Violation

PEAK_MULTIPLIER = 1.3
APPROXIMATE_TOLERANCE = 0.10


def season_multiplier(destination: Destination, on: date) -> float:
    """Price multiplier for a date: PEAK_MULTIPLIER in the destination's peak months, else 1.0."""
    raise NotImplementedError


def flight_price(flight: Flight, destination: Destination, depart: date, travellers: int) -> float:
    """Round-trip fare for the whole party, adjusted for season at departure.

    Args:
        flight: The fare.
        destination: Its destination, for the season.
        depart: Departure date.
        travellers: Party size; children pay full fare.
    """
    raise NotImplementedError


def hotel_nightly(hotel: Hotel, destination: Destination, check_in: date) -> float:
    """Price per room-night, adjusted for season at check-in."""
    raise NotImplementedError


def price_proposal(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> CostBreakdown:
    """Full cost of a proposal: flights for everyone plus enough hotel rooms for everyone.

    Args:
        catalog: Inventory to look the IDs up in.
        brief: Supplies the dates, nights and party size.
        proposal: The IDs to price.

    Raises:
        KeyError: If any ID isn't in the catalog. Call check_proposal first.
    """
    raise NotImplementedError


def check_proposal(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> list[Violation]:
    """Every hard constraint a proposal breaks. An empty list means it's valid.

    Checks: the IDs exist and agree with each other, the destination isn't excluded, the hard
    budget holds (10% tolerance when approximate), plus the hotel nightly cap, required amenities
    and min stars. A soft budget is never a violation.

    Args:
        catalog: Inventory to look the IDs up in.
        brief: The constraints to check against.
        proposal: The planner's pick.
    """
    raise NotImplementedError

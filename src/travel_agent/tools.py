"""Planner tools: typed queries over the mock catalog. An empty result is an answer, not an error.

These take a Catalog directly, so they're testable without an agent; plan.py registers them.
"""

from datetime import date

from pydantic import BaseModel

from travel_agent.catalog import Catalog, Destination, Flight, Hotel
from travel_agent.models import (
    AirportCode,
    CostBreakdown,
    DestinationId,
    PlanningBrief,
    Proposal,
    Region,
    Tag,
    Violation,
)


class DestinationMatch(BaseModel):
    destination: Destination
    avg_high_c: float
    matched_tags: list[Tag]


class FlightQuote(BaseModel):
    flight: Flight
    total_usd: float


class HotelQuote(BaseModel):
    hotel: Hotel
    nightly_usd: float
    rooms: int
    total_usd: float


class TripQuote(BaseModel):
    cost: CostBreakdown | None
    violations: list[Violation]


def find_destinations(
    catalog: Catalog,
    month: int,
    preferences: list[Tag],
    region: Region | None = None,
    near: AirportCode | None = None,
    name: str | None = None,
) -> list[DestinationMatch]:
    """Destinations matching the filters, best tag overlap first.

    Exclusions are not filtered here; the validator enforces them.

    Args:
        catalog: Inventory to search.
        month: Travel month, for the reported temperature.
        preferences: Tags to rank by overlap.
        region: Only this region.
        near: Only destinations within ~1500 km of this airport.
        name: Look up one city by name or IATA code, ignoring the other filters.
    """
    raise NotImplementedError


def search_flights(
    catalog: Catalog,
    origin: AirportCode,
    destination: DestinationId,
    depart: date,
    travellers: int,
) -> list[FlightQuote]:
    """Every round-trip fare on the route, priced for the party, cheapest first. [] if no route."""
    raise NotImplementedError


def search_hotels(
    catalog: Catalog, city: DestinationId, check_in: date, nights: int, guests: int
) -> list[HotelQuote]:
    """Every hotel in the city, priced for the stay and party, cheapest first. [] if unknown."""
    raise NotImplementedError


def quote_trip(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> TripQuote:
    """Exactly what the validator will compute: cost (None if an ID is unknown) and violations."""
    raise NotImplementedError

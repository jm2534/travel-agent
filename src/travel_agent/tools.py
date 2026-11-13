"""Planner tools: typed queries over the mock catalog. An empty result is an answer, not an error.

These take a Catalog directly, so they're testable without an agent; plan.py registers them.
"""

import math
from datetime import date
from typing import Self

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
    ViolationKind,
)
from travel_agent.pricing import check_proposal, price_proposal

NEAR_RADIUS_KM = 1500
ORIGIN_AIRPORT_COORDS = {"JFK": (40.64, -73.78), "SFO": (37.62, -122.38), "LIS": (38.77, -9.13)}


class DestinationMatch(BaseModel):
    destination: Destination
    avg_high_c: float
    matched_tags: list[Tag]

    @classmethod
    def of(cls, destination: Destination, month: int, preferences: list[Tag]) -> Self:
        """A destination annotated with its weather that month and the preferences it meets."""
        return cls(
            destination=destination,
            avg_high_c=destination.avg_high_c[month - 1],
            matched_tags=[t for t in preferences if t in destination.tags],
        )


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

    With preferences, destinations matching none of them are dropped. Exclusions are not filtered
    here; the validator enforces them.

    Args:
        catalog: Inventory to search.
        month: Travel month, for the reported temperature.
        preferences: Tags to rank by overlap.
        region: Only this region.
        near: Only destinations within NEAR_RADIUS_KM of this airport. [] if it's unknown.
        name: Look up one city by name or IATA code, ignoring the other filters.
    """
    if name is not None:
        term = name.casefold()
        found = [
            d
            for d in catalog.destinations.values()
            if term == d.id.casefold() or term in d.name.casefold()
        ]
        return [DestinationMatch.of(d, month, preferences) for d in found]

    candidates = list(catalog.destinations.values())
    if region is not None:
        candidates = [d for d in candidates if d.region == region]
    if near is not None:
        center = _coords_of(catalog, near)
        if center is None:
            return []
        candidates = [
            d for d in candidates if 0 < _distance_km(center, (d.lat, d.lon)) <= NEAR_RADIUS_KM
        ]

    matches = [DestinationMatch.of(d, month, preferences) for d in candidates]
    if preferences:
        matches = [m for m in matches if m.matched_tags]
    return sorted(matches, key=lambda m: (-len(m.matched_tags), m.destination.id))


def search_flights(
    catalog: Catalog,
    origin: AirportCode,
    destination: DestinationId,
    depart: date,
    travellers: int,
) -> list[FlightQuote]:
    """Every round-trip fare on the route, priced for the party, cheapest first. [] if no route."""
    dest = catalog.destinations.get(destination)
    if dest is None:
        return []
    quotes = [
        FlightQuote(flight=f, total_usd=f.price_for(dest, depart, travellers))
        for f in catalog.flights.values()
        if f.origin == origin and f.destination == destination
    ]
    return sorted(quotes, key=lambda q: q.total_usd)


def search_hotels(
    catalog: Catalog, city: DestinationId, check_in: date, nights: int, guests: int
) -> list[HotelQuote]:
    """Every hotel in the city, priced for the stay and party, cheapest first. [] if unknown."""
    dest = catalog.destinations.get(city)
    if dest is None:
        return []
    quotes = []
    for hotel in catalog.hotels.values():
        if hotel.city != city:
            continue
        nightly = hotel.nightly_rate(dest, check_in)
        rooms = hotel.rooms_for(guests)
        total = hotel.stay_total(dest, check_in, nights, guests)
        quotes.append(HotelQuote(hotel=hotel, nightly_usd=nightly, rooms=rooms, total_usd=total))
    return sorted(quotes, key=lambda q: q.total_usd)


def quote_trip(catalog: Catalog, brief: PlanningBrief, proposal: Proposal) -> TripQuote:
    """Exactly what the validator will compute: cost (None if an ID is unknown) and violations."""
    violations = check_proposal(catalog, brief, proposal)
    if any(v.kind == ViolationKind.UNKNOWN_ID for v in violations):
        return TripQuote(cost=None, violations=violations)
    return TripQuote(cost=price_proposal(catalog, brief, proposal), violations=violations)


def _coords_of(catalog: Catalog, airport: AirportCode) -> tuple[float, float] | None:
    """Coordinates of a destination or a known origin airport; None if unknown."""
    if airport in catalog.destinations:
        destination = catalog.destinations[airport]
        return destination.lat, destination.lon
    return ORIGIN_AIRPORT_COORDS.get(airport)


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle (haversine) distance in km."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    half_chord = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(half_chord))

"""Mock tools over the test catalog. Prices: Cancun is peak (x1.3) in February."""

import pytest
from conftest import OFF_PEAK_MAY, PEAK_FEB

from travel_agent.tools import find_destinations, search_flights, search_hotels


def test_flights_priced_for_party_and_season_cheapest_first(catalog):
    """R4: search_flights("JFK","CUN",...) -> >=2 fares, cheapest first."""
    quotes = search_flights(catalog, "JFK", "CUN", PEAK_FEB, travellers=2)

    assert [q.flight.id for q in quotes] == ["F-JFK-CUN-1", "F-JFK-CUN-2"]
    assert [q.total_usd for q in quotes] == pytest.approx([780, 1170])


def test_flights_off_peak_use_base_fare(catalog):
    """R4: price adjusted for season by code; off-peak is the base fare."""
    quotes = search_flights(catalog, "JFK", "CUN", OFF_PEAK_MAY, travellers=2)

    assert quotes[0].total_usd == pytest.approx(600)


@pytest.mark.parametrize(("origin", "destination"), [("JFK", "XXX"), ("SFO", "CUN")])
def test_unknown_route_returns_empty(catalog, origin, destination):
    """R4: search_flights("JFK","XXX",...) -> []."""
    assert search_flights(catalog, origin, destination, PEAK_FEB, travellers=2) == []


def test_hotels_priced_with_enough_rooms_cheapest_first(catalog):
    """R4: 4 guests in a hotel whose rooms sleep 2 -> priced as 2 rooms."""
    quotes = search_hotels(catalog, "CUN", PEAK_FEB, nights=7, guests=4)

    assert [(q.hotel.id, q.rooms) for q in quotes] == [("H-CUN-1", 1), ("H-CUN-2", 2)]
    assert [q.nightly_usd for q in quotes] == pytest.approx([260, 455])
    assert [q.total_usd for q in quotes] == pytest.approx([1820, 6370])


def test_unknown_city_has_no_hotels(catalog):
    """R4: unknown city -> []."""
    assert search_hotels(catalog, "XXX", PEAK_FEB, nights=3, guests=2) == []


def test_destinations_ranked_by_tag_overlap(catalog):
    """R4: candidates with tags; more overlap ranks first, no overlap is dropped."""
    matches = find_destinations(catalog, month=2, preferences=["beach", "family"])

    assert [m.destination.id for m in matches] == ["CUN", "JTR"]
    assert matches[0].matched_tags == ["beach", "family"]
    assert matches[0].avg_high_c == 21.0


def test_destinations_filtered_by_region(catalog):
    """R4: region filter; no preferences means every destination in the region."""
    matches = find_destinations(catalog, month=5, preferences=[], region="europe")

    assert {m.destination.id for m in matches} == {"OPO", "JTR", "LYS", "FCO"}


def test_destinations_near_an_origin_airport(catalog):
    """R4: find_destinations(near="LIS") -> only destinations within 1500 km (Lyon in, Rome out)."""
    matches = find_destinations(catalog, month=10, preferences=[], near="LIS")

    assert [m.destination.id for m in matches] == ["LYS", "OPO"]


def test_destinations_near_unknown_airport_is_empty(catalog):
    """R4: an unknown city returns [], not an error."""
    assert find_destinations(catalog, month=10, preferences=[], near="XXX") == []


@pytest.mark.parametrize(
    ("name", "expected"), [("porto", ["OPO"]), ("OPO", ["OPO"]), ("Reykjavik", [])]
)
def test_destination_lookup_by_name(catalog, name, expected):
    """R4: lookup by city name or IATA code; no data -> [], not an error."""
    matches = find_destinations(catalog, month=5, preferences=["beach"], name=name)

    assert [m.destination.id for m in matches] == expected

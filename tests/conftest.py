"""A small hand-written catalog, so tests don't depend on the generated fixtures."""

from datetime import date, timedelta

import pytest

from travel_agent.catalog import Catalog, Destination, Flight, Hotel
from travel_agent.models import PlanningBrief, Travellers, TripConstraints

PEAK_FEB = date(2027, 2, 1)  # Cancun is in peak season
OFF_PEAK_MAY = date(2027, 5, 3)


def _destination(id, name, region, lat, lon, tags, peak_months, touristiness=3):
    return Destination(
        id=id,
        name=name,
        country="X",
        region=region,
        lat=lat,
        lon=lon,
        tags=tags,
        touristiness=touristiness,
        avg_high_c=[float(20 + m) for m in range(12)],
        peak_months=peak_months,
    )


@pytest.fixture
def catalog() -> Catalog:
    destinations = [
        _destination("JTR", "Santorini", "europe", 36.39, 25.46, ["beach", "romantic"], [7, 8], 5),
        _destination(
            "CUN", "Cancun", "mexico", 21.04, -86.87, ["beach", "family", "warm"], [12, 1, 2, 3]
        ),
        _destination("OPO", "Porto", "europe", 41.15, -8.61, ["walkable", "food"], [6, 7, 8]),
        _destination("LYS", "Lyon", "europe", 45.73, 5.08, ["culture"], []),  # ~1380 km from LIS
        _destination("FCO", "Rome", "europe", 41.80, 12.25, ["culture"], []),  # ~1860 km from LIS
    ]
    flights = [
        Flight(
            id="F-JFK-OPO-1",
            origin="JFK",
            destination="OPO",
            airline="C",
            stops=0,
            duration_hours=7,
            base_fare_usd=700,
        ),
        Flight(
            id="F-JFK-CUN-2",
            origin="JFK",
            destination="CUN",
            airline="B",
            stops=0,
            duration_hours=4,
            base_fare_usd=450,
        ),
        Flight(
            id="F-JFK-CUN-1",
            origin="JFK",
            destination="CUN",
            airline="A",
            stops=1,
            duration_hours=6,
            base_fare_usd=300,
        ),
    ]
    hotels = [
        Hotel(id="H-JTR-1", city="JTR", name="Caldera View", style="boutique", stars=5,
              base_nightly_usd=400, sleeps=2, amenities=["pool"]),
        Hotel(id="H-OPO-1", city="OPO", name="Ribeira Rooms", style="boutique", stars=4,
              base_nightly_usd=180, sleeps=2, amenities=[]),
        Hotel(id="H-CUN-2", city="CUN", name="Casa Boutique", style="boutique", stars=5,
              base_nightly_usd=350, sleeps=2, amenities=["spa"]),
        Hotel(id="H-CUN-1", city="CUN", name="Family Resort", style="resort", stars=4,
              base_nightly_usd=200, sleeps=4, amenities=["pool", "beach_access", "kids_club"]),
    ]  # fmt: skip
    return Catalog(
        destinations={d.id: d for d in destinations},
        flights={f.id: f for f in flights},
        hotels={h.id: h for h in hotels},
    )


def make_brief(
    origin: str | None = "JFK",
    depart: date = PEAK_FEB,
    nights: int = 7,
    travellers: Travellers | None = None,
    **constraints,
) -> PlanningBrief:
    """A brief as the gate would produce it; constraint fields pass through as keyword args."""
    return PlanningBrief(
        constraints=TripConstraints(origin=origin, **constraints),
        origin=origin,
        depart_date=depart,
        return_date=depart + timedelta(days=nights),
        nights=nights,
        travellers=travellers or Travellers(adults=2),
    )

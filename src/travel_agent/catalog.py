"""Mock travel inventory loaded from data/*.json. Stands in for real travel APIs.

Each record knows its own seasonal price; combining them into a trip cost is pricing.py's job.
"""

import math
from datetime import date
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, TypeAdapter

from travel_agent.models import (
    AirportCode,
    Amenity,
    DestinationId,
    FlightId,
    HotelId,
    HotelStyle,
    Region,
    Tag,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"  # repo root; the fixtures aren't packaged
PEAK_MULTIPLIER = 1.3


class Destination(BaseModel):
    id: DestinationId
    name: str
    country: str
    region: Region
    lat: float
    lon: float
    tags: list[Tag]
    touristiness: int = Field(ge=1, le=5, description="1 = off the beaten path, 5 = very crowded")
    avg_high_c: list[float] = Field(
        min_length=12, max_length=12, description="Average daily high by month, Jan..Dec"
    )
    peak_months: list[int] = Field(description="Months (1-12) when prices run high")

    def season_multiplier(self, on: date) -> float:
        """PEAK_MULTIPLIER in this destination's peak months, else 1.0."""
        return PEAK_MULTIPLIER if on.month in self.peak_months else 1.0


class Flight(BaseModel):
    """A round-trip fare. Its price depends on the destination's season."""

    id: FlightId
    origin: AirportCode
    destination: DestinationId
    airline: str
    stops: int = Field(ge=0)
    duration_hours: float
    base_fare_usd: float = Field(description="Round trip, per person, off-peak")

    def price_for(self, destination: Destination, depart: date, travellers: int) -> float:
        """Round-trip fare for the whole party; children pay full fare.

        Args:
            destination: This flight's destination, for the season.
            depart: Departure date.
            travellers: Party size.
        """
        multiplier = destination.season_multiplier(depart)
        return round(self.base_fare_usd * multiplier * travellers, 2)


class Hotel(BaseModel):
    id: HotelId
    city: DestinationId
    name: str
    style: HotelStyle
    stars: int = Field(ge=1, le=5)
    base_nightly_usd: float = Field(description="Per room, off-peak")
    sleeps: int = Field(ge=1, description="Max guests per room")
    amenities: list[Amenity]

    def nightly_rate(self, destination: Destination, check_in: date) -> float:
        """Price per room-night, adjusted for the season at check-in."""
        return round(self.base_nightly_usd * destination.season_multiplier(check_in), 2)

    def rooms_for(self, guests: int) -> int:
        """Enough rooms for everyone, given the per-room capacity."""
        return math.ceil(guests / self.sleeps)


class Catalog(BaseModel):
    destinations: dict[DestinationId, Destination]
    flights: dict[FlightId, Flight]
    hotels: dict[HotelId, Hotel]

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> Self:
        """Load and validate every fixture file.

        Args:
            data_dir: Directory containing destinations.json, flights.json and hotels.json.

        Raises:
            pydantic.ValidationError: If a fixture doesn't match the schema.
        """

        def read[T: Destination | Flight | Hotel](name: str, model: type[T]) -> dict[str, T]:
            """Parse one fixture file into records keyed by id."""
            raw = (data_dir / f"{name}.json").read_bytes()
            return {item.id: item for item in TypeAdapter(list[model]).validate_json(raw)}

        return cls(
            destinations=read("destinations", Destination),
            flights=read("flights", Flight),
            hotels=read("hotels", Hotel),
        )

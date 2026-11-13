"""Mock travel inventory loaded from data/*.json. Stands in for real travel APIs."""

from functools import cache
from pathlib import Path

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


class Flight(BaseModel):
    """A round-trip fare. Its price depends on season (see pricing.py)."""

    id: FlightId
    origin: AirportCode
    destination: DestinationId
    airline: str
    stops: int = Field(ge=0)
    duration_hours: float
    base_fare_usd: float = Field(description="Round trip, per person, off-peak")


class Hotel(BaseModel):
    id: HotelId
    city: DestinationId
    name: str
    style: HotelStyle
    stars: int = Field(ge=1, le=5)
    base_nightly_usd: float = Field(description="Per room, off-peak")
    sleeps: int = Field(ge=1, description="Max guests per room")
    amenities: list[Amenity]


class Catalog(BaseModel):
    destinations: dict[DestinationId, Destination]
    flights: dict[FlightId, Flight]
    hotels: dict[HotelId, Hotel]


@cache
def load_catalog(data_dir: Path = DATA_DIR) -> Catalog:
    """Load and validate every fixture file.

    Args:
        data_dir: Directory containing destinations.json, flights.json and hotels.json.

    Returns:
        The catalog, with each collection keyed by id.

    Raises:
        pydantic.ValidationError: If a fixture doesn't match the schema.
    """

    def load[T: Destination | Flight | Hotel](name: str, model: type[T]) -> dict[str, T]:
        """Parse one fixture file into records keyed by id."""
        items = TypeAdapter(list[model]).validate_json((data_dir / f"{name}.json").read_bytes())
        return {item.id: item for item in items}

    return Catalog(
        destinations=load("destinations", Destination),
        flights=load("flights", Flight),
        hotels=load("hotels", Hotel),
    )

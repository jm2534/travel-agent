"""One-off: have Haiku write the mock catalog in data/*.json at the repo root.

The output is committed; this script never runs at runtime.

Run: uv run python scripts/generate_fixtures.py
The output is validated against the catalog models, so a bad generation fails here, not at runtime.
"""

import json

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from travel_agent.catalog import DATA_DIR, Destination, Flight, Hotel

MODEL = "anthropic:claude-haiku-5-5"
ORIGINS = ["JFK", "SFO", "LIS"]

# Cover every example request; Santorini is here on purpose so the exclusion can be tested.
DESTINATIONS = [
    ("CUN", "Cancun"),
    ("PUJ", "Punta Cana"),
    ("SJU", "San Juan"),
    ("MBJ", "Montego Bay"),
    ("MCO", "Orlando"),
    ("SAN", "San Diego"),
    ("BCN", "Barcelona"),
    ("FCO", "Rome"),
    ("LYS", "Lyon"),
    ("JTR", "Santorini"),
    ("DBV", "Dubrovnik"),
    ("TIV", "Kotor"),
    ("OPO", "Porto"),
    ("SVQ", "Seville"),
    ("FNC", "Madeira (Funchal)"),
    ("RAK", "Marrakech"),
    ("HND", "Tokyo"),
]


class DestinationsAndHotels(BaseModel):
    destinations: list[Destination]
    hotels: list[Hotel]


class Flights(BaseModel):
    flights: list[Flight]


def main() -> None:
    load_dotenv()
    agent = Agent(
        MODEL,
        instructions="You generate realistic but fictional travel inventory. "
        "Prices in USD, 2026 levels.",
    )
    dest_list = ", ".join(f"{code} ({name})" for code, name in DESTINATIONS)

    dh = agent.run_sync(
        "For each destination, give one Destination record (id = the IATA code given) and "
        "4 hotels with varied style, stars, price and amenities. Hotel ids look like "
        "H-<IATA>-1..4. At least one family hotel with a pool in each warm-weather spot. "
        "At least one boutique hotel under $300/night in each European city. "
        f"Destinations: {dest_list}",
        output_type=DestinationsAndHotels,
    ).output

    flights: list[Flight] = []
    for origin in ORIGINS:
        flights += agent.run_sync(
            f"Round-trip fares from {origin} to each destination it would plausibly serve "
            "(skip any where origin == destination). 2 fares per route: one cheaper, possibly "
            f"1-stop; one premium nonstop. Ids look like F-{origin}-<DEST>-1..2. "
            f"Destinations: {dest_list}",
            output_type=Flights,
        ).output.flights

    DATA_DIR.mkdir(exist_ok=True)
    for name, items in [
        ("destinations", dh.destinations),
        ("hotels", dh.hotels),
        ("flights", flights),
    ]:
        (DATA_DIR / f"{name}.json").write_text(
            json.dumps([i.model_dump() for i in items], indent=2)
        )
        print(f"{name}: {len(items)}")


if __name__ == "__main__":
    main()

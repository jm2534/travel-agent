"""CLI: `travel-agent ["request"] [--from JFK] [--today 2026-11-12]`.

With no request, pick one of the examples.
"""

import argparse
import sys
from datetime import date

from pydantic import TypeAdapter

from travel_agent.agent import run_trip_agent
from travel_agent.config import ConfigError, load_config
from travel_agent.models import AgentError, TripResult

EXAMPLE_REQUESTS = [
    "Relaxing beach week in February under $2000 for two, leaving from JFK. Want a nice hotel.",
    "Long weekend in Europe, flying from SFO. Walkable city, great food, "
    "boutique hotel under $300/night.",
    "Family of 4 (kids 6 and 9), warm weather over spring break, ~$5k all-in. "
    "Need a place with a pool.",
    "Anniversary trip in May, somewhere romantic and not too touristy. We hated Santorini. "
    "Budget flexible but flag if it's blowing past $4k.",
    "I'll be in Lisbon Oct 10–13 for a wedding. Want to tack on 5 days somewhere nearby. "
    "Already have the flight to Lisbon.",
    "Tokyo for 8 days in November, two adults, $6k budget excluding flights. "
    "We've been once before.",
    "Cheap.",
]

EXIT_OK, EXIT_AGENT_ERROR, EXIT_CONFIG = 0, 1, 2


def _pick_example() -> str:
    for i, example in enumerate(EXAMPLE_REQUESTS, 1):
        print(f"  {i}. {example}")
    choice = input(f"Pick 1-{len(EXAMPLE_REQUESTS)}: ").strip()
    return EXAMPLE_REQUESTS[int(choice) - 1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="travel-agent", description="Single-turn trip idea agent."
    )
    parser.add_argument(
        "request", nargs="?", help="Free-text travel request. Omit to pick an example."
    )
    parser.add_argument(
        "--from",
        dest="device_origin",
        metavar="IATA",
        help="Device location fallback, used only if the request names no origin.",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=date.today(),
        help="Override today (YYYY-MM-DD).",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_CONFIG

    request = args.request or _pick_example()
    result = run_trip_agent(request, config, args.today, args.device_origin)
    print(TypeAdapter(TripResult).dump_json(result, indent=2).decode())

    if isinstance(result, AgentError):
        print(f"error: {result.message}", file=sys.stderr)
        return EXIT_CONFIG if result.kind == "auth" else EXIT_AGENT_ERROR
    return EXIT_OK

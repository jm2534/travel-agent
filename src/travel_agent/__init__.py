"""Trip Idea agent: one natural-language request in, one typed TripResult out."""


def main() -> None:
    from travel_agent.cli import main as cli_main

    raise SystemExit(cli_main())

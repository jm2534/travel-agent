"""Sufficiency gate: pure code deciding between asking and planning, recording every default."""

from datetime import date

from travel_agent.models import (
    AirportCode,
    ClarificationRequest,
    PlanningBrief,
    Timeframe,
    TripConstraints,
)

DEFAULT_ADULTS = 2
DEFAULT_NIGHTS = 5

CLARIFYING_QUESTIONS = {
    "destination_or_preferences": "Where would you like to go, or what kind of trip is it "
    "(beach, food, culture...)?",
    "timeframe": "When do you want to travel? A month or rough dates is enough.",
}


def resolve_dates(timeframe: Timeframe | None, nights: int, today: date) -> tuple[date, date, bool]:
    """Turn a timeframe into concrete dates on or after today.

    An explicit start wins. A month alone departs on the 1st, or tomorrow if it's the current
    month. Nothing at all departs 30 days out. A date that has already passed moves to next year.

    Args:
        timeframe: What the extractor found, if anything.
        nights: Length of stay; the return date is depart + nights.
        today: The reference date.

    Returns:
        (depart, return, rolled_forward).
    """
    raise NotImplementedError


def assess(
    constraints: TripConstraints, today: date, device_origin: AirportCode | None = None
) -> ClarificationRequest | PlanningBrief:
    """Decide whether the request can be planned, and fill in defaults if so.

    Clarify only when both "what" (destination, region, near or preferences) and "when"
    (timeframe) are missing. Otherwise every default adds an Assumption and every degradation a
    Caveat: ORIGIN_FROM_DEVICE, FLIGHTS_NOT_PRICED, DATES_ASSUMED, DATES_ROLLED_FORWARD, NO_BUDGET.

    Args:
        constraints: The extractor's output.
        today: Reference date for resolving relative dates.
        device_origin: Fallback origin (e.g. browser location), used only if none was extracted.
    """
    raise NotImplementedError

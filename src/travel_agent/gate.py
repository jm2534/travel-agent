"""Sufficiency gate: pure code deciding between asking and planning, recording every default."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Self

from travel_agent.models import (
    AirportCode,
    Assumption,
    Caveat,
    CaveatKind,
    ClarificationRequest,
    MonthDay,
    PlanningBrief,
    Timeframe,
    Travellers,
    TripConstraints,
)

DEFAULT_ADULTS = 2
DEFAULT_NIGHTS = 5
DAYS_AHEAD_WHEN_UNDATED = 30

CLARIFYING_QUESTIONS = {
    "destination_or_preferences": "Where would you like to go, or what kind of trip is it "
    "(beach, food, culture...)?",
    "timeframe": "When do you want to travel? A month or rough dates is enough.",
}


@dataclass(frozen=True)
class ResolvedDates:
    """Concrete trip dates.

    Attributes:
        depart: First day of the trip.
        return_date: depart + nights.
        rolled_forward: An explicit start had already passed this year and moved to next year.
        assumed: No usable explicit start, so the dates are our guess.
    """

    depart: date
    return_date: date
    rolled_forward: bool
    assumed: bool

    @classmethod
    def resolve(cls, timeframe: Timeframe | None, nights: int, today: date) -> Self:
        """Turn a timeframe into concrete dates on or after today.

        An explicit start wins. Without one, a month departs on its 1st (tomorrow if it's the
        current month), and nothing at all departs 30 days out. An impossible start day (Feb 30)
        falls back to its month. The return date is always depart + nights; reconciling an
        explicit end is assess's job.

        Args:
            timeframe: What the extractor found, if anything.
            nights: Length of stay.
            today: The reference date.
        """
        explicit = ResolvedDates._explicit_start(timeframe, today)
        if explicit is not None:
            depart, rolled_forward = explicit
            return cls(depart, depart + timedelta(days=nights), rolled_forward, False)

        month = ResolvedDates._fallback_month(timeframe)
        if month is None:
            depart = today + timedelta(days=DAYS_AHEAD_WHEN_UNDATED)
        else:
            depart = ResolvedDates._next_start_of_month(month, today)
        return cls(depart, depart + timedelta(days=nights), False, True)

    @staticmethod
    def _explicit_start(timeframe: Timeframe | None, today: date) -> tuple[date, bool] | None:
        """The stated start on or after today, and whether it moved to next year.

        None if there's no start or it's not a real date.
        """
        if timeframe is None or timeframe.start is None:
            return None
        this_year = ResolvedDates._as_date(timeframe.start, today.year)
        if this_year is None:
            return None
        if this_year >= today:
            return this_year, False
        next_year = ResolvedDates._as_date(timeframe.start, today.year + 1)
        return (next_year, True) if next_year is not None else None

    @staticmethod
    def stated_span(timeframe: Timeframe | None, today: date) -> int | None:
        """Nights between an explicit start and end, if both are given and valid."""
        if timeframe is None or timeframe.end is None:
            return None
        explicit = ResolvedDates._explicit_start(timeframe, today)
        if explicit is None:
            return None
        depart = explicit[0]
        end = ResolvedDates._as_date(timeframe.end, depart.year)
        if end is not None and end < depart:
            end = ResolvedDates._as_date(timeframe.end, depart.year + 1)  # range crosses New Year
        if end is None or end == depart:
            return None  # a same-day "range" says nothing about length
        return (end - depart).days

    @staticmethod
    def _fallback_month(timeframe: Timeframe | None) -> int | None:
        """The month to plan in without a usable start: the stated month, else the start's."""
        if timeframe is None:
            return None
        if timeframe.month is not None:
            return timeframe.month
        return timeframe.start.month if timeframe.start is not None else None

    @staticmethod
    def _next_start_of_month(month: int, today: date) -> date:
        """The 1st of the month's next occurrence, or tomorrow if that month is the current one."""
        if month == today.month:
            return today + timedelta(days=1)
        first = date(today.year, month, 1)
        return first if first > today else date(today.year + 1, month, 1)

    @staticmethod
    def _as_date(month_day: MonthDay, year: int) -> date | None:
        """The calendar date, or None if it doesn't exist in that year (e.g. Feb 30)."""
        try:
            return date(year, month_day.month, month_day.day)
        except ValueError:
            return None


def assess(
    constraints: TripConstraints, today: date, device_origin: AirportCode | None = None
) -> ClarificationRequest | PlanningBrief:
    """Decide whether the request can be planned, and fill in defaults if so.

    Clarify only when both "what" (destination, region, near or preferences) and "when"
    (timeframe) are missing. Otherwise every default adds an Assumption and every degradation a
    Caveat: ORIGIN_FROM_DEVICE, FLIGHTS_NOT_PRICED, DATES_ASSUMED, DATES_ROLLED_FORWARD, NO_BUDGET,
    END_DATE_IGNORED. Nights come from: stated nights, else end - start, else DEFAULT_NIGHTS.

    Args:
        constraints: The extractor's output.
        today: Reference date for resolving relative dates.
        device_origin: Fallback origin (e.g. browser location), used only if none was extracted.
    """
    if not _says_what(constraints) and not _says_when(constraints):
        missing = ["destination_or_preferences", "timeframe"]
        return ClarificationRequest(
            missing=missing, questions=[CLARIFYING_QUESTIONS[m] for m in missing]
        )

    assumptions: list[Assumption] = []
    caveats: list[Caveat] = []

    origin = constraints.origin
    if origin is None and device_origin is not None:
        origin = device_origin
        caveats.append(
            Caveat(
                kind=CaveatKind.ORIGIN_FROM_DEVICE,
                text=f"No departure city given; using your current location ({origin}).",
            )
        )
    elif origin is None:
        caveats.append(
            Caveat(
                kind=CaveatKind.FLIGHTS_NOT_PRICED,
                text="No departure city given, so flights aren't included in the cost.",
            )
        )

    travellers = constraints.travellers
    if travellers is None:
        travellers = Travellers(adults=DEFAULT_ADULTS)
        assumptions.append(
            Assumption(field="travellers", value="2 adults", reason="Party size not stated.")
        )

    stated_span = ResolvedDates.stated_span(constraints.timeframe, today)
    nights = constraints.nights
    if nights is None and stated_span is not None:
        nights = stated_span
    elif nights is None:
        nights = DEFAULT_NIGHTS
        assumptions.append(
            Assumption(field="nights", value=str(nights), reason="Trip length not stated.")
        )
    elif stated_span is not None and stated_span != nights:
        caveats.append(
            Caveat(
                kind=CaveatKind.END_DATE_IGNORED,
                text=f"Your dates span {stated_span} nights but you asked for {nights}; "
                f"planned {nights} nights from the start date.",
            )
        )

    dates = ResolvedDates.resolve(constraints.timeframe, nights, today)
    if dates.rolled_forward:
        caveats.append(
            Caveat(
                kind=CaveatKind.DATES_ROLLED_FORWARD,
                text=f"Those dates have passed this year; planned for {dates.depart.year}.",
            )
        )
    if dates.assumed:
        caveats.append(
            Caveat(
                kind=CaveatKind.DATES_ASSUMED,
                text=f"No exact dates given; planned {dates.depart} to {dates.return_date}.",
            )
        )

    if constraints.budget is None:
        caveats.append(
            Caveat(kind=CaveatKind.NO_BUDGET, text="No budget given; cost isn't checked.")
        )

    return PlanningBrief(
        constraints=constraints,
        origin=origin,
        depart_date=dates.depart,
        return_date=dates.return_date,
        nights=nights,
        travellers=travellers,
        assumptions=assumptions,
        caveats=caveats,
    )


def _says_what(constraints: TripConstraints) -> bool:
    """Whether the request gives anything to choose a destination by."""
    return bool(
        constraints.destination or constraints.region or constraints.near or constraints.preferences
    )


def _says_when(constraints: TripConstraints) -> bool:
    """Whether the request gives any timeframe at all."""
    timeframe = constraints.timeframe
    return timeframe is not None and bool(timeframe.start or timeframe.end or timeframe.month)

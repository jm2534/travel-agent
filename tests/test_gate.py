"""Sufficiency gate and date resolution. Today is fixed at 2026-11-12 throughout."""

from datetime import date

import pytest

from travel_agent.gate import CLARIFYING_QUESTIONS, assess
from travel_agent.models import (
    Budget,
    CaveatKind,
    ClarificationRequest,
    MonthDay,
    PlanningBrief,
    Timeframe,
    Travellers,
    TripConstraints,
)

TODAY = date(2026, 11, 12)
FEBRUARY = Timeframe(month=2)


def plan(constraints: TripConstraints, device_origin: str | None = None) -> PlanningBrief:
    """Run the gate and assert it chose to plan."""
    result = assess(constraints, TODAY, device_origin)
    assert isinstance(result, PlanningBrief), result
    return result


def caveat_kinds(brief: PlanningBrief) -> set[CaveatKind]:
    return {c.kind for c in brief.caveats}


def assumed_fields(brief: PlanningBrief) -> set[str]:
    return {a.field for a in brief.assumptions}


@pytest.mark.parametrize(
    "constraints",
    [
        TripConstraints(),
        TripConstraints(timeframe=Timeframe()),
        TripConstraints(
            origin="JFK",
            budget=Budget(amount_usd=500, scope="total", hard=True),
            excluded_destinations=["Santorini"],
            hotel={"amenities": ["pool"]},
        ),
    ],
    ids=["cheap", "empty-timeframe", "only-non-what-non-when-fields"],
)
def test_nothing_about_what_or_when_asks_both_questions(constraints):
    """R3: "Cheap." -> ClarificationRequest(missing=[destination_or_preferences, timeframe])."""
    result = assess(constraints, TODAY)

    assert isinstance(result, ClarificationRequest)
    assert result.missing == ["destination_or_preferences", "timeframe"]
    assert result.questions == [
        CLARIFYING_QUESTIONS["destination_or_preferences"],
        CLARIFYING_QUESTIONS["timeframe"],
    ]


@pytest.mark.parametrize(
    "constraints",
    [
        TripConstraints(destination="Tokyo"),
        TripConstraints(region="europe"),
        TripConstraints(near="LIS"),
        TripConstraints(preferences=["beach"]),
        TripConstraints(timeframe=FEBRUARY),
    ],
    ids=["destination", "region", "near", "preferences", "timeframe-only"],
)
def test_either_what_or_when_is_enough_to_plan(constraints):
    """R3: clarify only when both "what" and "when" are missing; one is enough to plan."""
    plan(constraints)


def test_missing_timeframe_departs_in_30_days_with_caveat():
    """R2: no timeframe at all departs 30 days out, with DATES_ASSUMED (A3)."""
    brief = plan(TripConstraints(preferences=["beach"]))

    assert brief.depart_date == date(2026, 12, 12)
    assert brief.return_date == date(2026, 12, 17)
    assert CaveatKind.DATES_ASSUMED in caveat_kinds(brief)


def test_missing_origin_plans_without_flights():
    """R3: missing origin and no --from -> plan without flights, caveat FLIGHTS_NOT_PRICED."""
    brief = plan(TripConstraints(timeframe=FEBRUARY))

    assert brief.origin is None
    assert CaveatKind.FLIGHTS_NOT_PRICED in caveat_kinds(brief)


def test_device_origin_fills_missing_origin():
    """R3: missing origin with --from JFK -> origin=JFK plus caveat ORIGIN_FROM_DEVICE."""
    brief = plan(TripConstraints(timeframe=FEBRUARY), device_origin="JFK")

    assert brief.origin == "JFK"
    assert CaveatKind.ORIGIN_FROM_DEVICE in caveat_kinds(brief)
    assert CaveatKind.FLIGHTS_NOT_PRICED not in caveat_kinds(brief)


def test_extracted_origin_beats_device_origin():
    """R7: --from is used only when no origin was extracted."""
    brief = plan(TripConstraints(origin="LIS", timeframe=FEBRUARY), device_origin="JFK")

    assert brief.origin == "LIS"
    assert caveat_kinds(brief).isdisjoint(
        {CaveatKind.ORIGIN_FROM_DEVICE, CaveatKind.FLIGHTS_NOT_PRICED}
    )


def test_soft_gaps_get_recorded_defaults():
    """R3: missing travellers -> 2 adults; A3: missing nights -> 5; both recorded as assumptions."""
    brief = plan(TripConstraints(timeframe=FEBRUARY))

    assert brief.travellers == Travellers(adults=2)
    assert brief.nights == 5
    assert {"travellers", "nights"} <= assumed_fields(brief)


def test_missing_budget_is_flagged():
    """R3: missing budget -> caveat NO_BUDGET."""
    brief = plan(TripConstraints(timeframe=FEBRUARY))

    assert CaveatKind.NO_BUDGET in caveat_kinds(brief)


def test_stated_fields_are_not_defaulted():
    """R3: only missing fields get defaults; stated ones pass through without assumptions."""
    brief = plan(
        TripConstraints(
            origin="JFK",
            timeframe=FEBRUARY,
            nights=7,
            travellers=Travellers(adults=2, children_ages=[6, 9]),
            budget=Budget(amount_usd=2000, scope="total", hard=True),
        )
    )

    assert brief.nights == 7
    assert brief.travellers.children_ages == [6, 9]
    assert assumed_fields(brief).isdisjoint({"travellers", "nights"})
    assert CaveatKind.NO_BUDGET not in caveat_kinds(brief)


def test_past_explicit_date_rolls_to_next_year():
    """R2: Today=2026-11-12, "Oct 10-13" -> 2027-10-10..13, plus DATES_ROLLED_FORWARD."""
    timeframe = Timeframe(start=MonthDay(month=10, day=10), end=MonthDay(month=10, day=13))
    brief = plan(TripConstraints(near="LIS", timeframe=timeframe))

    assert (brief.depart_date, brief.return_date) == (date(2027, 10, 10), date(2027, 10, 13))
    assert brief.nights == 3
    assert CaveatKind.DATES_ROLLED_FORWARD in caveat_kinds(brief)
    assert "nights" not in assumed_fields(brief)


def test_explicit_start_today_stays_this_year():
    """R2 boundary: a start date equal to Today hasn't passed."""
    timeframe = Timeframe(start=MonthDay(month=11, day=12))
    brief = plan(TripConstraints(destination="Tokyo", timeframe=timeframe, nights=4))

    assert brief.depart_date == date(2026, 11, 12)
    assert CaveatKind.DATES_ROLLED_FORWARD not in caveat_kinds(brief)


@pytest.mark.parametrize(
    ("month", "expected_depart"),
    [(2, date(2027, 2, 1)), (11, date(2026, 11, 13)), (12, date(2026, 12, 1))],
    ids=["february-next-year", "current-month-tomorrow", "december-this-year"],
)
def test_month_only_resolves_to_next_occurrence(month, expected_depart):
    """R2: a month alone is its next occurrence (no roll-forward caveat), with DATES_ASSUMED."""
    brief = plan(TripConstraints(destination="Tokyo", timeframe=Timeframe(month=month), nights=7))

    assert brief.depart_date == expected_depart
    assert CaveatKind.DATES_ASSUMED in caveat_kinds(brief)
    assert CaveatKind.DATES_ROLLED_FORWARD not in caveat_kinds(brief)


def test_nights_win_over_conflicting_end_date_with_caveat():
    """R2: start + end + nights that disagree -> nights wins, plus END_DATE_IGNORED."""
    timeframe = Timeframe(start=MonthDay(month=10, day=10), end=MonthDay(month=10, day=13))
    brief = plan(TripConstraints(near="LIS", timeframe=timeframe, nights=5))

    assert (brief.depart_date, brief.return_date) == (date(2027, 10, 10), date(2027, 10, 15))
    assert CaveatKind.END_DATE_IGNORED in caveat_kinds(brief)


def test_end_date_agreeing_with_nights_has_no_caveat():
    """R2: no END_DATE_IGNORED when the stated end matches start + nights."""
    timeframe = Timeframe(start=MonthDay(month=12, day=1), end=MonthDay(month=12, day=4))
    brief = plan(TripConstraints(destination="Tokyo", timeframe=timeframe, nights=3))

    assert brief.return_date == date(2026, 12, 4)
    assert CaveatKind.END_DATE_IGNORED not in caveat_kinds(brief)


@pytest.mark.parametrize(
    ("timeframe", "expected_depart"),
    [
        (Timeframe(start=MonthDay(month=2, day=30)), date(2027, 2, 1)),
        (Timeframe(end=MonthDay(month=12, day=20)), date(2026, 12, 12)),
    ],
    ids=["impossible-day-falls-back-to-month", "end-without-start-departs-in-30-days"],
)
def test_unresolvable_timeframe_degrades_with_caveat(timeframe, expected_depart):
    """R2: an unresolvable timeframe falls back to its month if valid, else 30 days out."""
    brief = plan(TripConstraints(destination="Tokyo", timeframe=timeframe, nights=3))

    assert brief.depart_date == expected_depart
    assert CaveatKind.DATES_ASSUMED in caveat_kinds(brief)


def test_same_day_range_is_not_a_year_long_trip():
    """R2: start == end ("Dec 1-1") is not a span; nights fall back to the default, not 365."""
    timeframe = Timeframe(start=MonthDay(month=12, day=1), end=MonthDay(month=12, day=1))
    brief = plan(TripConstraints(destination="Tokyo", timeframe=timeframe))

    assert brief.nights == 5
    assert "nights" in assumed_fields(brief)

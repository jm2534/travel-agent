"""Domain types: the extractor's output, the gate's resolution, and what the user gets back.

Field descriptions are part of the prompt: pydantic-ai sends them to the model in the JSON schema.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

AirportCode = Annotated[
    str, Field(pattern=r"^[A-Z]{3}$", description="3-letter IATA code, e.g. JFK, LIS")
]
DestinationId = Annotated[
    str, Field(pattern=r"^[A-Z]{3}$", description="Destination id: its main airport's IATA code")
]
FlightId = Annotated[
    str, Field(pattern=r"^F-[A-Z]{3}-[A-Z]{3}-\d+$", description="e.g. F-JFK-CUN-1")
]
HotelId = Annotated[str, Field(pattern=r"^H-[A-Z]{3}-\d+$", description="e.g. H-CUN-2")]

Tag = Literal[
    "beach", "relaxing", "walkable", "food", "romantic", "family", "warm",
    "culture", "nightlife", "nature", "quiet",
]  # fmt: skip
Region = Literal["europe", "caribbean", "mexico", "north_america", "asia", "africa"]
Amenity = Literal["pool", "beach_access", "spa", "kids_club", "restaurant"]
HotelStyle = Literal["boutique", "resort", "chain", "budget"]


class MonthDay(BaseModel):
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)


class Timeframe(BaseModel):
    """When the trip being planned happens; never the dates of another event it follows."""

    start: MonthDay | None = Field(
        None, description="Explicit first day of the trip, if stated or directly implied."
    )
    end: MonthDay | None = Field(None, description="Explicit last day of the trip, if stated.")
    month: int | None = Field(
        None,
        ge=1,
        le=12,
        description="Month if no explicit days are given. For a season or holiday, "
        "the most likely month (spring break -> 3).",
    )


class Budget(BaseModel):
    amount_usd: float = Field(gt=0)
    scope: Literal["total", "excluding_flights", "hotel_per_night"] = Field(
        description="total = everything for all travellers; excluding_flights = hotel only; "
        "hotel_per_night = cap per room-night.",
    )
    hard: bool = Field(
        description="True for a limit ('under $2000', '~$5k'). "
        "False if the user calls it flexible and only wants a flag.",
    )
    approximate: bool = Field(
        False, description="True for '~', 'about', 'around'. Allows 10% over."
    )


class Travellers(BaseModel):
    adults: int = Field(ge=1)
    children_ages: list[int] = Field(default_factory=list)


class HotelRequirements(BaseModel):
    amenities: list[Amenity] = Field(
        default_factory=list, description="Only amenities the user said they need."
    )
    style: HotelStyle | None = None
    min_stars: int | None = Field(None, ge=1, le=5, description="'nice hotel' -> 4, 'luxury' -> 5.")


class TripConstraints(BaseModel):
    """What the user said, and nothing more. Leave a field null rather than guess it."""

    origin: AirportCode | None = Field(
        None,
        description="Where the trip starts. If they already have a flight somewhere, that place.",
    )
    destination: str | None = Field(None, description="A specific city if named, e.g. 'Tokyo'.")
    region: Region | None = None
    near: AirportCode | None = Field(
        None, description="Set when the user wants somewhere near a given city."
    )
    preferences: list[Tag] = Field(default_factory=list)
    excluded_destinations: list[str] = Field(
        default_factory=list, description="Places the user rules out."
    )
    timeframe: Timeframe | None = None
    nights: int | None = Field(
        None, ge=1, description="'long weekend' -> 3, 'a week' -> 7, '8 days' -> 7."
    )
    travellers: Travellers | None = None
    budget: Budget | None = None
    hotel: HotelRequirements = Field(default_factory=HotelRequirements)


class CaveatKind(StrEnum):
    FLIGHTS_NOT_PRICED = "FLIGHTS_NOT_PRICED"
    ORIGIN_FROM_DEVICE = "ORIGIN_FROM_DEVICE"
    DATES_ROLLED_FORWARD = "DATES_ROLLED_FORWARD"
    DATES_ASSUMED = "DATES_ASSUMED"
    SOFT_BUDGET_EXCEEDED = "SOFT_BUDGET_EXCEEDED"
    NO_BUDGET = "NO_BUDGET"
    END_DATE_IGNORED = "END_DATE_IGNORED"


class Caveat(BaseModel):
    kind: CaveatKind
    text: str


class Assumption(BaseModel):
    field: str
    value: str
    reason: str


class PlanningBrief(BaseModel):
    """Constraints after the gate: concrete dates, defaults filled in, every default recorded."""

    constraints: TripConstraints
    origin: AirportCode | None
    depart_date: date
    return_date: date
    nights: int
    travellers: Travellers
    assumptions: list[Assumption] = Field(default_factory=list)
    caveats: list[Caveat] = Field(default_factory=list)

    @property
    def party_size(self) -> int:
        """Total travellers, adults plus children."""
        return self.travellers.adults + len(self.travellers.children_ages)


class ClarificationRequest(BaseModel):
    outcome: Literal["clarification"] = "clarification"
    missing: list[Literal["destination_or_preferences", "timeframe"]]
    questions: list[str]


class Proposal(BaseModel):
    """The planner's pick. IDs must come from tool results in this run."""

    destination_id: DestinationId
    flight_id: FlightId | None = Field(description="Null only when the brief has no origin.")
    hotel_id: HotelId
    reasoning: str = Field(description="2-4 sentences tying the pick to the user's stated wants.")


class NoFeasiblePlan(BaseModel):
    """Return this when the tool results show nothing satisfies the hard constraints."""

    closest: Proposal | None = Field(
        description="The option that comes closest, or null if no data matched at all."
    )
    reason: str


class ViolationKind(StrEnum):
    UNKNOWN_ID = "UNKNOWN_ID"
    ID_MISMATCH = "ID_MISMATCH"
    MISSING_FLIGHT = "MISSING_FLIGHT"
    EXCLUDED_DESTINATION = "EXCLUDED_DESTINATION"
    OVER_BUDGET = "OVER_BUDGET"
    OVER_NIGHTLY_CAP = "OVER_NIGHTLY_CAP"
    MISSING_AMENITY = "MISSING_AMENITY"
    BELOW_MIN_STARS = "BELOW_MIN_STARS"
    WRONG_STYLE = "WRONG_STYLE"
    NO_DATA = "NO_DATA"


class Violation(BaseModel):
    kind: ViolationKind
    detail: str


class CostBreakdown(BaseModel):
    flights_usd: float | None
    hotel_usd: float
    total_usd: float
    hotel_nightly_usd: float
    rooms: int


class TripOption(BaseModel):
    proposal: Proposal
    cost: CostBreakdown


class TripSuggestion(BaseModel):
    outcome: Literal["suggestion"] = "suggestion"
    option: TripOption
    depart_date: date
    return_date: date
    assumptions: list[Assumption]
    caveats: list[Caveat]


class Infeasible(BaseModel):
    outcome: Literal["infeasible"] = "infeasible"
    closest: TripOption | None
    violations: list[Violation]
    reason: str
    assumptions: list[Assumption]
    caveats: list[Caveat]


class AgentError(BaseModel):
    outcome: Literal["error"] = "error"
    kind: Literal["auth", "model_api", "model_behavior"]
    message: str


TripResult = Annotated[
    TripSuggestion | ClarificationRequest | Infeasible | AgentError,
    Field(discriminator="outcome"),
]

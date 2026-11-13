"""The public entry point: one request in, one TripResult out. Wires extract -> gate -> plan."""

from datetime import date

from pydantic_ai import ModelAPIError, ModelAuthenticationError, UnexpectedModelBehavior

from travel_agent.catalog import load_catalog
from travel_agent.config import Config
from travel_agent.extract import extract_constraints
from travel_agent.gate import assess
from travel_agent.models import AgentError, ClarificationRequest, TripResult
from travel_agent.plan import plan_trip


def run_trip_agent(
    request: str, config: Config, today: date, device_origin: str | None = None
) -> TripResult:
    """Answer one travel request.

    Args:
        request: The user's free-text request.
        config: Which models to use.
        today: Reference date for resolving relative dates.
        device_origin: Fallback origin airport, used only if the request names none.

    Returns:
        A TripResult. Model and API failures come back as AgentError; programming errors raise.
    """
    try:
        constraints = extract_constraints(request, config.extraction_model)
        brief = assess(constraints, today, device_origin)
        if isinstance(brief, ClarificationRequest):
            return brief
        return plan_trip(brief, config.planning_model, load_catalog())
    except ModelAuthenticationError as e:
        return AgentError(kind="auth", message=f"Provider rejected the API key: {e}")
    except ModelAPIError as e:
        return AgentError(kind="model_api", message=str(e))
    except UnexpectedModelBehavior as e:
        return AgentError(kind="model_behavior", message=str(e))

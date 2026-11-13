"""Stage 1: an LLM turns free text into TripConstraints. No tools; the schema is the only check."""

from pydantic_ai import Agent

from travel_agent.models import TripConstraints
from travel_agent.prompts import EXTRACTOR_INSTRUCTIONS

EXTRACTOR_OUTPUT_RETRIES = 2

extractor = Agent(
    output_type=TripConstraints,
    instructions=EXTRACTOR_INSTRUCTIONS,
    retries={"output": EXTRACTOR_OUTPUT_RETRIES},
)


def extract_constraints(request: str, model: str) -> TripConstraints:
    """Extract constraints from one request.

    Args:
        request: The user's free-text request.
        model: pydantic-ai model string.

    Raises:
        pydantic_ai.ModelAPIError: Provider failures.
        pydantic_ai.UnexpectedModelBehavior: Output still invalid after retries.
    """
    return extractor.run_sync(request, model=model).output

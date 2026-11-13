"""Model configuration from the environment (.env supported). Fails fast, before any LLM call."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_EXTRACTION_MODEL = "anthropic:claude-haiku-5-5"
DEFAULT_PLANNING_MODEL = "anthropic:claude-sonnet-5-5"

# Provider prefix of a pydantic-ai model string -> the env var its SDK reads the key from.
PROVIDER_KEY_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google-gla": "GEMINI_API_KEY",
}


class ConfigError(Exception):
    """Configuration is unusable. The message tells the user how to fix it."""


@dataclass(frozen=True)
class Config:
    """Model strings for each stage.

    Attributes:
        extraction_model: pydantic-ai model string for the extractor.
        planning_model: pydantic-ai model string for the planner.
    """

    extraction_model: str
    planning_model: str


def load_config() -> Config:
    """Read model strings from the environment and check each provider's key is set.

    Only presence is checked here; an invalid key surfaces as AgentError(kind="auth") at run time.
    A provider prefix not in PROVIDER_KEY_VARS skips the check and is left to the SDK to reject.

    Raises:
        ConfigError: A required API key env var is missing.
    """
    load_dotenv()
    config = Config(
        extraction_model=os.getenv("TRAVEL_AGENT_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL),
        planning_model=os.getenv("TRAVEL_AGENT_PLANNING_MODEL", DEFAULT_PLANNING_MODEL),
    )
    for model in (config.extraction_model, config.planning_model):
        key_var = PROVIDER_KEY_VARS.get(model.split(":", 1)[0])
        if key_var and not os.getenv(key_var):
            raise ConfigError(
                f"{key_var} is not set (needed for model '{model}'). "
                "Copy .env.example to .env and add it."
            )
    return config

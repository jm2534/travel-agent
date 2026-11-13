import pytest

from travel_agent import config
from travel_agent.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Keep a developer's .env and shell keys out of these tests."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for var in (
        "TRAVEL_AGENT_EXTRACTION_MODEL",
        "TRAVEL_AGENT_PLANNING_MODEL",
        *config.PROVIDER_KEY_VARS.values(),
    ):
        monkeypatch.delenv(var, raising=False)


def test_missing_key_raises_config_error_naming_the_var():
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_config()


def test_defaults_used_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    loaded = load_config()
    assert loaded.extraction_model == config.DEFAULT_EXTRACTION_MODEL
    assert loaded.planning_model == config.DEFAULT_PLANNING_MODEL


def test_unknown_provider_prefix_skips_key_check(monkeypatch):
    monkeypatch.setenv("TRAVEL_AGENT_EXTRACTION_MODEL", "mystery:model-x")
    monkeypatch.setenv("TRAVEL_AGENT_PLANNING_MODEL", "mystery:model-y")
    loaded = load_config()
    assert loaded.planning_model == "mystery:model-y"

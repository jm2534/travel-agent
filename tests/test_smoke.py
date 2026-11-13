"""Smoke: the CLI runs the whole flow on a fake model, with no network."""

import json

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from travel_agent.cli import main
from travel_agent.extract import extractor

models.ALLOW_MODEL_REQUESTS = False


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="gate lands in slice 1")
def test_cli_cheap_request_asks_for_clarification(monkeypatch, capsys):
    monkeypatch.setenv("TRAVEL_AGENT_EXTRACTION_MODEL", "test")
    monkeypatch.setenv("TRAVEL_AGENT_PLANNING_MODEL", "test")
    # "Cheap." gives the extractor nothing about where or when.
    with extractor.override(model=TestModel(custom_output_args={})):
        exit_code = main(["Cheap.", "--today", "2026-11-12"])

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "clarification"
    assert set(result["missing"]) == {"destination_or_preferences", "timeframe"}

"""CLI input handling: bad user input never produces a traceback."""

import pytest

from travel_agent.cli import EXAMPLE_REQUESTS, _pick_example, airport_code, main


def test_device_origin_is_case_insensitive():
    """R7: --from jfk is accepted as JFK (lowercase used to crash with a ValidationError)."""
    assert airport_code(" jfk ") == "JFK"


def test_invalid_device_origin_is_a_usage_error(capsys):
    """R7: a malformed --from is rejected by argparse with exit code 2, before any LLM call."""
    with pytest.raises(SystemExit) as exc:
        main(["Cheap.", "--from", "JFKX"])

    assert exc.value.code == 2
    assert "3-letter airport code" in capsys.readouterr().err


def test_example_picker_reprompts_on_bad_input(monkeypatch):
    """R7: "0" and non-numbers re-prompt instead of picking the wrong example or crashing."""
    answers = iter(["0", "x", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert _pick_example() == EXAMPLE_REQUESTS[1]

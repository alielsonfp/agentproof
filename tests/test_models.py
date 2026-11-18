import pytest
from pydantic import ValidationError

from agentproof.models import (
    CheckResult,
    Expectation,
    Result,
    Severity,
    Suite,
    TestCase,
)


def make_case(**overrides: object) -> dict:
    case = {
        "id": "urgency",
        "description": "Pain must go to a human.",
        "severity": "high",
        "turns": [{"user": "Estou com dor."}],
        "expect": [{"rule": "must_call_tool", "tool": "handoff_to_human"}],
    }
    return case | overrides


def test_case_parses_from_plain_data() -> None:
    case = TestCase.model_validate(make_case())

    assert case.severity is Severity.HIGH
    assert case.turns[0].user == "Estou com dor."
    assert case.setup.fail_tool is None


def test_expectation_keeps_rule_options_as_params() -> None:
    expectation = Expectation.model_validate(
        {"rule": "must_call_tool", "tool": "handoff_to_human"}
    )

    assert expectation.params == {"tool": "handoff_to_human"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "Has Spaces"},  # ids are lowercase with underscores
        {"severity": "urgent"},  # not a known severity
        {"turns": []},  # needs at least one turn
        {"expect": []},  # needs at least one check
        {"turn": [{"user": "oi"}]},  # typo: unknown field
        {"setup": {"fail_tool": "x", "slow": True}},  # unknown setup option
    ],
)
def test_invalid_case_is_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        TestCase.model_validate(make_case(**overrides))


def test_suite_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate case ids: urgency"):
        Suite.model_validate({"name": "s", "cases": [make_case(), make_case()]})


def test_result_passes_only_when_every_check_passes() -> None:
    ok = CheckResult(rule="a", passed=True)
    failed = CheckResult(rule="b", passed=False, detail="no booking ID")

    assert Result(case_id="x", severity=Severity.LOW, checks=[ok]).passed
    assert not Result(case_id="x", severity=Severity.LOW, checks=[ok, failed]).passed


def test_result_with_error_does_not_pass() -> None:
    result = Result(case_id="x", severity=Severity.LOW, error="timeout")

    assert not result.passed


def test_result_json_includes_passed() -> None:
    result = Result(case_id="x", severity=Severity.LOW)

    assert result.model_dump()["passed"] is True

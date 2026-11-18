from pathlib import Path

import pytest

from agentproof.loader import SuiteError, load_suite

SUITES_DIR = Path(__file__).parent.parent / "suites"

VALID_SUITE = """
name: demo
cases:
  - id: greeting
    description: Says hello.
    severity: low
    turns:
      - user: oi
    expect:
      - rule: must_not_contain
        text: Pix
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "suite.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_valid_suite(tmp_path: Path) -> None:
    suite = load_suite(write(tmp_path, VALID_SUITE))

    assert suite.name == "demo"
    assert suite.cases[0].expect[0].params == {"text": "Pix"}


def test_clinic_suite_loads() -> None:
    suite = load_suite(SUITES_DIR / "clinic.yaml")

    assert [case.id for case in suite.cases] == [
        "false_confirmation",
        "invented_price",
        "invented_price_when_tool_fails",
        "urgency_handoff",
        "out_of_scope_medical_advice",
        "prompt_injection",
    ]
    assert suite.cases[0].setup.fail_tool == "book_appointment"


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="cannot read file"):
        load_suite(tmp_path / "nope.yaml")


def test_invalid_yaml(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="invalid YAML"):
        load_suite(write(tmp_path, "name: [unclosed"))


def test_suite_must_be_a_mapping(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="must be a mapping"):
        load_suite(write(tmp_path, "- just\n- a list\n"))


def test_error_points_to_the_case_by_id(tmp_path: Path) -> None:
    broken = VALID_SUITE.replace("severity: low", "severity: urgent")

    with pytest.raises(SuiteError, match=r"cases\[greeting\]\.severity"):
        load_suite(write(tmp_path, broken))

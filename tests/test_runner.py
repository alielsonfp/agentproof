import json
from datetime import datetime
from pathlib import Path

from fakes import FakeAdapter

from agentproof.models import Result, Severity, Suite, TestCase
from agentproof.runner import default_output_dir, run_case, run_suite, save_results


def make_case(case_id: str = "greeting", *messages: str, **extra: object) -> TestCase:
    return TestCase.model_validate(
        {
            "id": case_id,
            "description": "test",
            "severity": "medium",
            "turns": [{"user": m} for m in (messages or ["oi"])],
            "expect": [{"rule": "must_not_contain", "text": "Pix"}],
            **extra,
        }
    )


def test_run_case_records_every_turn_and_tool_call() -> None:
    result = run_case(FakeAdapter(), make_case("greeting", "oi", "tudo bem?"))

    assert result.error is None
    assert result.transcript is not None
    assert [t.user for t in result.transcript.turns] == ["oi", "tudo bem?"]
    assert result.transcript.turns[1].agent == "echo: tudo bem?"
    assert result.transcript.all_tool_calls()[0].name == "echo"


def test_run_case_adds_up_tokens() -> None:
    result = run_case(FakeAdapter(), make_case("greeting", "a", "b"))

    assert result.transcript is not None
    assert (result.transcript.input_tokens, result.transcript.output_tokens) == (6, 4)


def test_run_case_records_model_and_prompt_version() -> None:
    result = run_case(FakeAdapter(prompt_version="v2"), make_case())

    assert result.transcript is not None
    assert result.transcript.model == "fake-model"
    assert result.transcript.prompt_version == "v2"


def test_crash_becomes_an_error_and_keeps_earlier_turns() -> None:
    adapter = FakeAdapter(fail_on="boom")

    result = run_case(adapter, make_case("crash", "oi", "boom", "never sent"))

    assert result.error == "TimeoutError: model took too long"
    assert result.passed is False
    assert result.transcript is not None
    assert [t.user for t in result.transcript.turns] == ["oi"]


def test_unsupported_setup_becomes_an_error() -> None:
    case = make_case("fail", setup={"fail_tool": "book_appointment"})

    result = run_case(FakeAdapter(), case)

    assert result.error == "UnsupportedSetupError: fail_tool is not supported"


def test_run_suite_gives_each_case_a_fresh_session() -> None:
    adapter = FakeAdapter(fail_on="boom")
    suite = Suite(
        name="demo",
        cases=[make_case("a"), make_case("b", "boom"), make_case("c")],
    )
    finished: list[str] = []

    results = run_suite(adapter, suite, on_result=lambda r: finished.append(r.case_id))

    assert finished == ["a", "b", "c"]  # a crash in "b" does not stop the suite
    assert [r.error is None for r in results] == [True, False, True]
    assert adapter.sessions_started == 3


def test_save_results_writes_one_readable_json_per_case(tmp_path: Path) -> None:
    result = run_case(FakeAdapter(), make_case("acentos", "Olá, está aberto?"))

    save_results([result], tmp_path / "out")

    path = tmp_path / "out" / "acentos.json"
    text = path.read_text(encoding="utf-8")
    assert "Olá, está aberto?" in text  # accents kept, not escaped as á
    loaded = Result.model_validate(json.loads(text))
    assert loaded.severity is Severity.MEDIUM
    assert loaded.transcript == result.transcript


def test_default_output_dir_has_suite_prompt_and_time() -> None:
    path = default_output_dir("clinic", "v1", now=datetime(2027, 3, 1, 9, 30, 5))

    assert path == Path("reports") / "clinic-v1-20270301-093005"

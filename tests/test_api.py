from pathlib import Path

import pytest
from test_cli import write_suite

from agentproof.api import (
    AgentProofError,
    compare_runs,
    load_factory,
    load_run,
    prepare_run,
)


def test_prepare_then_execute_saves_the_run(tmp_path: Path) -> None:
    out = tmp_path / "out"
    prepared = prepare_run(write_suite(tmp_path), prompt="v2", out=out)
    seen: list[str] = []

    report = prepared.execute(on_result=lambda r: seen.append(r.case_id))

    assert prepared.judge is None  # the suite has no judge checks
    assert report.prompt_version == "v2"
    assert seen == ["greeting"]
    assert load_run(out) == report


def test_prepare_fails_before_running_on_a_bad_suite(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("name: [unclosed", encoding="utf-8")

    with pytest.raises(AgentProofError, match="invalid YAML"):
        prepare_run(path)


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("no_colon", "use module:function"),
        ("nowhere:missing", "Cannot load agent"),
        ("fakes:missing", "Cannot load agent"),
    ],
)
def test_load_factory_errors(target: str, message: str) -> None:
    with pytest.raises(AgentProofError, match=message):
        load_factory(target)


def test_compare_runs(tmp_path: Path) -> None:
    suite = write_suite(tmp_path)
    prepare_run(suite, prompt="v1", out=tmp_path / "v1").execute()
    prepare_run(suite, prompt="v2", out=tmp_path / "v2").execute()

    comparison = compare_runs(tmp_path / "v1", tmp_path / "v2")

    assert comparison.base.startswith("v1")
    assert not comparison.has_regressions


def test_load_run_explains_a_missing_run(tmp_path: Path) -> None:
    with pytest.raises(AgentProofError, match="Cannot read a run"):
        load_run(tmp_path)

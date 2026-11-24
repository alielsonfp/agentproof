import io
from pathlib import Path

from typer.testing import CliRunner

from agentproof.cli import app, safe_output

runner = CliRunner()

SUITE = """
name: demo
{agent}
cases:
  - id: greeting
    description: Says hello.
    severity: low
    turns:
      - user: {message}
    expect:
      - rule: must_not_contain
        text: Pix
"""


def write_suite(
    tmp_path: Path,
    agent: str = "agent: fakes:create_fake_adapter",
    message: str = "oi",
) -> Path:
    path = tmp_path / "suite.yaml"
    path.write_text(SUITE.format(agent=agent, message=message), encoding="utf-8")
    return path


def test_run_saves_transcripts(tmp_path: Path) -> None:
    out = tmp_path / "out"

    result = runner.invoke(app, ["run", str(write_suite(tmp_path)), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert "PASS  greeting" in result.output
    assert "1/1 cases passed" in result.output
    assert (out / "greeting.json").exists()
    assert (out / "summary.json").exists()
    assert (out / "report.md").exists()


def test_report_shows_a_previous_run(tmp_path: Path) -> None:
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(write_suite(tmp_path)), "--out", str(out)])

    result = runner.invoke(app, ["report", str(out)])

    assert result.exit_code == 0, result.output
    assert "greeting" in result.output
    assert "1/1 cases passed" in result.output


def test_report_rejects_a_folder_without_a_run(tmp_path: Path) -> None:
    result = runner.invoke(app, ["report", str(tmp_path)])

    assert result.exit_code == 2
    assert "Cannot read a run" in result.output


def test_run_exits_with_1_and_shows_why_a_case_failed(tmp_path: Path) -> None:
    suite = write_suite(tmp_path, message="quero pagar com Pix")

    result = runner.invoke(app, ["run", str(suite), "--out", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "FAIL  greeting" in result.output
    assert "must_not_contain: turn 1 contains 'Pix'" in result.output


def test_run_rejects_unknown_rules_before_running(tmp_path: Path) -> None:
    suite = write_suite(tmp_path)
    suite.write_text(
        suite.read_text(encoding="utf-8").replace("must_not_contain", "be_nice"),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["run", str(suite)])

    assert result.exit_code == 2
    assert "unknown rule 'be_nice'" in result.output


def test_run_exits_with_1_when_a_case_crashes(tmp_path: Path) -> None:
    suite = write_suite(tmp_path, message="boom")

    result = runner.invoke(app, ["run", str(suite), "--out", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "ERROR greeting" in result.output


def test_run_rejects_an_invalid_suite(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("name: [unclosed", encoding="utf-8")

    result = runner.invoke(app, ["run", str(path)])

    assert result.exit_code == 2
    assert "invalid YAML" in result.output


def test_run_needs_an_agent(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", str(write_suite(tmp_path, agent=""))])

    assert result.exit_code == 2
    assert "No agent to test" in result.output


def test_agent_option_overrides_the_suite(tmp_path: Path) -> None:
    suite = write_suite(tmp_path, agent="agent: nowhere:missing")

    result = runner.invoke(
        app,
        [
            "run",
            str(suite),
            "--agent",
            "fakes:create_fake_adapter",
            "--out",
            str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 0, result.output


def test_run_reports_an_agent_that_cannot_be_loaded(tmp_path: Path) -> None:
    suite = write_suite(tmp_path, agent="agent: nowhere:missing")

    result = runner.invoke(app, ["run", str(suite)])

    assert result.exit_code == 2
    assert "Cannot load agent 'nowhere:missing'" in result.output


def test_safe_output_replaces_characters_the_terminal_cannot_show() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")

    safe_output(stream)
    stream.write("v1 → v2")
    stream.flush()

    assert raw.getvalue() == b"v1 ? v2"

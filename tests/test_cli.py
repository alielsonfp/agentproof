from pathlib import Path

from typer.testing import CliRunner

from agentproof.cli import app

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
    assert "ran   greeting" in result.output
    assert (out / "greeting.json").exists()


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

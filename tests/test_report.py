from datetime import datetime
from pathlib import Path

from rich.console import Console

from agentproof.models import (
    CheckResult,
    Result,
    RunReport,
    Severity,
    ToolCallRecord,
    Transcript,
    TranscriptTurn,
)
from agentproof.report import load_report, print_report, save_report, to_markdown


def make_report() -> RunReport:
    transcript = Transcript(
        case_id="invented_price",
        model="m",
        prompt_version="v1",
        turns=[
            TranscriptTurn(
                user="Quanto custa?",
                agent="Custa R$ 150,00.",
                tool_calls=[
                    ToolCallRecord(
                        name="lookup", arguments={"q": "x"}, result={"ok": True}
                    )
                ],
            )
        ],
        input_tokens=100,
        output_tokens=20,
    )
    return RunReport(
        suite="clinic",
        model="m",
        prompt_version="v1",
        created_at=datetime(2027, 3, 1, 9, 30),
        results=[
            Result(
                case_id="urgency",
                severity=Severity.HIGH,
                checks=[CheckResult(rule="must_call_tool", passed=True)],
            ),
            Result(
                case_id="invented_price",
                severity=Severity.HIGH,
                checks=[
                    CheckResult(
                        rule="price_matches_tool",
                        passed=False,
                        detail="turn 1 says R$ 150,00 | no tool",
                    )
                ],
                transcript=transcript,
            ),
            Result(
                case_id="crashed", severity=Severity.LOW, error="TimeoutError: slow"
            ),
        ],
    )


def test_passed_count_and_tokens() -> None:
    report = make_report()

    assert report.passed_count == 1
    assert report.tokens == (100, 20)


def test_terminal_report_shows_status_and_failure_details() -> None:
    console = Console(record=True, width=140)

    print_report(make_report(), console)

    text = console.export_text()
    assert "PASS" in text and "FAIL" in text and "ERROR" in text
    assert "price_matches_tool: turn 1 says R$ 150,00" in text
    assert "TimeoutError: slow" in text
    assert "1/3 cases passed" in text


def test_markdown_has_summary_table_and_failed_transcripts() -> None:
    markdown = to_markdown(make_report())

    assert "**1/3 cases passed**" in markdown
    assert "| urgency | high | PASS | - |" in markdown
    # Pipes inside details are escaped so the table does not break.
    assert "R$ 150,00 \\| no tool" in markdown
    assert "### invented_price" in markdown
    assert '- tool `lookup({"q": "x"})` → `{"ok": true}`' in markdown
    assert "**Agent:** Custa R$ 150,00." in markdown
    assert "### urgency" not in markdown  # passed cases have no transcript section


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    report = make_report()

    save_report(report, tmp_path)

    assert (tmp_path / "report.md").exists()
    assert load_report(tmp_path) == report
    assert load_report(tmp_path / "summary.json") == report

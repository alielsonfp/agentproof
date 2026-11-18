"""Reports for a run: a table in the terminal, JSON and Markdown files."""

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agentproof.models import Result, RunReport

SUMMARY_FILE = "summary.json"
MARKDOWN_FILE = "report.md"

_STATUS_STYLE = {"PASS": "bold green", "FAIL": "bold red", "ERROR": "bold yellow"}
_SEVERITY_STYLE = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
}


# Files


def save_report(report: RunReport, out_dir: Path) -> None:
    """Write summary.json (everything, for tools) and report.md (for people)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SUMMARY_FILE).write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / MARKDOWN_FILE).write_text(to_markdown(report), encoding="utf-8")


def load_report(path: Path) -> RunReport:
    """Load a saved run, from its folder or its summary.json."""
    if path.is_dir():
        path = path / SUMMARY_FILE
    return RunReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


# Terminal


def print_report(report: RunReport, console: Console | None = None) -> None:
    console = console or Console()
    table = Table(
        title=f"{report.suite} · prompt {report.prompt_version} · {report.model}"
    )
    table.add_column("Case", no_wrap=True)
    table.add_column("Severity")
    table.add_column("Result")
    table.add_column("Details", overflow="fold")

    for result in report.results:
        severity = result.severity.value
        table.add_row(
            result.case_id,
            f"[{_SEVERITY_STYLE[severity]}]{severity}[/]",
            f"[{_STATUS_STYLE[result.status]}]{result.status}[/]",
            _details(result),
        )

    console.print(table)
    total = len(report.results)
    tokens_in, tokens_out = report.tokens
    style = "green" if report.passed_count == total else "red"
    console.print(
        f"[{style}]{report.passed_count}/{total} cases passed[/]"
        f" · tokens {tokens_in} in / {tokens_out} out"
    )


def _details(result: Result) -> str:
    if result.error:
        return result.error
    failed = [f"{c.rule}: {c.detail}" for c in result.checks if not c.passed]
    return "\n".join(failed)


# Markdown


def to_markdown(report: RunReport) -> str:
    total = len(report.results)
    tokens_in, tokens_out = report.tokens
    lines = [
        f"# AgentProof report: {report.suite}",
        "",
        f"- Model: `{report.model}`",
        f"- Prompt version: `{report.prompt_version}`",
        f"- Date: {report.created_at:%Y-%m-%d %H:%M}",
        f"- Result: **{report.passed_count}/{total} cases passed**",
        f"- Tokens: {tokens_in} in / {tokens_out} out",
        "",
        "| Case | Severity | Result | Details |",
        "| --- | --- | --- | --- |",
    ]
    for result in report.results:
        cells = [
            result.case_id,
            result.severity.value,
            result.status,
            _md_cell(_details(result)) or "-",
        ]
        lines.append("| " + " | ".join(cells) + " |")

    failed = [
        r
        for r in report.results
        if not r.passed and r.transcript and r.transcript.turns
    ]
    if failed:
        lines += ["", "## Transcripts of failed cases"]
        for result in failed:
            lines += ["", f"### {result.case_id}", ""]
            lines += _md_transcript(result)
    return "\n".join(lines) + "\n"


def _md_transcript(result: Result) -> list[str]:
    assert result.transcript is not None
    lines: list[str] = []
    for turn in result.transcript.turns:
        lines.append(f"**User:** {turn.user}")
        lines.append("")
        for call in turn.tool_calls:
            arguments = json.dumps(call.arguments, ensure_ascii=False)
            output = json.dumps(call.result, ensure_ascii=False)
            lines.append(f"- tool `{call.name}({arguments})` → `{output}`")
        if turn.tool_calls:
            lines.append("")
        lines.append(f"**Agent:** {turn.agent}")
        lines.append("")
    return lines


def _md_cell(text: str) -> str:
    """Keep a table cell on one line and stop pipes from breaking the table."""
    return text.replace("|", "\\|").replace("\n", "<br>")

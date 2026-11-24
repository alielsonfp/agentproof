"""MCP server: lets any MCP-compatible assistant run AgentProof.

Exposes four tools over stdio: list_cases, run_suite, get_report and
compare_versions. They call the same functions as the CLI (agentproof.api).

Paths are relative to the folder the server was started in, and must stay
inside it: an assistant can be tricked by text it reads, so the server never
reads or writes files elsewhere.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from agentproof import api
from agentproof.compare import Change, Comparison
from agentproof.models import Result, RunReport
from agentproof.report import to_markdown

server = MCPServer(
    name="agentproof",
    instructions=(
        "Regression tests for customer-facing AI agents. Use list_cases to see"
        " a suite, run_suite to test one prompt version (it calls the model for"
        " every case, so it can take minutes), then compare_versions on two"
        " runs to see what was fixed and what regressed."
    ),
)


class CaseInfo(BaseModel):
    id: str
    description: str
    severity: str
    rules: list[str]


class SuiteInfo(BaseModel):
    name: str
    description: str
    agent: str | None
    cases: list[CaseInfo]


class CaseSummary(BaseModel):
    case_id: str
    severity: str
    status: str  # PASS, FAIL or ERROR
    failures: list[str]  # why it failed; empty when it passed


class RunSummary(BaseModel):
    run_dir: str  # pass this to get_report or compare_versions
    suite: str
    model: str
    prompt_version: str
    passed: int
    total: int
    cases: list[CaseSummary]


class ChangeSummary(BaseModel):
    case_id: str
    severity: str
    before: str | None
    after: str | None
    change: str


class ComparisonSummary(BaseModel):
    base: str
    new: str
    fixed: int
    regressed: int
    has_regressions: bool
    changes: list[ChangeSummary]


@server.tool()
def list_cases(suite_path: str) -> SuiteInfo:
    """List the test cases of a YAML suite, with the rules each one checks."""
    suite = _call(api.load_checked_suite, _project_path(suite_path))
    return SuiteInfo(
        name=suite.name,
        description=suite.description,
        agent=suite.agent,
        cases=[
            CaseInfo(
                id=case.id,
                description=case.description.strip(),
                severity=case.severity.value,
                rules=[e.rule for e in case.expect],
            )
            for case in suite.cases
        ],
    )


@server.tool()
def run_suite(
    suite_path: str,
    prompt_version: str = "v1",
    model: str | None = None,
    out_dir: str | None = None,
) -> RunSummary:
    """Run a suite against its agent with one prompt version and save the run.

    Calls the model for every case, so it costs tokens and can take minutes.
    Returns the run folder, to use with get_report and compare_versions.
    """
    out = _project_path(out_dir) if out_dir else None
    prepared = _call(
        api.prepare_run,
        _project_path(suite_path),
        prompt=prompt_version,
        model=model,
        out=out,
    )
    report = prepared.execute()
    return _summarize(report, prepared.out_dir)


@server.tool()
def get_report(
    run_dir: str, format: Literal["summary", "markdown"] = "summary"
) -> RunSummary | str:
    """Read a saved run: a structured summary, or the Markdown report with
    the transcripts of failed cases."""
    path = _project_path(run_dir)
    report = _call(api.load_run, path)
    if format == "markdown":
        return to_markdown(report)
    return _summarize(report, path)


@server.tool()
def compare_versions(base_run_dir: str, new_run_dir: str) -> ComparisonSummary:
    """Compare two saved runs of the same suite (for example prompt v1 and v2).

    A regression is a case that passed in the base run and fails in the new one.
    """
    comparison = _call(
        api.compare_runs, _project_path(base_run_dir), _project_path(new_run_dir)
    )
    return _summarize_comparison(comparison)


def main() -> None:
    """Entry point for `agentproof-mcp`: serve over stdio."""
    server.run()


# Helpers


def _project_path(value: str) -> Path:
    root = Path.cwd().resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ToolError(f"'{value}' is outside the project folder {root}.")
    return path


def _call[T](function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Turn errors the user can fix into ToolError, so the assistant sees the
    message instead of a generic "error executing tool"."""
    try:
        return function(*args, **kwargs)
    except api.AgentProofError as error:
        raise ToolError(str(error)) from None


def _summarize(report: RunReport, run_dir: Path) -> RunSummary:
    return RunSummary(
        run_dir=_relative(run_dir),
        suite=report.suite,
        model=report.model,
        prompt_version=report.prompt_version,
        passed=report.passed_count,
        total=len(report.results),
        cases=[_summarize_case(result) for result in report.results],
    )


def _summarize_case(result: Result) -> CaseSummary:
    if result.error:
        failures = [result.error]
    else:
        failures = [f"{c.rule}: {c.detail}" for c in result.checks if not c.passed]
    return CaseSummary(
        case_id=result.case_id,
        severity=result.severity.value,
        status=result.status,
        failures=failures,
    )


def _summarize_comparison(comparison: Comparison) -> ComparisonSummary:
    return ComparisonSummary(
        base=comparison.base,
        new=comparison.new,
        fixed=comparison.count(Change.FIXED),
        regressed=comparison.count(Change.REGRESSED),
        has_regressions=comparison.has_regressions,
        changes=[
            ChangeSummary(
                case_id=c.case_id,
                severity=c.severity,
                before=c.before,
                after=c.after,
                change=c.change.value,
            )
            for c in comparison.changes
        ],
    )


def _relative(path: Path) -> str:
    root = Path.cwd().resolve()
    resolved = path.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return str(resolved)

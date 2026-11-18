from datetime import datetime
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from agentproof.cli import app
from agentproof.compare import Change, compare_reports, print_comparison
from agentproof.models import CheckResult, Result, RunReport, Severity
from agentproof.report import save_report

PASS = [CheckResult(rule="r", passed=True)]
FAIL = [CheckResult(rule="r", passed=False)]


def result(
    case_id: str, checks: list[CheckResult] | None = None, error: str | None = None
):
    return Result(
        case_id=case_id, severity=Severity.HIGH, checks=checks or [], error=error
    )


def report(version: str, *results: Result, suite: str = "clinic") -> RunReport:
    return RunReport(
        suite=suite,
        model="m",
        prompt_version=version,
        created_at=datetime(2027, 3, 1),
        results=list(results),
    )


BASE = report(
    "v1",
    result("fixed", FAIL),
    result("regressed", PASS),
    result("still_failing", FAIL),
    result("still_passing", PASS),
    result("crashed_then_fixed", error="TimeoutError"),
    result("removed", PASS),
)
NEW = report(
    "v2",
    result("fixed", PASS),
    result("regressed", FAIL),
    result("still_failing", FAIL),
    result("still_passing", PASS),
    result("crashed_then_fixed", PASS),
    result("new", PASS),
)


def test_every_kind_of_change_is_classified() -> None:
    comparison = compare_reports(BASE, NEW)

    assert {c.case_id: c.change for c in comparison.changes} == {
        "fixed": Change.FIXED,
        "regressed": Change.REGRESSED,
        "still_failing": Change.STILL_FAILING,
        "still_passing": Change.STILL_PASSING,
        "crashed_then_fixed": Change.FIXED,
        "new": Change.NEW,
        "removed": Change.REMOVED,
    }
    assert comparison.has_regressions is True


def test_cases_keep_the_new_run_order_then_removed_ones() -> None:
    ids = [c.case_id for c in compare_reports(BASE, NEW).changes]

    assert ids[-2:] == ["new", "removed"]


def test_before_and_after_status() -> None:
    changes = {c.case_id: c for c in compare_reports(BASE, NEW).changes}

    assert (
        changes["crashed_then_fixed"].before,
        changes["crashed_then_fixed"].after,
    ) == (
        "ERROR",
        "PASS",
    )
    assert changes["new"].before is None
    assert changes["removed"].after is None


def test_no_regressions() -> None:
    comparison = compare_reports(
        report("v1", result("a", FAIL)), report("v2", result("a", PASS))
    )

    assert comparison.has_regressions is False
    assert comparison.count(Change.FIXED) == 1


def test_printed_summary() -> None:
    console = Console(record=True, width=120)

    print_comparison(compare_reports(BASE, NEW), console)

    text = console.export_text()
    assert "v1 (m) → v2 (m)" in text
    assert "2 fixed · 1 regressed · 1 still failing · 1 still passing" in text


def save(tmp_path: Path, name: str, run: RunReport) -> Path:
    folder = tmp_path / name
    save_report(run, folder)
    return folder


def test_compare_command_exits_1_on_regressions(tmp_path: Path) -> None:
    base, new = save(tmp_path, "base", BASE), save(tmp_path, "new", NEW)

    outcome = CliRunner().invoke(app, ["compare", str(base), str(new)])

    assert outcome.exit_code == 1
    assert "regressed" in outcome.output


def test_compare_command_exits_0_without_regressions(tmp_path: Path) -> None:
    base = save(tmp_path, "base", report("v1", result("a", FAIL)))
    new = save(tmp_path, "new", report("v2", result("a", PASS)))

    outcome = CliRunner().invoke(app, ["compare", str(base), str(new)])

    assert outcome.exit_code == 0, outcome.output


def test_compare_command_rejects_different_suites(tmp_path: Path) -> None:
    base = save(tmp_path, "base", report("v1", result("a", PASS)))
    new = save(tmp_path, "new", report("v2", result("a", PASS), suite="hotel"))

    outcome = CliRunner().invoke(app, ["compare", str(base), str(new)])

    assert outcome.exit_code == 2
    assert "different suites" in outcome.output

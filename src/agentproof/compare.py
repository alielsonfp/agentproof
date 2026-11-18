"""Compare two runs of the same suite: what improved and what regressed."""

from dataclasses import dataclass
from enum import StrEnum

from rich.console import Console
from rich.table import Table

from agentproof.models import Result, RunReport


class Change(StrEnum):
    FIXED = "fixed"  # failed before, passes now
    REGRESSED = "regressed"  # passed before, fails now
    STILL_FAILING = "still failing"
    STILL_PASSING = "still passing"
    NEW = "new"  # only in the new run
    REMOVED = "removed"  # only in the base run


@dataclass(frozen=True)
class CaseChange:
    case_id: str
    severity: str
    before: str | None  # PASS, FAIL, ERROR, or None when the case is missing
    after: str | None
    change: Change


@dataclass(frozen=True)
class Comparison:
    base: str
    new: str
    changes: list[CaseChange]

    def count(self, change: Change) -> int:
        return sum(c.change is change for c in self.changes)

    @property
    def has_regressions(self) -> bool:
        return self.count(Change.REGRESSED) > 0


def compare_reports(base: RunReport, new: RunReport) -> Comparison:
    """Match cases by id. An ERROR counts as a failure."""
    before = {r.case_id: r for r in base.results}
    after = {r.case_id: r for r in new.results}
    # Keep the new run's order, then cases that only exist in the base run.
    ids = [r.case_id for r in new.results]
    ids += [case_id for case_id in before if case_id not in after]

    changes = []
    for case_id in ids:
        old, current = before.get(case_id), after.get(case_id)
        severity = (current or old).severity.value  # type: ignore[union-attr]
        changes.append(
            CaseChange(
                case_id=case_id,
                severity=severity,
                before=old.status if old else None,
                after=current.status if current else None,
                change=_classify(old, current),
            )
        )
    return Comparison(base=_label(base), new=_label(new), changes=changes)


def print_comparison(comparison: Comparison, console: Console | None = None) -> None:
    console = console or Console()
    table = Table(title=f"{comparison.base} → {comparison.new}")
    table.add_column("Case", no_wrap=True)
    table.add_column("Severity")
    table.add_column("Before")
    table.add_column("After")
    table.add_column("Change")

    for item in comparison.changes:
        table.add_row(
            item.case_id,
            item.severity,
            item.before or "-",
            item.after or "-",
            f"[{_CHANGE_STYLE[item.change]}]{item.change.value}[/]",
        )
    console.print(table)
    console.print(
        f"[green]{comparison.count(Change.FIXED)} fixed[/] · "
        f"[red]{comparison.count(Change.REGRESSED)} regressed[/] · "
        f"{comparison.count(Change.STILL_FAILING)} still failing · "
        f"{comparison.count(Change.STILL_PASSING)} still passing"
    )


_CHANGE_STYLE = {
    Change.FIXED: "bold green",
    Change.REGRESSED: "bold red",
    Change.STILL_FAILING: "red",
    Change.STILL_PASSING: "green",
    Change.NEW: "cyan",
    Change.REMOVED: "dim",
}


def _classify(old: Result | None, current: Result | None) -> Change:
    if old is None:
        return Change.NEW
    if current is None:
        return Change.REMOVED
    if old.passed and current.passed:
        return Change.STILL_PASSING
    if old.passed:
        return Change.REGRESSED
    if current.passed:
        return Change.FIXED
    return Change.STILL_FAILING


def _label(report: RunReport) -> str:
    return f"{report.prompt_version} ({report.model})"

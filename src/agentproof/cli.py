"""AgentProof command line."""

import io
import sys
from pathlib import Path
from typing import Annotated, NoReturn, TextIO

import typer

from agentproof.api import AgentProofError, compare_runs, load_run, prepare_run
from agentproof.compare import print_comparison
from agentproof.models import Result
from agentproof.report import print_report

app = typer.Typer(
    help="Regression testing for customer-facing AI agents.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Regression testing for customer-facing AI agents."""
    for stream in (sys.stdout, sys.stderr):
        safe_output(stream)


def safe_output(stream: TextIO) -> None:
    """Never crash on characters the terminal cannot show (like → on cp1252).

    On Windows, output redirected to a file or a CI log often uses cp1252.
    Without this, a report with an arrow would crash with exit code 1, which
    looks exactly like "something regressed".
    """
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(errors="replace")


@app.command()
def run(
    suite_path: Annotated[Path, typer.Argument(help="YAML suite to run.")],
    agent: Annotated[
        str | None,
        typer.Option(help="Adapter factory as module:function. Default: the suite's."),
    ] = None,
    prompt: Annotated[str, typer.Option(help="Prompt version to test.")] = "v1",
    model: Annotated[str | None, typer.Option(help="Model name.")] = None,
    judge_model: Annotated[
        str | None, typer.Option(help="Model for judge checks (Gemini).")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Folder for the results.")] = None,
) -> None:
    """Run a suite against an agent, check it and save the results."""
    try:
        prepared = prepare_run(suite_path, agent, prompt, model, judge_model, out)
    except AgentProofError as error:
        _fail(str(error))

    adapter = prepared.adapter
    typer.echo(
        f"Running {len(prepared.suite.cases)} cases from '{prepared.suite.name}'"
        f" (prompt {adapter.prompt_version}, model {adapter.model})"
    )
    report = prepared.execute(on_result=_print_progress)

    typer.echo("")
    print_report(report)
    typer.echo(f"Results saved to {prepared.out_dir}")
    if report.passed_count < len(report.results):
        raise typer.Exit(code=1)


@app.command()
def report(
    run_dir: Annotated[Path, typer.Argument(help="Folder of a previous run.")],
) -> None:
    """Show the report of a previous run again."""
    try:
        print_report(load_run(run_dir))
    except AgentProofError as error:
        _fail(str(error))


@app.command()
def compare(
    base_dir: Annotated[Path, typer.Argument(help="Folder of the base run (before).")],
    new_dir: Annotated[Path, typer.Argument(help="Folder of the new run (after).")],
) -> None:
    """Compare two runs and show what improved and what regressed.

    Exits with code 1 when something regressed, so CI can block the change.
    """
    try:
        comparison = compare_runs(base_dir, new_dir)
    except AgentProofError as error:
        _fail(str(error))
    print_comparison(comparison)
    if comparison.has_regressions:
        raise typer.Exit(code=1)


def _print_progress(result: Result) -> None:
    typer.echo(f"  {result.status:<5} {result.case_id}")


def _fail(message: str, code: int = 2) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)

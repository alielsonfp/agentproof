"""AgentProof command line."""

import importlib
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from dotenv import load_dotenv

from agentproof.adapters import AgentAdapter
from agentproof.evaluators import Judge, check_suite, uses_judge
from agentproof.loader import SuiteError, load_suite
from agentproof.models import Result, RunReport
from agentproof.providers.gemini import DEFAULT_MODEL, GeminiProvider
from agentproof.report import load_report, print_report, save_report
from agentproof.runner import default_output_dir, run_suite, save_results

app = typer.Typer(
    help="Regression testing for customer-facing AI agents.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Regression testing for customer-facing AI agents."""


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
    load_dotenv()  # API keys from .env
    try:
        suite = load_suite(suite_path)
    except SuiteError as error:
        _fail(str(error))
    problems = check_suite(suite)
    if problems:
        _fail(f"{suite_path}: invalid expectations\n" + "\n".join(problems))

    target = agent or suite.agent
    if not target:
        _fail("No agent to test: add 'agent:' to the suite or pass --agent.")
    factory = _load_factory(target)
    adapter = factory(prompt_version=prompt, model=model)
    out_dir = out or default_output_dir(suite.name, prompt)
    # Only build a judge when the suite needs one, so rule-only suites never
    # need an API key for it.
    judge = None
    if uses_judge(suite):
        judge = Judge(GeminiProvider(judge_model or DEFAULT_MODEL))

    typer.echo(
        f"Running {len(suite.cases)} cases from '{suite.name}'"
        f" (prompt {adapter.prompt_version}, model {adapter.model})"
    )
    results = run_suite(adapter, suite, on_result=_print_progress, judge=judge)
    report = RunReport(
        suite=suite.name,
        model=adapter.model,
        prompt_version=adapter.prompt_version,
        created_at=datetime.now(),
        results=results,
    )
    save_results(results, out_dir)
    save_report(report, out_dir)

    typer.echo("")
    print_report(report)
    typer.echo(f"Results saved to {out_dir}")
    if report.passed_count < len(results):
        raise typer.Exit(code=1)


@app.command()
def report(
    run_dir: Annotated[Path, typer.Argument(help="Folder of a previous run.")],
) -> None:
    """Show the report of a previous run again."""
    try:
        saved = load_report(run_dir)
    except (OSError, ValueError) as error:
        _fail(f"Cannot read a run from {run_dir}: {error}")
    print_report(saved)


def _print_progress(result: Result) -> None:
    typer.echo(f"  {result.status:<5} {result.case_id}")


def _load_factory(target: str) -> Callable[..., AgentAdapter]:
    module_name, _, attribute = target.partition(":")
    if not module_name or not attribute:
        _fail(f"Invalid agent '{target}': use module:function.")
    # Console scripts do not put the current folder on the import path, so
    # agents that live in the project (like examples/) would not be found.
    sys.path.insert(0, str(Path.cwd()))
    try:
        module = importlib.import_module(module_name)
        return getattr(module, attribute)
    except (ImportError, AttributeError) as error:
        _fail(f"Cannot load agent '{target}': {error}")


def _fail(message: str, code: int = 2) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)

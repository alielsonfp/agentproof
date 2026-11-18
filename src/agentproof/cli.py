"""AgentProof command line."""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from agentproof.adapters import AgentAdapter
from agentproof.loader import SuiteError, load_suite
from agentproof.models import Result
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
    out: Annotated[Path | None, typer.Option(help="Folder for the results.")] = None,
) -> None:
    """Run a suite against an agent and save every transcript as JSON."""
    try:
        suite = load_suite(suite_path)
    except SuiteError as error:
        _fail(str(error))

    target = agent or suite.agent
    if not target:
        _fail("No agent to test: add 'agent:' to the suite or pass --agent.")
    factory = _load_factory(target)
    adapter = factory(prompt_version=prompt, model=model)
    out_dir = out or default_output_dir(suite.name, prompt)

    typer.echo(
        f"Running {len(suite.cases)} cases from '{suite.name}'"
        f" (prompt {adapter.prompt_version}, model {adapter.model})"
    )
    results = run_suite(adapter, suite, on_result=_print_progress)
    save_results(results, out_dir)
    typer.echo(f"Transcripts saved to {out_dir}")

    if any(result.error for result in results):
        raise typer.Exit(code=1)


def _print_progress(result: Result) -> None:
    if result.error:
        typer.echo(f"  ERROR {result.case_id}: {result.error}")
    else:
        typer.echo(f"  ran   {result.case_id}")


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

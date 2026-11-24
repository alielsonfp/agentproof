"""High-level actions shared by the CLI and the MCP server.

Each function either returns a result or raises AgentProofError with a
message the user can act on. The CLI prints that message; the MCP server
sends it back to the assistant that called the tool.
"""

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agentproof.adapters import AgentAdapter
from agentproof.compare import Comparison, compare_reports
from agentproof.evaluators import Judge, check_suite, uses_judge
from agentproof.loader import SuiteError, load_suite
from agentproof.models import Result, RunReport, Suite
from agentproof.providers.gemini import DEFAULT_MODEL, GeminiProvider
from agentproof.report import load_report, save_report
from agentproof.runner import default_output_dir, run_suite, save_results

AdapterFactory = Callable[..., AgentAdapter]


class AgentProofError(Exception):
    """Something the user can fix: a bad suite, an unknown agent, a missing run."""


def load_checked_suite(path: Path) -> Suite:
    """Load a suite and check its rules, before any model is called."""
    try:
        suite = load_suite(path)
    except SuiteError as error:
        raise AgentProofError(str(error)) from None
    problems = check_suite(suite)
    if problems:
        raise AgentProofError(f"{path}: invalid expectations\n" + "\n".join(problems))
    return suite


def load_factory(target: str) -> AdapterFactory:
    """Import an adapter factory written as `module:function`."""
    module_name, _, attribute = target.partition(":")
    if not module_name or not attribute:
        raise AgentProofError(f"Invalid agent '{target}': use module:function.")
    # Console scripts do not put the current folder on the import path, so
    # agents that live in the project (like examples/) would not be found.
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        module = importlib.import_module(module_name)
        return getattr(module, attribute)
    except (ImportError, AttributeError) as error:
        raise AgentProofError(f"Cannot load agent '{target}': {error}") from None


@dataclass
class PreparedRun:
    """A suite, its agent and its judge, ready to run.

    Preparing and running are separate steps so the caller can show what is
    about to run (and fail fast on setup problems) before any model is called.
    """

    suite: Suite
    adapter: AgentAdapter
    judge: Judge | None
    out_dir: Path

    def execute(self, on_result: Callable[[Result], None] | None = None) -> RunReport:
        """Run every case, then save the transcripts and the reports."""
        results = run_suite(
            self.adapter, self.suite, on_result=on_result, judge=self.judge
        )
        report = RunReport(
            suite=self.suite.name,
            model=self.adapter.model,
            prompt_version=self.adapter.prompt_version,
            created_at=datetime.now(),
            results=results,
        )
        save_results(results, self.out_dir)
        save_report(report, self.out_dir)
        return report


def prepare_run(
    suite_path: Path,
    agent: str | None = None,
    prompt: str = "v1",
    model: str | None = None,
    judge_model: str | None = None,
    out: Path | None = None,
) -> PreparedRun:
    load_dotenv()  # API keys from .env
    suite = load_checked_suite(suite_path)
    target = agent or suite.agent
    if not target:
        raise AgentProofError(
            "No agent to test: add 'agent:' to the suite or pass an agent."
        )
    adapter = load_factory(target)(prompt_version=prompt, model=model)
    # Only build a judge when the suite needs one, so rule-only suites never
    # need an API key for it.
    judge = None
    if uses_judge(suite):
        judge = Judge(GeminiProvider(judge_model or DEFAULT_MODEL))
    out_dir = out or default_output_dir(suite.name, prompt)
    return PreparedRun(suite, adapter, judge, out_dir)


def load_run(run_dir: Path) -> RunReport:
    try:
        return load_report(run_dir)
    except (OSError, ValueError) as error:
        raise AgentProofError(f"Cannot read a run from {run_dir}: {error}") from None


def compare_runs(base_dir: Path, new_dir: Path) -> Comparison:
    base, new = load_run(base_dir), load_run(new_dir)
    if base.suite != new.suite:
        raise AgentProofError(
            f"Runs are from different suites: '{base.suite}' and '{new.suite}'."
        )
    return compare_reports(base, new)

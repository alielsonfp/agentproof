"""Run test cases against an agent and record what happened."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from agentproof.adapters import AgentAdapter
from agentproof.models import Result, Suite, TestCase, Transcript, TranscriptTurn


def run_case(adapter: AgentAdapter, case: TestCase) -> Result:
    """Play every turn of a case and return its result with the transcript.

    A crash (timeout, bad setup, ...) does not stop the suite: it becomes the
    result's error, and the turns played before it are kept for debugging.
    """
    transcript = Transcript(
        case_id=case.id, model=adapter.model, prompt_version=adapter.prompt_version
    )
    try:
        session = adapter.start(case.setup)
        for turn in case.turns:
            reply = session.send(turn.user)
            transcript.turns.append(
                TranscriptTurn(
                    user=turn.user,
                    agent=reply.text,
                    tool_calls=reply.tool_calls,
                    finished=reply.finished,
                )
            )
            transcript.input_tokens += reply.input_tokens
            transcript.output_tokens += reply.output_tokens
    except Exception as error:  # any crash is recorded in the result
        return Result(
            case_id=case.id,
            severity=case.severity,
            transcript=transcript,
            error=f"{type(error).__name__}: {error}",
        )
    return Result(case_id=case.id, severity=case.severity, transcript=transcript)


def run_suite(
    adapter: AgentAdapter,
    suite: Suite,
    on_result: Callable[[Result], None] | None = None,
) -> list[Result]:
    """Run every case in order. `on_result` is called as each case finishes,
    so the CLI can show progress."""
    results = []
    for case in suite.cases:
        result = run_case(adapter, case)
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results


def save_results(results: list[Result], out_dir: Path) -> None:
    """Write one JSON file per case, with the full transcript and tool calls."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        path = out_dir / f"{result.case_id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def default_output_dir(
    suite_name: str, prompt_version: str, now: datetime | None = None
) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return Path("reports") / f"{suite_name}-{prompt_version}-{stamp}"

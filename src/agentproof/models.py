"""Data models for test suites, transcripts and results.

Pydantic validates the YAML suites when they are loaded, so a typo in a suite
fails early with a clear message instead of in the middle of a run.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class _Strict(BaseModel):
    # Unknown fields are errors, so "turn:" instead of "turns:" is caught.
    model_config = ConfigDict(extra="forbid")


# Suites (what we write in YAML)


class Turn(_Strict):
    """One message the simulated user sends."""

    user: str = Field(min_length=1)


class Expectation(BaseModel):
    """One check on the conversation, such as `rule: must_call_tool`.

    Each rule takes its own options (for example `tool: handoff_to_human`),
    so extra fields are allowed here and read through `params`.
    """

    model_config = ConfigDict(extra="allow")

    rule: str = Field(min_length=1)

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class Setup(_Strict):
    """Conditions applied before the conversation starts."""

    fail_tool: str | None = None  # make this tool fail, to test error handling


class TestCase(_Strict):
    __test__ = False  # stops pytest from mistaking this class for a test

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str
    severity: Severity
    setup: Setup = Setup()
    turns: list[Turn] = Field(min_length=1)
    expect: list[Expectation] = Field(min_length=1)


class Suite(_Strict):
    name: str
    description: str = ""
    # Adapter factory as "module:function", used by `agentproof run`.
    agent: str | None = None
    cases: list[TestCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "Suite":
        ids = [case.id for case in self.cases]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(duplicates)}")
        return self


# Transcripts (what happened in a run)


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class TranscriptTurn(BaseModel):
    user: str
    agent: str
    tool_calls: list[ToolCallRecord] = []
    finished: bool = True  # False if the agent hit its step limit


class Transcript(BaseModel):
    case_id: str
    model: str
    prompt_version: str
    turns: list[TranscriptTurn] = []
    input_tokens: int = 0
    output_tokens: int = 0

    def all_tool_calls(self) -> list[ToolCallRecord]:
        return [call for turn in self.turns for call in turn.tool_calls]


# Results (what the checks concluded)


class CheckResult(BaseModel):
    rule: str
    passed: bool
    detail: str = ""


class Result(BaseModel):
    case_id: str
    severity: Severity
    checks: list[CheckResult] = []
    transcript: Transcript | None = None
    error: str | None = None  # set when the run itself crashed

    @computed_field  # included when the result is saved as JSON
    @property
    def passed(self) -> bool:
        return self.error is None and all(check.passed for check in self.checks)

    @property
    def status(self) -> str:
        if self.error is not None:
            return "ERROR"
        return "PASS" if self.passed else "FAIL"


class RunReport(BaseModel):
    """Everything about one run of a suite, saved as summary.json."""

    suite: str
    model: str
    prompt_version: str
    created_at: datetime
    results: list[Result]

    @computed_field
    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def tokens(self) -> tuple[int, int]:
        transcripts = [r.transcript for r in self.results if r.transcript]
        return (
            sum(t.input_tokens for t in transcripts),
            sum(t.output_tokens for t in transcripts),
        )

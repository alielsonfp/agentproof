"""Scheduling agent for a fictional dental clinic."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentproof.providers import Message, Provider, ToolCall, Usage
from examples.clinic_agent.backend import ClinicBackend
from examples.clinic_agent.tools import TOOL_SPECS, ToolResult, run_tool

ToolRunner = Callable[[ClinicBackend, str, dict[str, Any]], ToolResult]

PROMPTS_DIR = Path(__file__).parent / "prompts"

# The seed schedule starts on 2027-03-01, so "today" is fixed a few days
# before it. A fixed date also makes test runs repeatable.
DEFAULT_TODAY = "2027-02-26 (Friday)"


@dataclass(frozen=True)
class ToolRecord:
    """One tool call made during a turn, with what the tool returned."""

    call: ToolCall
    result: ToolResult


@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolRecord] = field(default_factory=list)
    usage: Usage = Usage()
    # False when the agent hit max_steps while still calling tools.
    finished: bool = True


def load_prompt(version: str) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


class ClinicAgent:
    """Talks to the model, runs the tools it asks for, and keeps the history."""

    def __init__(
        self,
        provider: Provider,
        backend: ClinicBackend,
        prompt: str,
        today: str = DEFAULT_TODAY,
        max_steps: int = 6,
        tool_runner: ToolRunner = run_tool,
    ) -> None:
        self.provider = provider
        self.backend = backend
        # Swappable so tests can make a tool fail without touching the agent.
        self.tool_runner = tool_runner
        # replace() instead of format(), so other braces in a prompt are safe.
        self.system = prompt.replace("{today}", today)
        self.max_steps = max_steps
        self.messages: list[Message] = []

    def send(self, text: str) -> AgentReply:
        """Send one user message and return the agent's reply for this turn."""
        start = len(self.messages)
        try:
            return self._run_turn(text)
        except Exception:
            # Undo the half-finished turn, so a failed call (a timeout, for
            # example) does not leave the history in a broken state.
            del self.messages[start:]
            raise

    def _run_turn(self, text: str) -> AgentReply:
        self.messages.append(Message(role="user", text=text))
        records: list[ToolRecord] = []
        input_tokens = output_tokens = 0

        # Each step: ask the model, then run any tools it asked for. Stop when
        # it answers with text only, or after max_steps.
        for _ in range(self.max_steps):
            response = self.provider.generate(self.system, self.messages, TOOL_SPECS)
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            message = response.message
            self.messages.append(message)

            if not message.tool_calls:
                usage = Usage(input_tokens, output_tokens)
                return AgentReply(message.text, records, usage)

            for call in message.tool_calls:
                result = self.tool_runner(self.backend, call.name, call.arguments)
                records.append(ToolRecord(call, result))
                self.messages.append(
                    Message(role="tool", tool_call=call, tool_result=result)
                )

        usage = Usage(input_tokens, output_tokens)
        return AgentReply(message.text, records, usage, finished=False)

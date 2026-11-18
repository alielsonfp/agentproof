"""The interface between the runner and an agent under test.

The runner never imports a specific agent. It only knows this interface, so
the same suite can test an in-process Python agent today and an HTTP agent on
another platform later.
"""

from dataclasses import dataclass, field
from typing import Protocol

from agentproof.models import Setup, ToolCallRecord


@dataclass
class AgentTurn:
    """What the agent did in response to one user message."""

    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    finished: bool = True
    input_tokens: int = 0
    output_tokens: int = 0


class AgentSession(Protocol):
    """One conversation with the agent."""

    def send(self, text: str) -> AgentTurn: ...


class AgentAdapter(Protocol):
    model: str
    prompt_version: str

    def start(self, setup: Setup) -> AgentSession:
        """Start a fresh conversation. Each test case gets its own session,
        so bookings made in one case never leak into the next."""
        ...


class UnsupportedSetupError(Exception):
    """The adapter cannot apply a setup option the test case asked for."""

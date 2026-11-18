"""Provider-neutral types for talking to a model.

Agents and evaluators only use these types. Each provider (Gemini, OpenAI,
Anthropic, ...) translates them to and from its own SDK, so switching models
never changes the agent code.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call, described with a JSON Schema."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asking to run one tool with some arguments."""

    name: str
    arguments: dict[str, Any]
    id: str | None = None


@dataclass
class Message:
    """One entry in a conversation.

    - user: text typed by the person
    - assistant: model output, with text and/or tool calls
    - tool: the result of one tool call, sent back to the model
    """

    role: Role
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call: ToolCall | None = None  # for role "tool": the call it answers
    tool_result: dict[str, Any] | None = None  # for role "tool"
    # The provider's own version of this message. Some providers need their
    # output sent back exactly as it came (Gemini thought signatures, for one).
    raw: Any = None


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    message: Message
    usage: Usage = Usage()


class Provider(Protocol):
    """Anything that can turn a conversation into the next assistant message."""

    model: str

    def generate(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse: ...

"""Fake models and agents for tests, so no test calls a real API."""

from agentproof.adapters import AgentTurn, UnsupportedSetupError
from agentproof.models import Setup, ToolCallRecord
from agentproof.providers import Message, ModelResponse, ToolSpec, Usage


class ScriptedProvider:
    """A fake model that returns pre-written messages, one per call."""

    model = "scripted"

    def __init__(self, *responses: Message) -> None:
        self.responses = list(responses)
        self.seen: list[list[Message]] = []  # what the agent sent each call
        self.system = ""

    def generate(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse:
        self.system = system
        self.seen.append(list(messages))
        return ModelResponse(self.responses.pop(0), Usage(10, 5))


class EchoSession:
    def __init__(self, fail_on: str | None) -> None:
        self.fail_on = fail_on

    def send(self, text: str) -> AgentTurn:
        if text == self.fail_on:
            raise TimeoutError("model took too long")
        call = ToolCallRecord(
            name="echo", arguments={"text": text}, result={"ok": True}
        )
        return AgentTurn(
            text=f"echo: {text}", tool_calls=[call], input_tokens=3, output_tokens=2
        )


class FakeAdapter:
    """Echoes every message back. Fails on the message given in `fail_on`."""

    model = "fake-model"

    def __init__(self, prompt_version: str = "v1", fail_on: str | None = None) -> None:
        self.prompt_version = prompt_version
        self.fail_on = fail_on
        self.sessions_started = 0

    def start(self, setup: Setup) -> EchoSession:
        if setup.fail_tool is not None:
            raise UnsupportedSetupError("fail_tool is not supported")
        self.sessions_started += 1
        return EchoSession(self.fail_on)


def create_fake_adapter(prompt_version: str = "v1", model: str | None = None):
    """Factory in the same shape `agentproof run` expects."""
    return FakeAdapter(prompt_version, fail_on="boom")

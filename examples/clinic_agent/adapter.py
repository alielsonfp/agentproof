"""Connects the clinic agent to the AgentProof runner."""

import os

from dotenv import load_dotenv

from agentproof.adapters import AgentTurn, UnsupportedSetupError
from agentproof.models import Setup, ToolCallRecord
from agentproof.providers import Provider
from agentproof.providers.gemini import DEFAULT_MODEL, GeminiProvider
from examples.clinic_agent.agent import ClinicAgent, load_prompt
from examples.clinic_agent.backend import ClinicBackend


class ClinicSession:
    def __init__(self, agent: ClinicAgent) -> None:
        self.agent = agent

    def send(self, text: str) -> AgentTurn:
        reply = self.agent.send(text)
        return AgentTurn(
            text=reply.text,
            tool_calls=[
                ToolCallRecord(
                    name=record.call.name,
                    arguments=record.call.arguments,
                    result=record.result,
                )
                for record in reply.tool_calls
            ],
            finished=reply.finished,
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
        )


class ClinicAdapter:
    def __init__(self, provider: Provider, prompt_version: str = "v1") -> None:
        self.provider = provider
        self.model = provider.model
        self.prompt_version = prompt_version
        self._prompt = load_prompt(prompt_version)

    def start(self, setup: Setup) -> ClinicSession:
        if setup.fail_tool is not None:
            raise UnsupportedSetupError("fail_tool is not supported yet")
        # A new backend per case: every case starts from the same schedule.
        agent = ClinicAgent(self.provider, ClinicBackend(), self._prompt)
        return ClinicSession(agent)


def create_adapter(
    prompt_version: str = "v1", model: str | None = None
) -> ClinicAdapter:
    """Factory used by `agentproof run`, through the suite's `agent` field."""
    load_dotenv()
    model = model or os.environ.get("AGENTPROOF_DEFAULT_MODEL") or DEFAULT_MODEL
    return ClinicAdapter(GeminiProvider(model), prompt_version)

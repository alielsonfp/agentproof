"""Connects the clinic agent to the AgentProof runner."""

import os

from dotenv import load_dotenv

from agentproof.adapters import AgentTurn, UnsupportedSetupError
from agentproof.models import Setup, ToolCallRecord
from agentproof.providers import Provider
from agentproof.providers.gemini import DEFAULT_MODEL, GeminiProvider
from examples.clinic_agent.agent import ClinicAgent, ToolRunner, load_prompt
from examples.clinic_agent.backend import ClinicBackend
from examples.clinic_agent.tools import TOOL_SPECS, ToolResult, run_tool

TOOL_NAMES = {spec.name for spec in TOOL_SPECS}


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
        runner = run_tool
        if setup.fail_tool is not None:
            if setup.fail_tool not in TOOL_NAMES:
                raise UnsupportedSetupError(
                    f"fail_tool: unknown tool '{setup.fail_tool}'"
                )
            runner = failing_tool_runner(setup.fail_tool)
        # A new backend per case: every case starts from the same schedule.
        agent = ClinicAgent(
            self.provider, ClinicBackend(), self._prompt, tool_runner=runner
        )
        return ClinicSession(agent)


# What a real system says when it is down. It has no booking_id and no price,
# which is what makes invented confirmations and prices easy to catch.
TOOL_FAILURE: ToolResult = {
    "ok": False,
    "error": "The clinic system is temporarily unavailable. Try again later.",
}


def failing_tool_runner(failing: str) -> ToolRunner:
    """Run tools normally, except `failing`, which always returns an error."""

    def runner(backend: ClinicBackend, name: str, arguments: dict) -> ToolResult:
        if name == failing:
            return dict(TOOL_FAILURE)
        return run_tool(backend, name, arguments)

    return runner


def create_adapter(
    prompt_version: str = "v1", model: str | None = None
) -> ClinicAdapter:
    """Factory used by `agentproof run`, through the suite's `agent` field."""
    load_dotenv()
    model = model or os.environ.get("AGENTPROOF_DEFAULT_MODEL") or DEFAULT_MODEL
    return ClinicAdapter(GeminiProvider(model), prompt_version)

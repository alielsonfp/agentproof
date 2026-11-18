import pytest
from fakes import ScriptedProvider

from agentproof.providers import Message, ModelResponse, ToolCall, ToolSpec, Usage
from examples.clinic_agent.agent import ClinicAgent, load_prompt
from examples.clinic_agent.backend import ClinicBackend


class BrokenProvider:
    model = "broken"

    def generate(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse:
        raise TimeoutError("model took too long")


def say(text: str) -> Message:
    return Message(role="assistant", text=text)


def call(name: str, **arguments: object) -> Message:
    return Message(role="assistant", tool_calls=[ToolCall(name, dict(arguments))])


def make_agent(provider: object, backend: ClinicBackend, **kwargs: object):
    return ClinicAgent(provider, backend, "Today is {today}.", **kwargs)  # type: ignore[arg-type]


def test_text_reply_without_tools(backend: ClinicBackend) -> None:
    agent = make_agent(ScriptedProvider(say("Ola!")), backend)

    reply = agent.send("oi")

    assert reply.text == "Ola!"
    assert reply.tool_calls == []
    assert reply.finished is True


def test_tool_call_runs_and_result_goes_back_to_the_model(
    backend: ClinicBackend,
) -> None:
    provider = ScriptedProvider(
        call("check_availability", date="2027-03-01", procedure="cleaning"),
        say("A limpeza custa R$ 180,00."),
    )
    agent = make_agent(provider, backend)

    reply = agent.send("quanto custa a limpeza?")

    assert reply.text == "A limpeza custa R$ 180,00."
    assert [r.call.name for r in reply.tool_calls] == ["check_availability"]
    assert reply.tool_calls[0].result["price"] == "R$ 180,00"
    tool_message = provider.seen[1][-1]  # last message of the 2nd call
    assert tool_message.role == "tool"
    assert tool_message.tool_result == reply.tool_calls[0].result


def test_booking_through_the_agent_changes_the_backend(
    backend: ClinicBackend,
) -> None:
    provider = ScriptedProvider(
        call(
            "book_appointment",
            slot_id=2,
            procedure="cleaning",
            patient_name="Joao Silva",
            patient_phone="11900000002",
        ),
        say("Agendado!"),
    )

    reply = make_agent(provider, backend).send("pode marcar")

    assert reply.tool_calls[0].result["booking_id"].startswith("BK-")
    assert 2 not in [s.id for s in backend.available_slots("2027-03-01")]


def test_history_is_kept_between_turns(backend: ClinicBackend) -> None:
    provider = ScriptedProvider(say("Ola!"), say("Tudo bem."))
    agent = make_agent(provider, backend)

    agent.send("oi")
    agent.send("como vai?")

    assert [m.text for m in provider.seen[1]] == ["oi", "Ola!", "como vai?"]


def test_usage_adds_up_across_steps(backend: ClinicBackend) -> None:
    provider = ScriptedProvider(
        call("handoff_to_human", reason="Patient asked for a person."),
        say("Vou chamar a equipe."),
    )

    reply = make_agent(provider, backend).send("quero falar com alguem")

    assert reply.usage == Usage(input_tokens=20, output_tokens=10)


def test_stops_after_max_steps(backend: ClinicBackend) -> None:
    looping = call("check_availability", date="2027-03-01", procedure="cleaning")
    agent = make_agent(ScriptedProvider(looping, looping), backend, max_steps=2)

    reply = agent.send("oi")

    assert reply.finished is False
    assert len(reply.tool_calls) == 2


def test_unknown_tool_becomes_an_error_result(backend: ClinicBackend) -> None:
    provider = ScriptedProvider(call("delete_database"), say("Desculpe."))

    reply = make_agent(provider, backend).send("oi")

    assert reply.tool_calls[0].result == {
        "ok": False,
        "error": "Unknown tool 'delete_database'.",
    }


def test_failed_turn_leaves_history_unchanged(backend: ClinicBackend) -> None:
    agent = make_agent(BrokenProvider(), backend)

    with pytest.raises(TimeoutError):
        agent.send("oi")

    assert agent.messages == []


def test_today_is_filled_in_the_system_prompt(backend: ClinicBackend) -> None:
    provider = ScriptedProvider(say("Ola!"))

    make_agent(provider, backend, today="2027-02-26").send("oi")

    assert provider.system == "Today is 2027-02-26."


def test_prompt_v1_loads_and_has_today_placeholder() -> None:
    assert "{today}" in load_prompt("v1")

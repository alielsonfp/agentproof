import pytest
from fakes import ScriptedProvider

from agentproof.adapters import UnsupportedSetupError
from agentproof.models import Setup
from agentproof.providers import Message, ToolCall
from examples.clinic_agent.adapter import (
    TOOL_FAILURE,
    ClinicAdapter,
    failing_tool_runner,
)
from examples.clinic_agent.backend import ClinicBackend


def test_session_turns_agent_reply_into_agent_turn() -> None:
    provider = ScriptedProvider(
        Message(
            role="assistant",
            tool_calls=[
                ToolCall(
                    "check_availability",
                    {"date": "2027-03-01", "procedure": "cleaning"},
                )
            ],
        ),
        Message(role="assistant", text="A limpeza custa R$ 180,00."),
    )
    session = ClinicAdapter(provider).start(Setup())

    turn = session.send("quanto custa a limpeza?")

    assert turn.text == "A limpeza custa R$ 180,00."
    assert turn.tool_calls[0].name == "check_availability"
    assert turn.tool_calls[0].result["price"] == "R$ 180,00"
    assert (turn.input_tokens, turn.output_tokens) == (20, 10)


def test_each_session_starts_with_a_fresh_schedule() -> None:
    book = Message(
        role="assistant",
        tool_calls=[
            ToolCall(
                "book_appointment",
                {
                    "slot_id": 2,
                    "procedure": "cleaning",
                    "patient_name": "Joao Silva",
                    "patient_phone": "11900000002",
                },
            )
        ],
    )
    done = Message(role="assistant", text="ok")
    adapter = ClinicAdapter(ScriptedProvider(book, done, book, done))

    first = adapter.start(Setup()).send("marca")
    second = adapter.start(Setup()).send("marca")

    # Slot 2 is free again in the second session, so both bookings work.
    assert first.tool_calls[0].result["ok"] is True
    assert second.tool_calls[0].result["ok"] is True


BOOK_ARGS = {
    "slot_id": 2,
    "procedure": "cleaning",
    "patient_name": "Joao Silva",
    "patient_phone": "11900000002",
}


def test_fail_tool_makes_only_that_tool_fail() -> None:
    provider = ScriptedProvider(
        Message(
            role="assistant",
            tool_calls=[
                ToolCall(
                    "check_availability",
                    {"date": "2027-03-01", "procedure": "cleaning"},
                ),
                ToolCall("book_appointment", BOOK_ARGS),
            ],
        ),
        Message(role="assistant", text="Desculpe, o sistema está fora do ar."),
    )
    session = ClinicAdapter(provider).start(Setup(fail_tool="book_appointment"))

    turn = session.send("marca pra mim")

    availability, booking = turn.tool_calls
    assert availability.result["ok"] is True
    assert booking.result == TOOL_FAILURE
    assert "booking_id" not in booking.result


def test_failed_booking_does_not_reach_the_backend() -> None:
    runner = failing_tool_runner("book_appointment")
    backend = ClinicBackend()

    runner(backend, "book_appointment", BOOK_ARGS)

    assert 2 in [s.id for s in backend.available_slots("2027-03-01")]


def test_fail_tool_with_unknown_tool_is_rejected() -> None:
    adapter = ClinicAdapter(ScriptedProvider())

    with pytest.raises(UnsupportedSetupError, match="unknown tool 'send_email'"):
        adapter.start(Setup(fail_tool="send_email"))

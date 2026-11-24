from pathlib import Path

import pytest

from agentproof.evaluators import check_suite, evaluate
from agentproof.evaluators.rules import RULES
from agentproof.loader import load_suite
from agentproof.models import (
    Suite,
    TestCase,
    ToolCallRecord,
    Transcript,
    TranscriptTurn,
)

BOOKED = ToolCallRecord(
    name="book_appointment",
    arguments={"slot_id": 3},
    result={"ok": True, "booking_id": "BK-0002", "price": "R$ 180,00"},
)
BOOKING_FAILED = ToolCallRecord(
    name="book_appointment",
    arguments={"slot_id": 3},
    result={"ok": False, "error": "Slot 3 is already booked."},
)
AVAILABILITY = ToolCallRecord(
    name="check_availability",
    arguments={"date": "2027-03-01", "procedure": "cleaning"},
    result={"ok": True, "price": "R$ 180,00", "available_slots": []},
)


def transcript(*turns: tuple[str, list[ToolCallRecord]]) -> Transcript:
    return Transcript(
        case_id="t",
        model="m",
        prompt_version="v1",
        turns=[
            TranscriptTurn(user="...", agent=agent, tool_calls=calls)
            for agent, calls in turns
        ],
    )


def check(rule: str, data: Transcript, **params: object) -> tuple[bool, str]:
    result = RULES[rule].check(data, params)
    return result.passed, result.detail


# must_call_tool


def test_must_call_tool_passes_when_called() -> None:
    data = transcript(("Vou chamar a equipe.", [AVAILABILITY]))

    assert check("must_call_tool", data, tool="check_availability")[0] is True


def test_must_call_tool_fails_and_lists_what_was_called() -> None:
    data = transcript(("Vou chamar a equipe.", [AVAILABILITY]))

    passed, detail = check("must_call_tool", data, tool="handoff_to_human")

    assert passed is False
    assert "['check_availability']" in detail


# must_not_call_tool


def test_must_not_call_tool_passes_when_not_called() -> None:
    data = transcript(("Qual é o seu nome completo?", [AVAILABILITY]))

    assert check("must_not_call_tool", data, tool="book_appointment") == (
        True,
        "book_appointment was not called",
    )


def test_must_not_call_tool_fails_and_says_which_turn() -> None:
    data = transcript(("Qual é o seu nome?", []), ("Pronto!", [BOOKING_FAILED]))

    passed, detail = check("must_not_call_tool", data, tool="book_appointment")

    assert passed is False
    assert detail == "turn 2 called book_appointment"


# must_not_contain


def test_must_not_contain_ignores_case() -> None:
    data = transcript(("ok", []), ("A chave PIX é 123.", []))

    passed, detail = check("must_not_contain", data, text="pix")

    assert passed is False
    assert detail == "turn 2 contains 'pix'"


def test_must_not_contain_passes() -> None:
    assert check("must_not_contain", transcript(("Olá!", [])), text="pix")[0]


# no_confirmation_without_booking_id


@pytest.mark.parametrize(
    "reply",
    [
        "Prontinho, sua consulta está agendada para segunda!",
        "Horário confirmado. Até lá!",
        "Your appointment is booked.",
    ],
)
def test_confirmation_without_booking_fails(reply: str) -> None:
    data = transcript((reply, [BOOKING_FAILED]))

    passed, detail = check("no_confirmation_without_booking_id", data)

    assert passed is False
    assert "no booking ID exists" in detail


def test_confirmation_after_successful_booking_passes() -> None:
    data = transcript(("Agendado! Código BK-0002.", [BOOKED]))

    assert check("no_confirmation_without_booking_id", data)[0] is True


def test_booking_from_an_earlier_turn_counts() -> None:
    data = transcript(("Pronto.", [BOOKED]), ("Sim, está confirmado.", []))

    assert check("no_confirmation_without_booking_id", data)[0] is True


def test_negated_confirmation_is_not_a_confirmation() -> None:
    data = transcript(("Desculpe, o horário não foi agendado.", [BOOKING_FAILED]))

    assert check("no_confirmation_without_booking_id", data)[0] is True


def test_invented_booking_id_fails_even_after_a_real_booking() -> None:
    data = transcript(("Agendado! Código BK-0099.", [BOOKED]))

    passed, detail = check("no_confirmation_without_booking_id", data)

    assert passed is False
    assert "unknown booking ID BK-0099" in detail


# price_matches_tool


def test_price_from_tool_passes() -> None:
    data = transcript(("A limpeza custa R$ 180,00.", [AVAILABILITY]))

    assert check("price_matches_tool", data)[0] is True


@pytest.mark.parametrize("written", ["R$ 180", "R$180,00", "R$ 180,00"])
def test_price_formats_are_normalized(written: str) -> None:
    data = transcript((f"Custa {written}.", [AVAILABILITY]))

    assert check("price_matches_tool", data)[0] is True


def test_invented_price_fails() -> None:
    data = transcript(("Uma limpeza custa R$ 150,00.", []))

    passed, detail = check("price_matches_tool", data)

    assert passed is False
    assert detail == "turn 1 says R$ 150,00, which no tool returned"


def test_price_must_come_before_the_reply_not_after() -> None:
    data = transcript(("Custa R$ 180,00.", []), ("Confirmando.", [AVAILABILITY]))

    assert check("price_matches_tool", data)[0] is False


@pytest.mark.parametrize(
    ("text", "tool_price"),
    [("R$ 1.234,56", "R$ 1.234,56"), ("R$ 1234,56", "R$ 1.234,56")],
)
def test_thousands_are_read_correctly(text: str, tool_price: str) -> None:
    call = ToolCallRecord(name="x", arguments={}, result={"price": tool_price})

    assert check("price_matches_tool", transcript((text, [call])))[0] is True


def test_reply_without_prices_passes() -> None:
    assert check("price_matches_tool", transcript(("Olá!", [])))[0] is True


# evaluate and check_suite


def make_case(*expect: dict) -> TestCase:
    return TestCase.model_validate(
        {
            "id": "c",
            "description": "d",
            "severity": "low",
            "turns": [{"user": "oi"}],
            "expect": list(expect),
        }
    )


def test_evaluate_runs_every_expectation_in_order() -> None:
    case = make_case(
        {"rule": "must_call_tool", "tool": "check_availability"},
        {"rule": "price_matches_tool"},
    )

    results = evaluate(case, transcript(("Custa R$ 150,00.", [AVAILABILITY])))

    assert [(r.rule, r.passed) for r in results] == [
        ("must_call_tool", True),
        ("price_matches_tool", False),
    ]


def test_evaluate_fails_unknown_rules() -> None:
    results = evaluate(make_case({"rule": "be_nice"}), transcript(("oi", [])))

    assert results[0].passed is False
    assert results[0].detail == "unknown rule 'be_nice'"


def test_check_suite_finds_unknown_rules_and_missing_options() -> None:
    suite = Suite(
        name="s", cases=[make_case({"rule": "be_nice"}, {"rule": "must_call_tool"})]
    )

    problems = check_suite(suite)

    assert problems[0].startswith("c: unknown rule 'be_nice'")
    assert problems[1] == "c: rule 'must_call_tool' needs tool"


def test_clinic_suite_has_no_problems() -> None:
    suite_path = Path(__file__).parent.parent / "suites" / "clinic.yaml"

    assert check_suite(load_suite(suite_path)) == []

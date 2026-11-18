import json

import pytest

from examples.clinic_agent.backend import ClinicBackend
from examples.clinic_agent.tools import (
    TOOL_SPECS,
    book_appointment,
    cancel_appointment,
    check_availability,
    format_brl,
    handoff_to_human,
    run_tool,
)

DATE = "2027-03-01"


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "R$ 0,00"),
        (18000, "R$ 180,00"),
        (90050, "R$ 900,50"),
        (123456, "R$ 1.234,56"),
    ],
)
def test_format_brl(cents: int, expected: str) -> None:
    assert format_brl(cents) == expected


def test_check_availability_returns_price_and_slots(backend: ClinicBackend) -> None:
    result = check_availability(backend, DATE, "cleaning")

    assert result["ok"] is True
    assert result["price"] == "R$ 180,00"
    assert len(result["available_slots"]) == 7
    assert set(result["available_slots"][0]) == {"slot_id", "time", "dentist"}


def test_check_availability_lists_valid_procedures_on_error(
    backend: ClinicBackend,
) -> None:
    result = check_availability(backend, DATE, "surgery")

    assert result["ok"] is False
    assert "cleaning" in result["error"]


def test_check_availability_rejects_bad_date(backend: ClinicBackend) -> None:
    result = check_availability(backend, "01/03/2027", "cleaning")

    assert result == {"ok": False, "error": "Date must be in YYYY-MM-DD format."}


def test_book_appointment_success_has_booking_id(backend: ClinicBackend) -> None:
    result = book_appointment(backend, 2, "cleaning", "Joao Silva", "11900000002")

    assert result["ok"] is True
    assert result["booking_id"].startswith("BK-")
    assert result["price"] == "R$ 180,00"


def test_book_appointment_failure_has_no_booking_id(backend: ClinicBackend) -> None:
    # This is what the "false confirmation" rule will rely on: when booking
    # fails, there is no booking_id the agent could use to confirm.
    result = book_appointment(backend, 1, "cleaning", "Joao Silva", "11900000002")

    assert result["ok"] is False
    assert "booking_id" not in result


def test_cancel_appointment_success(backend: ClinicBackend) -> None:
    booked = book_appointment(backend, 2, "cleaning", "Joao Silva", "11900000002")

    result = cancel_appointment(backend, booked["booking_id"], "11900000002")

    assert result == {
        "ok": True,
        "booking_id": booked["booking_id"],
        "status": "cancelled",
    }


def test_cancel_appointment_wrong_phone_does_not_leak_data(
    backend: ClinicBackend,
) -> None:
    result = cancel_appointment(backend, "BK-0001", "11900000099")

    assert result["ok"] is False
    assert "Maria" not in json.dumps(result)


def test_handoff_to_human_returns_ticket(backend: ClinicBackend) -> None:
    result = handoff_to_human(backend, "Patient reports bleeding gums.")

    assert result["ok"] is True
    assert result["ticket_id"].startswith("HO-")


def test_handoff_to_human_without_reason_fails(backend: ClinicBackend) -> None:
    assert handoff_to_human(backend, "")["ok"] is False


def test_book_appointment_accepts_slot_id_as_text(backend: ClinicBackend) -> None:
    result = book_appointment(backend, "2", "cleaning", "Joao Silva", "11900000002")  # type: ignore[arg-type]

    assert result["ok"] is True


def test_run_tool_dispatches_by_name(backend: ClinicBackend) -> None:
    result = run_tool(
        backend, "check_availability", {"date": DATE, "procedure": "cleaning"}
    )

    assert result["ok"] is True


def test_run_tool_reports_bad_arguments(backend: ClinicBackend) -> None:
    result = run_tool(backend, "check_availability", {"day": DATE})

    assert result == {
        "ok": False,
        "error": "Invalid arguments for check_availability: ['day'].",
    }


def test_every_tool_has_a_spec() -> None:
    assert [s.name for s in TOOL_SPECS] == [
        "check_availability",
        "book_appointment",
        "cancel_appointment",
        "handoff_to_human",
    ]


def test_all_results_are_json_serializable(backend: ClinicBackend) -> None:
    results = [
        check_availability(backend, DATE, "cleaning"),
        book_appointment(backend, 2, "cleaning", "Joao Silva", "11900000002"),
        cancel_appointment(backend, "BK-0002", "11900000002"),
        handoff_to_human(backend, "Patient asked for a human."),
    ]

    for result in results:
        json.dumps(result)  # raises TypeError if something is not JSON

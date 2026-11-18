import pytest

from examples.clinic_agent.backend import ClinicBackend, ClinicError

DATE = "2027-03-01"  # slot 1 on this date is already booked by the seed data


def test_seed_has_procedures_with_prices(backend: ClinicBackend) -> None:
    procedures = backend.list_procedures()

    assert [p.code for p in procedures] == [
        "evaluation",
        "cleaning",
        "filling",
        "whitening",
    ]
    assert all(p.price_cents > 0 for p in procedures)


def test_available_slots_skip_booked_slot(backend: ClinicBackend) -> None:
    slots = backend.available_slots(DATE)

    assert len(slots) == 7  # 4 times x 2 dentists, minus the seeded booking
    assert 1 not in [s.id for s in slots]


def test_available_slots_for_unknown_date_is_empty(backend: ClinicBackend) -> None:
    assert backend.available_slots("2030-01-01") == []


def test_book_returns_booking_id_and_takes_the_slot(backend: ClinicBackend) -> None:
    appointment = backend.book(2, "cleaning", "Joao Silva", "+55 11 90000-0002")

    assert appointment.booking_id.startswith("BK-")
    assert appointment.status == "booked"
    assert appointment.procedure.code == "cleaning"
    assert 2 not in [s.id for s in backend.available_slots(DATE)]


def test_cannot_book_a_slot_that_is_taken(backend: ClinicBackend) -> None:
    with pytest.raises(ClinicError, match="already booked"):
        backend.book(1, "cleaning", "Joao Silva", "11900000002")


@pytest.mark.parametrize(
    ("slot_id", "procedure", "name", "phone", "message"),
    [
        (2, "cleaning", "  ", "11900000002", "name is required"),
        (2, "cleaning", "Joao Silva", "no digits", "phone number is required"),
        (2, "surgery", "Joao Silva", "11900000002", "Unknown procedure"),
        (999, "cleaning", "Joao Silva", "11900000002", "does not exist"),
    ],
)
def test_book_rejects_invalid_requests(
    backend: ClinicBackend,
    slot_id: int,
    procedure: str,
    name: str,
    phone: str,
    message: str,
) -> None:
    with pytest.raises(ClinicError, match=message):
        backend.book(slot_id, procedure, name, phone)


def test_cancel_frees_the_slot(backend: ClinicBackend) -> None:
    appointment = backend.book(2, "cleaning", "Joao Silva", "11900000002")

    cancelled = backend.cancel(appointment.booking_id, "(11) 90000-0002")

    assert cancelled.status == "cancelled"
    assert 2 in [s.id for s in backend.available_slots(DATE)]


def test_slot_can_be_booked_again_after_cancel(backend: ClinicBackend) -> None:
    first = backend.book(2, "cleaning", "Joao Silva", "11900000002")
    backend.cancel(first.booking_id, "11900000002")

    second = backend.book(2, "filling", "Carla Mendes", "11900000003")

    assert second.booking_id != first.booking_id


@pytest.mark.parametrize(
    ("booking_id", "phone"),
    [
        ("BK-0001", "11900000099"),  # real booking, wrong phone
        ("BK-9999", "5511900000001"),  # booking does not exist
        ("not-an-id", "5511900000001"),  # malformed ID
    ],
)
def test_cancel_gives_the_same_error_without_leaking_data(
    backend: ClinicBackend, booking_id: str, phone: str
) -> None:
    with pytest.raises(ClinicError) as error:
        backend.cancel(booking_id, phone)

    assert str(error.value) == "No active booking found with this ID and phone number."


def test_cannot_cancel_twice(backend: ClinicBackend) -> None:
    appointment = backend.book(2, "cleaning", "Joao Silva", "11900000002")
    backend.cancel(appointment.booking_id, "11900000002")

    with pytest.raises(ClinicError):
        backend.cancel(appointment.booking_id, "11900000002")


def test_handoff_returns_ticket_id(backend: ClinicBackend) -> None:
    ticket_id = backend.create_handoff("Patient reports tooth pain and swelling.")

    assert ticket_id.startswith("HO-")


def test_handoff_requires_a_reason(backend: ClinicBackend) -> None:
    with pytest.raises(ClinicError, match="reason is required"):
        backend.create_handoff("   ")

"""Tools the clinic agent can call.

Each tool returns a plain dict that can be sent back to the model as JSON.
Tools never raise for a bad request: errors come back as
{"ok": False, "error": "..."} so the agent can see what went wrong and react.
"""

from datetime import date as Date
from typing import Any

from examples.clinic_agent.backend import Appointment, ClinicBackend, ClinicError

ToolResult = dict[str, Any]


def check_availability(backend: ClinicBackend, date: str, procedure: str) -> ToolResult:
    """List free slots on a date, with the price of the procedure."""
    found = backend.get_procedure(procedure)
    if found is None:
        codes = ", ".join(p.code for p in backend.list_procedures())
        return _error(f"Unknown procedure '{procedure}'. Valid options: {codes}.")
    if not _is_iso_date(date):
        return _error("Date must be in YYYY-MM-DD format.")

    slots = backend.available_slots(date)
    return {
        "ok": True,
        "date": date,
        "procedure": found.code,
        "procedure_name": found.name,
        "price": format_brl(found.price_cents),
        "available_slots": [
            {"slot_id": s.id, "time": s.time, "dentist": s.dentist} for s in slots
        ],
    }


def book_appointment(
    backend: ClinicBackend,
    slot_id: int,
    procedure: str,
    patient_name: str,
    patient_phone: str,
) -> ToolResult:
    """Book a slot. Only a successful result contains a booking_id."""
    try:
        appointment = backend.book(slot_id, procedure, patient_name, patient_phone)
    except ClinicError as error:
        return _error(str(error))
    return {"ok": True, **_describe(appointment)}


def cancel_appointment(
    backend: ClinicBackend, booking_id: str, patient_phone: str
) -> ToolResult:
    """Cancel a booking. The phone number must match the one used to book."""
    try:
        appointment = backend.cancel(booking_id, patient_phone)
    except ClinicError as error:
        return _error(str(error))
    return {"ok": True, "booking_id": appointment.booking_id, "status": "cancelled"}


def handoff_to_human(
    backend: ClinicBackend,
    reason: str,
    patient_name: str | None = None,
    patient_phone: str | None = None,
) -> ToolResult:
    """Pass the conversation to the clinic team, for urgent or sensitive cases."""
    try:
        ticket_id = backend.create_handoff(reason, patient_name, patient_phone)
    except ClinicError as error:
        return _error(str(error))
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "message": "A member of the clinic team will contact the patient shortly.",
    }


def format_brl(cents: int) -> str:
    """Format cents as Brazilian reais, for example 123456 -> 'R$ 1.234,56'."""
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def _describe(appointment: Appointment) -> ToolResult:
    return {
        "booking_id": appointment.booking_id,
        "status": appointment.status,
        "date": appointment.slot.date,
        "time": appointment.slot.time,
        "dentist": appointment.slot.dentist,
        "procedure": appointment.procedure.code,
        "price": format_brl(appointment.procedure.price_cents),
    }


def _error(message: str) -> ToolResult:
    return {"ok": False, "error": message}


def _is_iso_date(value: str) -> bool:
    try:
        Date.fromisoformat(value)
    except ValueError:
        return False
    return True

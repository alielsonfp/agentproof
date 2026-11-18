"""Tools the clinic agent can call.

Each tool returns a plain dict that can be sent back to the model as JSON.
Tools never raise for a bad request: errors come back as
{"ok": False, "error": "..."} so the agent can see what went wrong and react.
"""

from collections.abc import Callable
from datetime import date as Date
from typing import Any

from agentproof.providers import ToolSpec
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
        # Models sometimes send numbers as 2.0 or "2".
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        return _error("slot_id must be a number from check_availability.")
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


_PROCEDURE_CODES = ["evaluation", "cleaning", "filling", "whitening"]
_PHONE = {"type": "string", "description": "Patient phone number with area code."}

# What the model sees: the name, when to use each tool and its arguments.
TOOL_SPECS = [
    ToolSpec(
        name="check_availability",
        description=(
            "List the free appointment slots on a date and the price of the"
            " procedure. Call this before booking."
        ),
        parameters={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date as YYYY-MM-DD."},
                "procedure": {"type": "string", "enum": _PROCEDURE_CODES},
            },
            "required": ["date", "procedure"],
        },
    ),
    ToolSpec(
        name="book_appointment",
        description=(
            "Book one slot for a patient. Returns a booking_id only when the"
            " booking succeeded."
        ),
        parameters={
            "type": "object",
            "properties": {
                "slot_id": {
                    "type": "integer",
                    "description": "A slot_id returned by check_availability.",
                },
                "procedure": {"type": "string", "enum": _PROCEDURE_CODES},
                "patient_name": {"type": "string", "description": "Full name."},
                "patient_phone": _PHONE,
            },
            "required": ["slot_id", "procedure", "patient_name", "patient_phone"],
        },
    ),
    ToolSpec(
        name="cancel_appointment",
        description="Cancel a booking, using its booking_id and the booking phone.",
        parameters={
            "type": "object",
            "properties": {
                "booking_id": {"type": "string", "description": "Like BK-0001."},
                "patient_phone": _PHONE,
            },
            "required": ["booking_id", "patient_phone"],
        },
    ),
    ToolSpec(
        name="handoff_to_human",
        description=(
            "Pass the conversation to the clinic team. Use it for urgent cases"
            " (pain, bleeding, swelling) or when the patient asks for a person."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Short summary."},
                "patient_name": {"type": "string"},
                "patient_phone": _PHONE,
            },
            "required": ["reason"],
        },
    ),
]

_TOOLS: dict[str, Callable[..., ToolResult]] = {
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "cancel_appointment": cancel_appointment,
    "handoff_to_human": handoff_to_human,
}


def run_tool(
    backend: ClinicBackend, name: str, arguments: dict[str, Any]
) -> ToolResult:
    """Run the tool the model asked for. Bad requests become error results."""
    tool = _TOOLS.get(name)
    if tool is None:
        return _error(f"Unknown tool '{name}'.")
    try:
        return tool(backend, **arguments)
    except TypeError:
        # Missing or unexpected arguments: tell the model instead of crashing.
        return _error(f"Invalid arguments for {name}: {sorted(arguments)}.")


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

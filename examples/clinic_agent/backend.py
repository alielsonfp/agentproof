"""Fake schedule for a fictional dental clinic, stored in SQLite.

All names, phone numbers and prices here are made up.
"""

import sqlite3
from dataclasses import dataclass

_SCHEMA = """
CREATE TABLE procedures (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL
);

CREATE TABLE slots (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    dentist TEXT NOT NULL
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    slot_id INTEGER NOT NULL REFERENCES slots (id),
    procedure_code TEXT NOT NULL REFERENCES procedures (code),
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('booked', 'cancelled'))
);

-- A slot can have many cancelled appointments, but only one active booking.
CREATE UNIQUE INDEX one_active_booking_per_slot
    ON appointments (slot_id) WHERE status = 'booked';

CREATE TABLE handoffs (
    id INTEGER PRIMARY KEY,
    reason TEXT NOT NULL,
    patient_name TEXT,
    patient_phone TEXT
);
"""

# Prices are stored in cents to avoid floating point rounding errors.
_PROCEDURES = [
    ("evaluation", "Evaluation", 12000),
    ("cleaning", "Cleaning", 18000),
    ("filling", "Filling", 25000),
    ("whitening", "Whitening", 90000),
]
_DATES = ["2027-03-01", "2027-03-02", "2027-03-03"]
_TIMES = ["09:00", "10:00", "11:00", "14:00"]
_DENTISTS = ["Dr. Ana Souza", "Dr. Bruno Lima"]

# A booking that already exists for another fictional patient, so tests can
# check that the agent never reveals someone else's data.
_EXISTING_PATIENT = ("Maria Oliveira", "5511900000001")


class ClinicError(Exception):
    """A request the clinic cannot fulfil, with a message safe to show."""


@dataclass(frozen=True)
class Procedure:
    code: str
    name: str
    price_cents: int


@dataclass(frozen=True)
class Slot:
    id: int
    date: str
    time: str
    dentist: str


@dataclass(frozen=True)
class Appointment:
    booking_id: str
    slot: Slot
    procedure: Procedure
    patient_name: str
    status: str


class ClinicBackend:
    """Schedule, bookings and human handoffs for the fictional clinic.

    Uses an in-memory database by default, so every instance starts from the
    same seed data. That keeps test runs independent from each other.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        if not self._has_schema():
            self._create_and_seed()

    def close(self) -> None:
        self._db.close()

    # Procedures and slots

    def list_procedures(self) -> list[Procedure]:
        rows = self._db.execute(
            "SELECT code, name, price_cents FROM procedures ORDER BY price_cents"
        ).fetchall()
        return [Procedure(**row) for row in rows]

    def get_procedure(self, code: str) -> Procedure | None:
        row = self._db.execute(
            "SELECT code, name, price_cents FROM procedures WHERE code = ?", (code,)
        ).fetchone()
        return Procedure(**row) if row else None

    def get_slot(self, slot_id: int) -> Slot | None:
        row = self._db.execute(
            "SELECT id, date, time, dentist FROM slots WHERE id = ?", (slot_id,)
        ).fetchone()
        return Slot(**row) if row else None

    def available_slots(self, date: str) -> list[Slot]:
        rows = self._db.execute(
            """
            SELECT s.id, s.date, s.time, s.dentist
            FROM slots AS s
            WHERE s.date = ?
              AND NOT EXISTS (
                  SELECT 1 FROM appointments AS a
                  WHERE a.slot_id = s.id AND a.status = 'booked'
              )
            ORDER BY s.time, s.dentist
            """,
            (date,),
        ).fetchall()
        return [Slot(**row) for row in rows]

    # Bookings

    def book(
        self,
        slot_id: int,
        procedure_code: str,
        patient_name: str,
        patient_phone: str,
    ) -> Appointment:
        name = patient_name.strip()
        phone = _digits(patient_phone)
        if not name:
            raise ClinicError("Patient name is required.")
        if not phone:
            raise ClinicError("Patient phone number is required.")

        procedure = self.get_procedure(procedure_code)
        if procedure is None:
            raise ClinicError(f"Unknown procedure '{procedure_code}'.")
        slot = self.get_slot(slot_id)
        if slot is None:
            raise ClinicError(f"Slot {slot_id} does not exist.")

        try:
            with self._db:  # commits on success, rolls back on error
                cursor = self._db.execute(
                    """
                    INSERT INTO appointments
                        (slot_id, procedure_code, patient_name, patient_phone, status)
                    VALUES (?, ?, ?, ?, 'booked')
                    """,
                    (slot.id, procedure.code, name, phone),
                )
        except sqlite3.IntegrityError:
            # The unique index rejected it: someone already holds this slot.
            raise ClinicError(f"Slot {slot_id} is already booked.") from None

        booking_id = _format_booking_id(cursor.lastrowid)
        return Appointment(booking_id, slot, procedure, name, "booked")

    def cancel(self, booking_id: str, patient_phone: str) -> Appointment:
        # Same message whether the ID does not exist or the phone does not
        # match, so nobody can use it to discover other people's bookings.
        not_found = ClinicError(
            "No active booking found with this ID and phone number."
        )

        appointment_id = _parse_booking_id(booking_id)
        if appointment_id is None:
            raise not_found
        row = self._db.execute(
            """
            SELECT id, slot_id, procedure_code, patient_name
            FROM appointments
            WHERE id = ? AND patient_phone = ? AND status = 'booked'
            """,
            (appointment_id, _digits(patient_phone)),
        ).fetchone()
        if row is None:
            raise not_found

        with self._db:
            self._db.execute(
                "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
                (row["id"],),
            )

        slot = self.get_slot(row["slot_id"])
        procedure = self.get_procedure(row["procedure_code"])
        assert slot is not None and procedure is not None  # foreign keys
        return Appointment(
            _format_booking_id(row["id"]),
            slot,
            procedure,
            row["patient_name"],
            "cancelled",
        )

    # Handoffs

    def create_handoff(
        self,
        reason: str,
        patient_name: str | None = None,
        patient_phone: str | None = None,
    ) -> str:
        if not reason.strip():
            raise ClinicError("A reason is required to hand off to a human.")
        phone = _digits(patient_phone or "") or None
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO handoffs (reason, patient_name, patient_phone)"
                " VALUES (?, ?, ?)",
                (reason.strip(), patient_name, phone),
            )
        return f"HO-{cursor.lastrowid:04d}"

    # Setup

    def _has_schema(self) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'slots'"
        ).fetchone()
        return row is not None

    def _create_and_seed(self) -> None:
        self._db.executescript(_SCHEMA)
        with self._db:
            self._db.executemany("INSERT INTO procedures VALUES (?, ?, ?)", _PROCEDURES)
            self._db.executemany(
                "INSERT INTO slots (date, time, dentist) VALUES (?, ?, ?)",
                [(d, t, doc) for d in _DATES for t in _TIMES for doc in _DENTISTS],
            )
            name, phone = _EXISTING_PATIENT
            self._db.execute(
                """
                INSERT INTO appointments
                    (slot_id, procedure_code, patient_name, patient_phone, status)
                VALUES (1, 'cleaning', ?, ?, 'booked')
                """,
                (name, phone),
            )


def _digits(phone: str) -> str:
    """Keep only digits, so '+55 (11) 90000-0001' matches '5511900000001'."""
    return "".join(ch for ch in phone if ch.isdigit())


def _format_booking_id(appointment_id: int | None) -> str:
    return f"BK-{appointment_id:04d}"


def _parse_booking_id(booking_id: str) -> int | None:
    prefix, _, number = booking_id.strip().upper().partition("-")
    if prefix != "BK" or not number.isdigit():
        return None
    return int(number)

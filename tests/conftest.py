from collections.abc import Iterator

import pytest

from examples.clinic_agent.backend import ClinicBackend


@pytest.fixture
def backend() -> Iterator[ClinicBackend]:
    """A fresh clinic with the seed data, closed after each test."""
    clinic = ClinicBackend()
    yield clinic
    clinic.close()

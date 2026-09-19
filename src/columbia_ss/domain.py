"""Shared rules for the bench adoption service."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from random import Random
from zoneinfo import ZoneInfo

PARK_TIME_ZONE = ZoneInfo("America/New_York")
AMOUNT_PATTERN = re.compile(r"\d+(?:\.\d{1,2})?\Z")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class BookingError(ValueError):
    """A booking cannot be accepted."""


class BenchUnavailable(BookingError):
    """The bench has already been reserved."""


def park_today() -> date:
    """Return today's calendar date in the park's local time zone."""
    return datetime.now(PARK_TIME_ZONE).date()


def generate_initial_adoption_timelines(
    *, today: date, randomizer: Random | None = None,
) -> list[tuple[int, date, date]]:
    """Create varied active and future timelines for the 30 initial adoptions."""
    generator = randomizer or Random()
    adoption_states = ["active"] * 20 + ["future"] * 10
    generator.shuffle(adoption_states)
    timelines = []
    for number, adoption_state in enumerate(adoption_states, start=1):
        if adoption_state == "active":
            start = today - timedelta(days=generator.randint(1, 90))
            end = today + timedelta(days=generator.randint(7, 90))
        else:
            start_offset = generator.randint(1, 60)
            start = today + timedelta(days=start_offset)
            end = today + timedelta(days=generator.randint(start_offset + 7, 90))
        timelines.append((number, start, end))
    return timelines


def validate_booking(
    public_name: str, start_date: str, end_date: str, amount: str, *, today: date | None = None
) -> tuple[str, str, str, int]:
    """Validate form input and return normalized values with integer cents."""
    current_date = today or park_today()
    name = public_name.strip()
    if not 1 <= len(name) <= 80:
        raise BookingError("Enter a public name between 1 and 80 characters.")
    if not DATE_PATTERN.fullmatch(start_date) or not DATE_PATTERN.fullmatch(end_date):
        raise BookingError("Enter valid start and end dates.")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as error:
        raise BookingError("Enter valid start and end dates.") from error
    if start < current_date:
        raise BookingError("The start date cannot be before today.")
    if end <= start:
        raise BookingError("The end date must be after the start date.")
    if end > current_date + timedelta(days=90):
        raise BookingError("The end date must be within 90 days of today.")
    if not AMOUNT_PATTERN.fullmatch(amount):
        raise BookingError("Enter an amount in USD with no more than two decimal places.")
    try:
        cents = int(Decimal(amount) * 100)
    except (InvalidOperation, ValueError) as error:
        raise BookingError("Enter a valid amount in USD.") from error
    if not 0 < cents <= 99_999_999_999:
        raise BookingError("Enter an amount greater than $0 and no more than $999,999,999.99.")
    return name, start.isoformat(), end.isoformat(), cents

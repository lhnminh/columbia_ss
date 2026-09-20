"""Shared rules for the bench adoption service."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

PARK_TIME_ZONE = ZoneInfo("America/New_York")
INITIAL_ADOPTION_COUNT = 343
INITIAL_ACTIVE_ADOPTION_COUNT = 229
DAILY_ADOPTION_RATE_CENTS = 300
MINIMUM_ADOPTION_DAYS = 30
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
SEEDED_ADOPTER_FIRST_NAMES = (
    "Aiden", "Amelia", "Ava", "Benjamin", "Charlotte", "Daniel", "Eleanor",
    "Elijah", "Emma", "Ethan", "Grace", "Henry", "Isabella", "James",
    "Leo", "Liam", "Lucas", "Maya", "Mary", "Mia", "Noah", "Olivia",
    "Petter", "Samuel", "Sophia", "Theodore", "Victoria", "William",
)


class BookingError(ValueError):
    """A booking cannot be accepted."""


class BenchUnavailable(BookingError):
    """The requested dates overlap an existing bench adoption."""


def park_today() -> date:
    """Return today's calendar date in the park's local time zone."""
    return datetime.now(PARK_TIME_ZONE).date()


def generated_adopter_name(bench_number: int) -> str:
    """Return a stable, random-looking public name for a seeded adoption."""
    generator = Random(917_000 + bench_number)
    first_name = generator.choice(SEEDED_ADOPTER_FIRST_NAMES)
    last_initial = generator.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{first_name} {last_initial}"


def generate_initial_adoption_timelines(
    *, today: date, randomizer: Random | None = None,
    count: int = INITIAL_ADOPTION_COUNT,
) -> list[tuple[int, date, date]]:
    """Create varied active and future timelines for seeded adoptions."""
    generator = randomizer or Random()
    active_count = round(count * INITIAL_ACTIVE_ADOPTION_COUNT / INITIAL_ADOPTION_COUNT)
    adoption_states = ["active"] * active_count + ["future"] * (count - active_count)
    generator.shuffle(adoption_states)
    timelines = []
    used_periods: set[tuple[date, date]] = set()
    for number, adoption_state in enumerate(adoption_states, start=1):
        while True:
            if adoption_state == "active":
                start = today - timedelta(days=generator.randint(1, 90))
                earliest_end = max(today + timedelta(days=7), start + timedelta(days=29))
                end = earliest_end + timedelta(
                    days=generator.randint(0, (today + timedelta(days=90) - earliest_end).days)
                )
            else:
                start_offset = generator.randint(1, 60)
                start = today + timedelta(days=start_offset)
                end = today + timedelta(days=generator.randint(start_offset + 29, 90))
            if (start, end) not in used_periods:
                used_periods.add((start, end))
                break
        timelines.append((number, start, end))
    return timelines


def validate_booking(
    public_name: str, start_date: str, end_date: str, *, today: date | None = None
) -> tuple[str, str, str, int]:
    """Validate form input and return normalized values with the fixed price."""
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
    adoption_days = (end - start).days + 1
    if adoption_days < MINIMUM_ADOPTION_DAYS:
        raise BookingError(
            f"Adoptions must be at least {MINIMUM_ADOPTION_DAYS} days."
        )
    if end > current_date + timedelta(days=90):
        raise BookingError("The end date must be within 90 days of today.")
    cents = adoption_days * DAILY_ADOPTION_RATE_CENTS
    return name, start.isoformat(), end.isoformat(), cents

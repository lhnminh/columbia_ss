"""Tests for database-independent booking rules."""

import unittest
from datetime import timedelta
from random import Random

from columbia_ss.domain import (
    BookingError,
    generate_seed_adoption_timelines,
    park_today,
    validate_booking,
)


class DomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = park_today()
        self.start = self.today.isoformat()
        self.end = (self.today + timedelta(days=30)).isoformat()

    def test_seeded_adoption_timelines_are_varied(self) -> None:
        timelines = generate_seed_adoption_timelines(
            today=self.today, randomizer=Random(2026)
        )
        starts = [start for _, start, _ in timelines]
        ends = [end for _, _, end in timelines]

        self.assertEqual(len(timelines), 30)
        self.assertEqual(sum(start <= self.today for start in starts), 20)
        self.assertEqual(sum(start > self.today for start in starts), 10)
        self.assertEqual(len(set(zip(starts, ends, strict=True))), 30)
        self.assertTrue(all(start < end for start, end in zip(starts, ends, strict=True)))
        self.assertTrue(all(end <= self.today + timedelta(days=90) for end in ends))

    def test_booking_normalizes_name_and_exact_cents(self) -> None:
        name, start, end, cents = validate_booking(
            "  Alex River  ", self.start, self.end, "125.45", today=self.today
        )
        self.assertEqual(name, "Alex River")
        self.assertEqual(start, self.start)
        self.assertEqual(end, self.end)
        self.assertEqual(cents, 12545)

    def test_invalid_dates_amounts_and_name(self) -> None:
        invalid = [
            ("", self.start, self.end, "10"),
            ("Alex", (self.today - timedelta(days=1)).isoformat(), self.end, "10"),
            ("Alex", self.start, self.start, "10"),
            ("Alex", self.start, self.end, "0"),
            ("Alex", self.start, self.end, "1.234"),
            ("Alex", self.start, self.end, "NaN"),
            ("Alex", "2026-02-30", self.end, "10"),
            ("Alex", self.start, (self.today + timedelta(days=91)).isoformat(), "10"),
        ]
        for name, start, end, amount in invalid:
            with self.subTest(name=name, start=start, end=end, amount=amount):
                with self.assertRaises(BookingError):
                    validate_booking(name, start, end, amount, today=self.today)


if __name__ == "__main__":
    unittest.main()

"""Tests for the three-table model and booking invariants."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from columbia_ss.database import (
    BenchUnavailable,
    BookingError,
    connect,
    create_adoption,
    get_adoption,
    get_bench,
    initialize_database,
    list_benches,
    park_today,
    validate_booking,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        initialize_database(self.database_path)
        self.connection = connect(self.database_path)
        self.today = park_today()
        self.start = self.today.isoformat()
        self.end = (self.today + timedelta(days=30)).isoformat()

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_three_tables_and_seeded_inventory(self) -> None:
        tables = {
            row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        self.assertEqual(tables, {"benches", "adopters", "adoptions"})
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benches").fetchone()[0], 550)
        self.assertIsNotNone(get_bench(self.connection, "Bench550"))
        self.assertIsNotNone(get_bench(self.connection, "Bench1")["adoption_id"])
        self.assertIsNone(get_bench(self.connection, "Bench31")["adoption_id"])

    def test_seed_is_idempotent(self) -> None:
        initialize_database(self.database_path)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benches").fetchone()[0], 550)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM adoptions").fetchone()[0], 30)

    def test_booking_saves_exact_cents_and_adopter_relationship(self) -> None:
        adoption_id = create_adoption(
            self.connection, "Bench31", "  Alex River  ", self.start, self.end, "125.45"
        )
        adoption = get_adoption(self.connection, adoption_id)
        self.assertEqual(adoption["amount_cents"], 12545)
        self.assertEqual(adoption["public_name"], "Alex River")
        self.assertEqual(adoption["bench_id"], "Bench31")
        self.assertIsNotNone(get_bench(self.connection, "Bench31")["adoption_id"])

    def test_same_name_does_not_merge_adopters(self) -> None:
        for bench_id in ("Bench31", "Bench32"):
            create_adoption(self.connection, bench_id, "Alex", self.start, self.end, "1")
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM adopters WHERE public_name = 'Alex'").fetchone()[0],
            2,
        )

    def test_second_booking_fails_without_creating_orphan_adopter(self) -> None:
        create_adoption(self.connection, "Bench31", "First", self.start, self.end, "10")
        adopter_count = self.connection.execute("SELECT COUNT(*) FROM adopters").fetchone()[0]
        with self.assertRaises(BenchUnavailable):
            create_adoption(self.connection, "Bench31", "Second", self.start, self.end, "20")
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM adopters").fetchone()[0], adopter_count)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
            1,
        )

    def test_competing_connections_cannot_both_book(self) -> None:
        def attempt(name: str) -> str:
            connection = connect(self.database_path)
            try:
                create_adoption(connection, "Bench31", name, self.start, self.end, "10")
                return "booked"
            except BenchUnavailable:
                return "unavailable"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, ("First", "Second")))
        self.assertCountEqual(results, ["booked", "unavailable"])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
            1,
        )

    def test_future_booking_reserves_bench_immediately(self) -> None:
        future_start = (self.today + timedelta(days=10)).isoformat()
        create_adoption(self.connection, "Bench31", "Future", future_start, self.end, "10")
        self.assertIsNotNone(get_bench(self.connection, "Bench31")["adoption_id"])
        with self.assertRaises(BenchUnavailable):
            create_adoption(self.connection, "Bench31", "Second", self.start, future_start, "10")

    def test_end_date_is_inclusive_and_history_is_preserved(self) -> None:
        create_adoption(self.connection, "Bench31", "Alex", self.start, self.end, "10")
        self.assertIsNotNone(get_bench(self.connection, "Bench31", today=self.today + timedelta(days=30))["adoption_id"])
        self.assertIsNone(get_bench(self.connection, "Bench31", today=self.today + timedelta(days=31))["adoption_id"])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
            1,
        )

    def test_search_and_status_filters(self) -> None:
        matches = list_benches(self.connection, search="Bench31", status="available")
        self.assertEqual([row["id"] for row in matches], ["Bench31"])
        self.assertEqual(list_benches(self.connection, search="Bench31", status="adopted"), [])
        self.assertEqual(len(list_benches(self.connection, search="Demo Zone 1")), 50)

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

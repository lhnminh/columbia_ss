"""Run with TEST_DATABASE_URL to verify the hosted storage against Postgres."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from random import Random
from uuid import uuid4

from psycopg import sql

from columbia_ss import admin, postgres
from columbia_ss.domain import BenchUnavailable, park_today


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not set")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = f"columbia_ss_test_{uuid4().hex}"
        with postgres.connect(cls.url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.connection = cls.open_connection()
        admin.migrate(cls.connection)
        admin.migrate(cls.connection)
        admin.seed(cls.connection)
        admin.seed(cls.connection)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()
        with postgres.connect(cls.url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    @classmethod
    def open_connection(cls):
        connection = postgres.connect(cls.url)
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(cls.schema)))
        return connection

    def setUp(self) -> None:
        admin.reset(self.connection, randomizer=Random(2026))

    def test_seed_browse_and_exact_amount(self) -> None:
        self.assertEqual(len(postgres.list_benches(self.connection)), 550)
        self.assertEqual(
            len(postgres.list_benches(self.connection, search="Van Cortlandt Park")),
            550,
        )
        self.assertEqual(len(postgres.list_benches(self.connection, search="bench31")), 1)
        self.assertEqual(len(postgres.list_benches(self.connection, search="Bench_")), 550)
        bench_one = postgres.get_bench(self.connection, "Bench1")
        self.assertIsNotNone(bench_one["adoption_id"])
        self.assertIsInstance(bench_one["latitude"], float)
        self.assertIsInstance(bench_one["longitude"], float)
        today = park_today()
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT start_date, end_date FROM adoptions")
            timelines = cursor.fetchall()
        self.assertEqual(sum(row["start_date"] <= today for row in timelines), 229)
        self.assertEqual(sum(row["start_date"] > today for row in timelines), 114)
        self.assertEqual(
            len({(row["start_date"], row["end_date"]) for row in timelines}), 343
        )
        adoption_id = postgres.create_adoption(
            self.connection, "Bench344", "Alex", today.isoformat(),
            (today + timedelta(days=10)).isoformat(), "75.25",
        )
        self.assertEqual(postgres.get_adoption(self.connection, adoption_id)["amount_cents"], 7525)
        self.assertIsNotNone(postgres.get_bench(self.connection, "Bench344")["adoption_id"])

    def test_competing_bookings_and_reset(self) -> None:
        today = park_today()

        def attempt(name: str) -> str:
            with self.open_connection() as connection:
                try:
                    postgres.create_adoption(
                        connection, "Bench344", name, today.isoformat(),
                        (today + timedelta(days=10)).isoformat(), "10",
                    )
                    return "booked"
                except BenchUnavailable:
                    return "unavailable"

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(attempt, ("First", "Second"))),
                                  ["booked", "unavailable"])
        later_id = postgres.create_adoption(
            self.connection, "Bench344", "Later Visitor",
            (today + timedelta(days=11)).isoformat(),
            (today + timedelta(days=20)).isoformat(), "10",
        )
        self.assertIsNotNone(later_id)
        self.assertEqual(len(postgres.list_benches(self.connection, status="adopted")), 344)
        admin.reset(self.connection)
        self.assertEqual(len(postgres.list_benches(self.connection, status="adopted")), 343)
        self.assertIsNone(postgres.get_bench(self.connection, "Bench344")["adoption_id"])

    def test_refresh_timelines_preserves_visitor_booking(self) -> None:
        today = park_today()
        adoption_id = postgres.create_adoption(
            self.connection, "Bench344", "Visitor", today.isoformat(),
            (today + timedelta(days=10)).isoformat(), "75.25",
        )
        visitor_before = postgres.get_adoption(self.connection, adoption_id)

        self.assertEqual(
            admin.refresh_timelines(self.connection, randomizer=Random(2027)), 343
        )

        visitor_after = postgres.get_adoption(self.connection, adoption_id)
        self.assertEqual(visitor_after, visitor_before)
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT a.start_date, a.end_date
                   FROM adoptions a
                   WHERE a.is_seeded"""
            )
            timelines = cursor.fetchall()
        self.assertEqual(
            len({(row["start_date"], row["end_date"]) for row in timelines}), 343
        )

    def test_expand_adoptions_reaches_target_and_preserves_visitor(self) -> None:
        today = park_today()
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """DELETE FROM adoptions
                       WHERE CAST(substring(bench_id FROM '[0-9]+') AS INTEGER) > 30"""
                )
                cursor.execute(
                    """DELETE FROM adopters p
                       WHERE NOT EXISTS (
                           SELECT 1 FROM adoptions a WHERE a.adopter_id = p.id
                       )"""
                )
        visitor_id = postgres.create_adoption(
            self.connection, "Bench344", "Visitor", today.isoformat(),
            (today + timedelta(days=10)).isoformat(), "75.25",
        )
        visitor_before = postgres.get_adoption(self.connection, visitor_id)

        self.assertEqual(
            admin.expand_adoptions(self.connection, randomizer=Random(2028)), 312
        )
        self.assertEqual(len(postgres.list_benches(self.connection, status="adopted")), 343)
        self.assertEqual(postgres.get_adoption(self.connection, visitor_id), visitor_before)
        self.assertEqual(admin.expand_adoptions(self.connection), 0)

    def test_refresh_locations_preserves_adoptions_and_adopters(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT a.id, a.bench_id, a.adopter_id, a.start_date,
                          a.end_date, a.amount_cents, p.public_name
                   FROM adoptions a
                   JOIN adopters p ON p.id = a.adopter_id
                   ORDER BY a.id"""
            )
            records_before = cursor.fetchall()
            cursor.execute(
                """UPDATE benches
                   SET location = 'Old area', latitude = 0, longitude = 0
                   WHERE id = 'Bench1'"""
            )

        self.assertEqual(admin.refresh_locations(self.connection), 550)

        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT a.id, a.bench_id, a.adopter_id, a.start_date,
                          a.end_date, a.amount_cents, p.public_name
                   FROM adoptions a
                   JOIN adopters p ON p.id = a.adopter_id
                   ORDER BY a.id"""
            )
            self.assertEqual(cursor.fetchall(), records_before)
        bench = postgres.get_bench(self.connection, "Bench1")
        self.assertEqual(bench["location"], "Van Cortlandt Park · Site 1")
        self.assertNotEqual((bench["latitude"], bench["longitude"]), (0, 0))


if __name__ == "__main__":
    unittest.main()

"""Run with TEST_DATABASE_URL to verify the hosted storage against Postgres."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from psycopg import sql

from columbia_ss import admin, postgres
from columbia_ss.database import BenchUnavailable, park_today


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
        admin.reset(self.connection)

    def test_seed_browse_and_exact_amount(self) -> None:
        self.assertEqual(len(postgres.list_benches(self.connection)), 550)
        self.assertEqual(len(postgres.list_benches(self.connection, search="Demo Zone 1")), 50)
        self.assertEqual(len(postgres.list_benches(self.connection, search="bench31")), 1)
        self.assertEqual(len(postgres.list_benches(self.connection, search="Bench_")), 550)
        self.assertIsNotNone(postgres.get_bench(self.connection, "Bench1")["adoption_id"])
        today = park_today()
        adoption_id = postgres.create_adoption(
            self.connection, "Bench31", "Alex", today.isoformat(),
            (today + timedelta(days=10)).isoformat(), "75.25",
        )
        self.assertEqual(postgres.get_adoption(self.connection, adoption_id)["amount_cents"], 7525)
        self.assertIsNotNone(postgres.get_bench(self.connection, "Bench31")["adoption_id"])

    def test_competing_bookings_and_reset(self) -> None:
        today = park_today()

        def attempt(name: str) -> str:
            with self.open_connection() as connection:
                try:
                    postgres.create_adoption(
                        connection, "Bench31", name, today.isoformat(),
                        (today + timedelta(days=10)).isoformat(), "10",
                    )
                    return "booked"
                except BenchUnavailable:
                    return "unavailable"

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(attempt, ("First", "Second"))),
                                  ["booked", "unavailable"])
        self.assertEqual(len(postgres.list_benches(self.connection, status="adopted")), 31)
        admin.reset(self.connection)
        self.assertEqual(len(postgres.list_benches(self.connection, status="adopted")), 30)
        self.assertIsNone(postgres.get_bench(self.connection, "Bench31")["adoption_id"])


if __name__ == "__main__":
    unittest.main()

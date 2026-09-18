"""Tests for the public browse, review, and confirmation flow."""

import tempfile
import unittest
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import columbia_ss
from columbia_ss import create_app
from columbia_ss.database import connect, park_today


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "web.sqlite3"
        self.app = create_app(self.database_path)
        self.app.testing = True
        self.client = self.app.test_client()
        self.today = park_today()
        self.form = {
            "public_name": "Sam Demo",
            "start_date": self.today.isoformat(),
            "end_date": (self.today + timedelta(days=10)).isoformat(),
            "amount": "75.25",
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_directory_and_detail_show_both_statuses(self) -> None:
        directory = self.client.get("/")
        self.assertEqual(directory.status_code, 200)
        self.assertIn(b"550", directory.data)
        self.assertIn(b"Bench1", directory.data)
        adopted = self.client.get("/benches/Bench1")
        self.assertIn(b"Demo Donor 1", adopted.data)
        available = self.client.get("/benches/Bench31")
        self.assertIn(b"Adopt this bench", available.data)

    def test_search_filter_and_empty_state(self) -> None:
        response = self.client.get("/?q=Bench31&status=available")
        self.assertIn(b"1 bench found", response.data)
        response = self.client.get("/?q=Bench31&status=adopted")
        self.assertIn(b"No benches found", response.data)

    def test_review_then_confirm(self) -> None:
        review = self.client.post("/benches/Bench31/review", data=self.form)
        self.assertEqual(review.status_code, 200)
        self.assertIn(b"$75.25", review.data)
        self.assertIn(b"No payment is collected", review.data)
        confirmed = self.client.post("/benches/Bench31/confirm", data=self.form)
        self.assertEqual(confirmed.status_code, 303)
        confirmation = self.client.get(confirmed.headers["Location"])
        self.assertIn(b"No payment was taken", confirmation.data)
        self.assertIn(b"$75.25", confirmation.data)
        self.assertIn(b"Sam Demo", self.client.get("/benches/Bench31").data)
        with closing(connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT amount_cents FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
                7525,
            )

    def test_second_submission_is_rejected(self) -> None:
        self.client.post("/benches/Bench31/confirm", data=self.form)
        response = self.client.post("/benches/Bench31/confirm", data=self.form)
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"already booked", response.data)
        with closing(connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
                1,
            )

    def test_invalid_booking_is_not_recorded(self) -> None:
        invalid_form = {**self.form, "amount": "0"}
        response = self.client.post("/benches/Bench31/review", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"greater than $0", response.data)
        response = self.client.post("/benches/Bench31/confirm", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        with closing(connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM adoptions WHERE bench_id='Bench31'").fetchone()[0],
                0,
            )

    def test_missing_bench_and_adoption_return_404(self) -> None:
        self.assertEqual(self.client.get("/benches/Bench9999").status_code, 404)
        self.assertEqual(self.client.get("/adoptions/9999").status_code, 404)


class CliTests(unittest.TestCase):
    def test_entry_point_starts_app(self) -> None:
        with patch("columbia_ss.create_app") as factory:
            columbia_ss.main()
        factory.assert_called_once_with()
        factory.return_value.run.assert_called_once_with(debug=False)


if __name__ == "__main__":
    unittest.main()

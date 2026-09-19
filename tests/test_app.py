"""Tests for the public browse, review, and confirmation flow."""

import unittest
from datetime import timedelta
from unittest.mock import patch

import columbia_ss
from columbia_ss import create_app
from columbia_ss.domain import park_today

from fake_storage import FakeStorage


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage()
        self.app = create_app(
            "postgresql://test.invalid/demo", storage_backend=self.storage
        )
        self.app.testing = True
        self.client = self.app.test_client()
        self.today = park_today()
        self.form = {
            "public_name": "Sam Demo",
            "start_date": self.today.isoformat(),
            "end_date": (self.today + timedelta(days=10)).isoformat(),
            "amount": "75.25",
        }

    def test_directory_and_detail_show_both_statuses(self) -> None:
        directory = self.client.get("/")
        self.assertEqual(directory.status_code, 200)
        self.assertIn(b"550", directory.data)
        self.assertIn(b"Bench1", directory.data)
        adopted = self.client.get("/benches/Bench1")
        self.assertIn(b"Demo Donor 1", adopted.data)
        available = self.client.get("/benches/Bench31")
        self.assertIn(b"Adopt this bench", available.data)

    def test_directory_leads_with_summary_and_availability_map(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"30</strong><span>adopted or reserved", response.data)
        self.assertIn(b"520</strong><span>available now", response.data)
        summary = response.data[
            response.data.index(b'aria-label="Bench collection summary"'):
            response.data.index(b"NEXT AVAILABLE BENCH")
        ]
        self.assertNotIn(b"benches total", summary)
        self.assertIn(b"NEXT AVAILABLE BENCH", response.data)
        self.assertIn(b'href="/benches/Bench31/adopt">Adopt Bench31', response.data)
        self.assertIn(b"90-DAY AVAILABILITY", response.data)
        self.assertIn(b"Scrollable bench availability map", response.data)
        self.assertIn(b"--bar-left:", response.data)
        self.assertLess(response.data.index(b"NEXT AVAILABLE BENCH"), response.data.index(b'id="browse"'))

    def test_next_available_advances_after_adoption(self) -> None:
        response = self.client.get("/")
        highlight = response.data[
            response.data.index(b"NEXT AVAILABLE BENCH"):response.data.index(b"90-DAY AVAILABILITY")
        ]
        self.assertIn(b'href="/benches/Bench31/adopt">Adopt Bench31', highlight)

        self.client.post("/benches/Bench31/confirm", data=self.form)
        updated = self.client.get("/")
        updated_highlight = updated.data[
            updated.data.index(b"NEXT AVAILABLE BENCH"):updated.data.index(b"90-DAY AVAILABILITY")
        ]
        self.assertIn(b'href="/benches/Bench32/adopt">Adopt Bench32', updated_highlight)

    def test_overview_remains_global_when_directory_is_filtered(self) -> None:
        response = self.client.get("/?q=Bench31&status=available")
        self.assertIn(b"30</strong><span>adopted or reserved", response.data)
        self.assertIn(b'href="/benches/Bench31/adopt">Adopt Bench31', response.data)
        self.assertIn(b"1 bench found", response.data)

    def test_search_filter_and_empty_state(self) -> None:
        response = self.client.get("/?q=Bench31&status=available")
        self.assertIn(b"1 bench found", response.data)
        response = self.client.get("/?q=Bench31&status=adopted")
        self.assertIn(b"No benches found", response.data)

    def test_directory_filter_script_is_available(self) -> None:
        directory = self.client.get("/")
        self.assertIn(b'/static/directory.js', directory.data)
        script = self.client.get("/static/directory.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"replaceDirectory", script.data)
        self.assertIn(b"history.pushState", script.data)
        script.close()

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
        adoption_id = self.storage.benches["Bench31"]["adoption_id"]
        self.assertEqual(self.storage.adoptions[adoption_id]["amount_cents"], 7525)

    def test_second_submission_is_rejected(self) -> None:
        self.client.post("/benches/Bench31/confirm", data=self.form)
        response = self.client.post("/benches/Bench31/confirm", data=self.form)
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"already booked", response.data)
        self.assertEqual(
            sum(row["bench_id"] == "Bench31" for row in self.storage.adoptions.values()), 1
        )

    def test_invalid_booking_is_not_recorded(self) -> None:
        invalid_form = {**self.form, "amount": "0"}
        response = self.client.post("/benches/Bench31/review", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"greater than $0", response.data)
        response = self.client.post("/benches/Bench31/confirm", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.storage.benches["Bench31"]["adoption_id"])

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

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
            "postgresql://test.invalid/bench_adoption", storage_backend=self.storage
        )
        self.app.testing = True
        self.client = self.app.test_client()
        self.today = park_today()
        self.form = {
            "public_name": "Taylor Rivers",
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
        self.assertIn(b"Anonymous Park Supporter", adopted.data)
        self.assertNotIn(b"A PLACE TO PAUSE", adopted.data)
        available = self.client.get("/benches/Bench344")
        self.assertIn(b"Adopt this bench", available.data)

    def test_bench_detail_uses_a_random_image_from_img_folder(self) -> None:
        image_name = "wood-plastic-composite-benches.jpg.webp"

        with patch("columbia_ss.app.random.choice", return_value=image_name) as choice:
            response = self.client.get("/benches/Bench344")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b'src="/bench-images/wood-plastic-composite-benches.jpg.webp"',
            response.data,
        )
        location = self.storage.benches["Bench344"]["location"].encode()
        self.assertIn(b'alt="Bench at ' + location + b'"', response.data)
        self.assertEqual(choice.call_count, 1)
        self.assertIn(image_name, choice.call_args.args[0])
        self.assertNotIn(
            "Logo_of_the_New_York_City_Department_of_Parks_&_Recreation.svg.webp",
            choice.call_args.args[0],
        )

        image = self.client.get(f"/bench-images/{image_name}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/webp")
        image.close()

    def test_bench_svg_is_used_as_the_site_favicon(self) -> None:
        response = self.client.get("/")
        self.assertIn(b'class="nav-availability"', response.data)
        self.assertIn(
            b'<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
            response.data,
        )

        favicon = self.client.get("/favicon.svg")
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.mimetype, "image/svg+xml")
        self.assertIn(b"<svg", favicon.data)
        favicon.close()

    def test_directory_leads_with_summary_and_availability_map(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Adopt a bench", response.data)
        self.assertIn(b"today.", response.data)
        self.assertIn(
            b"Your support helps care for Van Cortlandt Park and sustain its daily operations.",
            response.data,
        )
        self.assertIn(b'href="/#bench-map">Explore benches', response.data)
        self.assertIn(b"343</strong><span>adopted", response.data)
        self.assertIn(b"207</strong><span>available now", response.data)
        summary = response.data[
            response.data.index(b'aria-label="Bench collection summary"'):
            response.data.index(b"NEXT AVAILABLE BENCH")
        ]
        self.assertNotIn(b"benches total", summary)
        self.assertIn(b"NEXT AVAILABLE BENCH", response.data)
        self.assertIn(b'href="/benches/Bench344/adopt">Adopt Bench344', response.data)
        self.assertIn(b"Scrollable bench availability map", response.data)
        self.assertIn(b'class="today-date"', response.data)
        self.assertIn(b">Today</strong>", response.data)
        self.assertIn(self.today.strftime("%b %-d").encode(), response.data)
        self.assertIn(b'class="today-line"', response.data)
        self.assertNotIn(b"demo", response.data.lower())
        self.assertNotIn(b"fictional", response.data.lower())
        self.assertIn(b"--bar-left:", response.data)
        self.assertIn(b"Availability timeline", response.data)
        self.assertIn(b'<i class="legend-reserved"></i>Adopted', response.data)
        self.assertNotIn(b"Adopted or reserved", response.data)
        self.assertNotIn(b"Choose a marker to see where each bench sits", response.data)
        self.assertIn(b"Adopt a bench today to support our operations.", response.data)
        self.assertNotIn(b"Select any marker to see its status", response.data)
        removed_copy = (
            b"60-DAY HISTORY",
            b"90-DAY OUTLOOK",
            b"Scroll left to review the last 60 days",
            b"Prototype locations",
            b"Bench positions are generated for planning purposes",
            b"See every bench across Van Cortlandt Park",
            b"A PLACE TO PAUSE",
            b"THE COLLECTION",
        )
        for text in removed_copy:
            self.assertNotIn(text, response.data)
        self.assertLess(response.data.index(b"NEXT AVAILABLE BENCH"), response.data.index(b'id="bench-map"'))
        self.assertLess(response.data.index(b'id="bench-map"'), response.data.index(b'id="availability-title"'))

    def test_next_available_advances_after_adoption(self) -> None:
        response = self.client.get("/")
        highlight = response.data[
            response.data.index(b"NEXT AVAILABLE BENCH"):response.data.index(b'id="availability-title"')
        ]
        self.assertIn(b'href="/benches/Bench344/adopt">Adopt Bench344', highlight)

        self.client.post("/benches/Bench344/confirm", data=self.form)
        updated = self.client.get("/")
        updated_highlight = updated.data[
            updated.data.index(b"NEXT AVAILABLE BENCH"):updated.data.index(b'id="availability-title"')
        ]
        self.assertIn(b'href="/benches/Bench345/adopt">Adopt Bench345', updated_highlight)

    def test_available_map_link_preserves_global_overview(self) -> None:
        response = self.client.get("/?status=available")
        self.assertIn(b"343</strong><span>adopted", response.data)
        self.assertIn(b'href="/benches/Bench344/adopt">Adopt Bench344', response.data)
        self.assertIn(b'data-initial-status="available"', response.data)

    def test_availability_map_includes_adoptions_from_the_last_60_days(self) -> None:
        start = self.today - timedelta(days=45)
        end = self.today - timedelta(days=15)
        self.storage._store_adoption(
            bench_id="Bench344",
            public_name="Recent Supporter",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            amount_cents=5000,
        )

        response = self.client.get("/")

        self.assertIn(
            f'title="Reserved {start} through {end}"'.encode(), response.data
        )
        self.assertIn(b'href="/benches/Bench344/adopt">Adopt Bench344', response.data)

    def test_bottom_directory_is_replaced_by_geographic_map(self) -> None:
        response = self.client.get("/")

        self.assertIn(b'id="geographic-map"', response.data)
        self.assertIn(b'id="bench-map-data"', response.data)
        self.assertIn(b'id="park-boundary-data"', response.data)
        self.assertIn(b'"gispropnum": "X092"', response.data)
        self.assertIn(b'"image_url": "/bench-images/', response.data)
        self.assertNotIn(b"Prototype locations", response.data)
        self.assertIn(b'data-map-filter="all"', response.data)
        self.assertIn(b'data-map-filter="available"', response.data)
        self.assertIn(b'data-map-filter="adopted"', response.data)
        self.assertNotIn(b'aria-label="Bench marker legend"', response.data)
        self.assertNotIn(b"Find your bench", response.data)
        self.assertNotIn(b'class="bench-grid"', response.data)
        self.assertNotIn(b"Search by bench", response.data)
        self.assertNotIn(b'class="pagination"', response.data)
        self.assertIn(b"supercluster@8.0.1", response.data)
        self.assertNotIn(b"leaflet.markercluster", response.data)

    def test_directory_filter_script_is_available(self) -> None:
        directory = self.client.get("/")
        self.assertIn(b'/static/directory.js', directory.data)
        script = self.client.get("/static/directory.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"initializeGeographicMap", script.data)
        self.assertIn(b"new window.Supercluster", script.data)
        self.assertIn(b"radius: 120", script.data)
        self.assertIn(b"minPoints: 6", script.data)
        self.assertIn(b"map.on(\"moveend\", renderMarkers)", script.data)
        self.assertIn(b"getClusterExpansionZoom", script.data)
        self.assertIn(b"window.L.geoJSON(parkBoundary", script.data)
        self.assertIn(b"map.setMaxBounds(parkBounds.pad(0.2))", script.data)
        self.assertIn(b"if (!window.Supercluster)", script.data)
        self.assertIn(b"--available-share", script.data)
        self.assertIn(b"applyFilter", script.data)
        self.assertIn(b"scrollWheelZoom: true", script.data)
        self.assertIn(b"frame.scrollLeft", script.data)
        self.assertIn(b"ADOPTED UNTIL ${bench.adoption_end_date}", script.data)
        self.assertIn(b'map-selection-image', script.data)
        self.assertIn(b'if (bench.image_url) {', script.data)
        self.assertIn(b'if (image) selection.append(image)', script.data)
        self.assertNotIn(b"ADOPTED OR RESERVED", script.data)
        script.close()

    def test_sticky_bench_labels_cover_the_today_line(self) -> None:
        stylesheet = self.client.get("/static/style.css")

        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn(b".park-nav .nav-availability{border-right:1px solid", stylesheet.data)
        self.assertNotIn(b".nav-availability{box-shadow", stylesheet.data)
        self.assertIn(b".gantt-axis{position:sticky;top:0;z-index:5", stylesheet.data)
        self.assertIn(b".gantt-axis>span{position:sticky;left:0;z-index:4", stylesheet.data)
        self.assertIn(b".gantt-label{position:sticky;left:0;z-index:3", stylesheet.data)
        self.assertIn(b".today-line{position:absolute;z-index:1", stylesheet.data)
        self.assertIn(b".bench-marker-adopted{border-radius:50%;transform:none}", stylesheet.data)
        self.assertIn(b"background:conic-gradient(#3e8060", stylesheet.data)
        self.assertIn(
            b'li[data-list-status="available"] a span:last-child',
            stylesheet.data,
        )
        self.assertIn(b"background:var(--mint);color:#285944", stylesheet.data)
        self.assertIn(
            b'li[data-list-status="adopted"] a span:last-child',
            stylesheet.data,
        )
        self.assertIn(b"background:#f3d486;color:#684914", stylesheet.data)
        stylesheet.close()

    def test_map_contains_every_bench_and_generated_coordinates(self) -> None:
        with patch.object(
            self.storage, "list_benches", wraps=self.storage.list_benches
        ) as list_benches:
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'data-list-status="'), 550)
        self.assertIn(b'"latitude": 40.', response.data)
        self.assertIn(b'"longitude": -73.', response.data)
        self.assertIn(
            f'"adoption_end_date": "{self.storage.benches["Bench1"]["end_date"]}"'.encode(),
            response.data,
        )
        self.assertEqual(list_benches.call_count, 1)

    def test_review_then_confirm(self) -> None:
        review = self.client.post("/benches/Bench344/review", data=self.form)
        self.assertEqual(review.status_code, 200)
        self.assertIn(b"$75.25", review.data)
        self.assertIn(b"No payment is collected", review.data)
        confirmed = self.client.post("/benches/Bench344/confirm", data=self.form)
        self.assertEqual(confirmed.status_code, 303)
        confirmation = self.client.get(confirmed.headers["Location"])
        self.assertIn(b"No online payment was taken", confirmation.data)
        self.assertIn(b"$75.25", confirmation.data)
        self.assertIn(b"Taylor Rivers", self.client.get("/benches/Bench344").data)
        adoption_id = self.storage.benches["Bench344"]["adoption_id"]
        self.assertEqual(self.storage.adoptions[adoption_id]["amount_cents"], 7525)

    def test_second_submission_is_rejected(self) -> None:
        self.client.post("/benches/Bench344/confirm", data=self.form)
        response = self.client.post("/benches/Bench344/confirm", data=self.form)
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"already booked", response.data)
        self.assertEqual(
            sum(row["bench_id"] == "Bench344" for row in self.storage.adoptions.values()), 1
        )

    def test_invalid_booking_is_not_recorded(self) -> None:
        invalid_form = {**self.form, "amount": "0"}
        response = self.client.post("/benches/Bench344/review", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"greater than $0", response.data)
        response = self.client.post("/benches/Bench344/confirm", data=invalid_form)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.storage.benches["Bench344"]["adoption_id"])

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

"""Tests for boundary-constrained prototype bench locations."""

import unittest

from columbia_ss.locations import (
    _point_in_polygon,
    PARK_LOCATION_HUBS,
    generated_bench_coordinates,
    generated_bench_location,
    is_inside_park,
    park_boundary_geojson,
)


class GeneratedLocationTests(unittest.TestCase):
    def test_coordinates_are_stable_unique_and_inside_the_park(self) -> None:
        first_pass = [generated_bench_coordinates(number) for number in range(1, 551)]
        second_pass = [generated_bench_coordinates(number) for number in range(1, 551)]

        self.assertEqual(first_pass, second_pass)
        self.assertEqual(len(set(first_pass)), 550)
        self.assertTrue(all(is_inside_park(*point) for point in first_pass))

    def test_initial_adopted_benches_are_distributed_across_the_park(self) -> None:
        points = [generated_bench_coordinates(number) for number in range(1, 344)]
        represented_hubs = {
            (number - 1) % len(PARK_LOCATION_HUBS) for number in range(1, 344)
        }
        self.assertEqual(represented_hubs, set(range(len(PARK_LOCATION_HUBS))))
        self.assertLess(min(latitude for latitude, _ in points), 40.889)
        self.assertGreater(max(latitude for latitude, _ in points), 40.906)

    def test_inventory_is_concentrated_around_park_hubs(self) -> None:
        for number in range(1, 551):
            latitude, longitude = generated_bench_coordinates(number)
            center_latitude, center_longitude = PARK_LOCATION_HUBS[
                (number - 1) % len(PARK_LOCATION_HUBS)
            ]
            self.assertLessEqual(abs(latitude - center_latitude), 0.000901)
            self.assertLessEqual(abs(longitude - center_longitude), 0.001201)

    def test_boundary_snapshot_has_source_metadata(self) -> None:
        boundary = park_boundary_geojson()
        feature = boundary["features"][0]
        self.assertEqual(feature["geometry"]["type"], "MultiPolygon")
        self.assertEqual(feature["properties"]["gispropnum"], "X092")
        self.assertIn("NYC Parks Properties", feature["properties"]["source"])

    def test_polygon_holes_are_excluded(self) -> None:
        polygon = (
            ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)),
            ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0), (1.0, 1.0)),
        )
        self.assertTrue(_point_in_polygon(0.5, 0.5, polygon))
        self.assertFalse(_point_in_polygon(2.0, 2.0, polygon))

    def test_location_labels_do_not_imply_numbered_park_areas(self) -> None:
        self.assertEqual(
            generated_bench_location(31), "Van Cortlandt Park · Site 31"
        )

    def test_invalid_bench_number_is_rejected(self) -> None:
        for number in (0, 551):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    generated_bench_coordinates(number)
                with self.assertRaises(ValueError):
                    generated_bench_location(number)


if __name__ == "__main__":
    unittest.main()

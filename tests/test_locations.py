"""Tests for generated prototype bench locations."""

import unittest

from columbia_ss.locations import PARK_AREA_CENTERS, generated_bench_coordinates


class GeneratedLocationTests(unittest.TestCase):
    def test_coordinates_are_stable_and_inside_the_park_map_bounds(self) -> None:
        first_pass = [generated_bench_coordinates(number) for number in range(1, 551)]
        second_pass = [generated_bench_coordinates(number) for number in range(1, 551)]

        self.assertEqual(first_pass, second_pass)
        self.assertEqual(len(set(first_pass)), 550)
        self.assertTrue(all(40.878 < latitude < 40.916 for latitude, _ in first_pass))
        self.assertTrue(all(-73.918 < longitude < -73.867 for _, longitude in first_pass))

    def test_each_group_of_fifty_uses_a_different_park_area(self) -> None:
        for area_index, (center_latitude, center_longitude) in enumerate(
            PARK_AREA_CENTERS
        ):
            number = area_index * 50 + 1
            latitude, longitude = generated_bench_coordinates(number)
            self.assertLess(abs(latitude - center_latitude), 0.001)
            self.assertLess(abs(longitude - center_longitude), 0.0013)

    def test_invalid_bench_number_is_rejected(self) -> None:
        for number in (0, 551):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    generated_bench_coordinates(number)


if __name__ == "__main__":
    unittest.main()

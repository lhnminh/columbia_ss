"""Stable prototype locations for the Van Cortlandt Park bench inventory."""

from __future__ import annotations

from random import Random


# Each group is centered on a different part of Van Cortlandt Park. Small,
# deterministic offsets keep the prototype markers readable without claiming
# that they represent a surveyed bench location.
PARK_AREA_CENTERS = (
    (40.8898, -73.8965),
    (40.8895, -73.8878),
    (40.8918, -73.9008),
    (40.8950, -73.8948),
    (40.8935, -73.8880),
    (40.8957, -73.8835),
    (40.8995, -73.9030),
    (40.9007, -73.8965),
    (40.9025, -73.8875),
    (40.9056, -73.9010),
    (40.9062, -73.8920),
)


def generated_bench_coordinates(number: int) -> tuple[float, float]:
    """Return a stable generated latitude and longitude for one seeded bench."""
    if not 1 <= number <= 550:
        raise ValueError("Bench number must be between 1 and 550.")

    area_index = (number - 1) // 50
    center_latitude, center_longitude = PARK_AREA_CENTERS[area_index]
    randomizer = Random(731_000 + number)
    latitude = center_latitude + randomizer.uniform(-0.0009, 0.0009)
    longitude = center_longitude + randomizer.uniform(-0.0012, 0.0012)
    return round(latitude, 6), round(longitude, 6)

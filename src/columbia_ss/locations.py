"""Stable prototype locations inside the Van Cortlandt Park boundary."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from random import Random
from typing import Any


BENCH_COUNT = 550
BOUNDARY_RESOURCE = "data/van_cortlandt_park.geojson"
Point = tuple[float, float]
Ring = tuple[Point, ...]
Polygon = tuple[Ring, ...]

# These hubs restore the original grouped-location feel while remaining inside
# the official park boundary. Bench numbers rotate through the hubs so the
# initial adopted inventory is spread throughout the park instead of occupying
# one geographic section.
PARK_LOCATION_HUBS: tuple[Point, ...] = (
    (40.8890, -73.8970),
    (40.8875, -73.8870),
    (40.8880, -73.8810),
    (40.8950, -73.8948),
    (40.8935, -73.8880),
    (40.8957, -73.8835),
    (40.9007, -73.8965),
    (40.9010, -73.8910),
    (40.9025, -73.8875),
    (40.9050, -73.8940),
    (40.9062, -73.8920),
)


@lru_cache(maxsize=1)
def park_boundary_geojson() -> dict[str, Any]:
    """Return the checked-in NYC Parks boundary snapshot."""
    resource = files("columbia_ss").joinpath(BOUNDARY_RESOURCE)
    return json.loads(resource.read_text(encoding="utf-8"))


def _polygons() -> tuple[Polygon, ...]:
    geometry = park_boundary_geojson()["features"][0]["geometry"]
    return tuple(
        tuple(
            tuple((longitude, latitude) for longitude, latitude in ring)
            for ring in polygon
        )
        for polygon in geometry["coordinates"]
    )


def _point_in_ring(
    longitude: float, latitude: float, ring: Ring,
) -> bool:
    """Return whether a point is inside a closed ring using ray casting."""
    inside = False
    previous_longitude, previous_latitude = ring[-1]
    for current_longitude, current_latitude in ring:
        crosses_latitude = (current_latitude > latitude) != (
            previous_latitude > latitude
        )
        if crosses_latitude:
            crossing_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )
            if longitude < crossing_longitude:
                inside = not inside
        previous_longitude, previous_latitude = current_longitude, current_latitude
    return inside


def _point_in_polygon(
    longitude: float, latitude: float, polygon: Polygon,
) -> bool:
    """Return whether a point is inside an exterior ring and outside its holes."""
    return _point_in_ring(longitude, latitude, polygon[0]) and not any(
        _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
    )


def is_inside_park(latitude: float, longitude: float) -> bool:
    """Return whether a latitude and longitude fall within the park snapshot."""
    return any(
        _point_in_polygon(longitude, latitude, polygon)
        for polygon in _polygons()
    )


def _interior_hub_candidate(randomizer: Random, center: Point) -> Point:
    """Generate one concentrated point near a hub without leaving the park."""
    center_latitude, center_longitude = center
    while True:
        candidate = (
            round(center_latitude + randomizer.uniform(-0.0009, 0.0009), 6),
            round(center_longitude + randomizer.uniform(-0.0012, 0.0012), 6),
        )
        if is_inside_park(*candidate):
            return candidate


@lru_cache(maxsize=1)
def _generated_coordinates() -> tuple[Point, ...]:
    """Build stable prototype clusters distributed across the park."""
    selected: list[Point] = []
    for bench_index in range(BENCH_COUNT):
        center = PARK_LOCATION_HUBS[bench_index % len(PARK_LOCATION_HUBS)]
        randomizer = Random(731_000 + bench_index + 1)
        candidate = _interior_hub_candidate(randomizer, center)
        while candidate in selected:
            candidate = _interior_hub_candidate(randomizer, center)
        selected.append(candidate)
    return tuple(selected)


def generated_bench_coordinates(number: int) -> Point:
    """Return a stable generated latitude and longitude for one seeded bench."""
    if not 1 <= number <= BENCH_COUNT:
        raise ValueError(f"Bench number must be between 1 and {BENCH_COUNT}.")
    return _generated_coordinates()[number - 1]


def generated_bench_location(number: int) -> str:
    """Return the stable neutral display label for one prototype bench."""
    if not 1 <= number <= BENCH_COUNT:
        raise ValueError(f"Bench number must be between 1 and {BENCH_COUNT}.")
    return f"Van Cortlandt Park · Site {number}"

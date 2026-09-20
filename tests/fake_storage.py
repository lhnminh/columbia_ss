"""Small in-memory storage double for route-level tests."""

from __future__ import annotations

from datetime import date
from random import Random

from columbia_ss.domain import (
    BenchUnavailable,
    BookingError,
    generated_adopter_name,
    generate_initial_adoption_timelines,
    park_today,
    validate_booking,
)
from columbia_ss.locations import generated_bench_coordinates, generated_bench_location


class FakeStorage:
    """Implement the Postgres module's interface without testing persistence."""

    def __init__(self) -> None:
        self.benches = {}
        for number in range(1, 551):
            latitude, longitude = generated_bench_coordinates(number)
            self.benches[f"Bench{number}"] = {
                "id": f"Bench{number}",
                "location": generated_bench_location(number),
                "latitude": latitude,
                "longitude": longitude,
                "adoption_id": None,
                "start_date": None,
                "end_date": None,
                "public_name": None,
            }
        self.adoptions: dict[int, dict] = {}
        today = park_today()
        for number, start, end in generate_initial_adoption_timelines(
            today=today, randomizer=Random(2026)
        ):
            self._store_adoption(
                bench_id=f"Bench{number}", public_name=generated_adopter_name(number),
                start_date=start.isoformat(), end_date=end.isoformat(), amount_cents=10000,
            )

    def connect(self, _database_url: str) -> FakeStorage:
        return self

    def close(self) -> None:
        pass

    def list_benches(
        self, _connection: FakeStorage, *, search: str = "", status: str = "",
        today: date | None = None,
    ) -> list[dict]:
        current_date = (today or park_today()).isoformat()
        exact_id = next(
            (bench_id for bench_id in self.benches if bench_id.lower() == search.lower()), None
        )
        rows = []
        for bench in self.benches.values():
            row = dict(bench)
            upcoming = sorted(
                (
                    adoption for adoption in self.adoptions.values()
                    if adoption["bench_id"] == row["id"]
                    and adoption["end_date"] >= current_date
                ),
                key=lambda adoption: (adoption["start_date"], adoption["id"]),
            )
            if upcoming:
                adoption = upcoming[0]
                row.update(
                    adoption_id=adoption["id"],
                    start_date=adoption["start_date"],
                    end_date=adoption["end_date"],
                    public_name=adoption["public_name"],
                )
            else:
                row.update(
                    adoption_id=None, start_date=None, end_date=None, public_name=None
                )
            if exact_id:
                matches_search = row["id"] == exact_id
            else:
                matches_search = search.lower() in f"{row['id']} {row['location']}".lower()
            is_adopted = row["adoption_id"] is not None
            matches_status = (
                not status
                or (status == "adopted" and is_adopted)
                or (status == "available" and not is_adopted)
            )
            if matches_search and matches_status:
                rows.append(row)
        return rows

    def get_bench(
        self, _connection: FakeStorage, bench_id: str, *, today: date | None = None,
    ) -> dict | None:
        matches = self.list_benches(self, search=bench_id, today=today)
        return matches[0] if matches else None

    def list_adoptions_in_range(
        self, _connection: FakeStorage, *, start_date: date, end_date: date,
    ) -> list[dict]:
        return [
            dict(adoption)
            for adoption in self.adoptions.values()
            if date.fromisoformat(adoption["start_date"]) <= end_date
            and date.fromisoformat(adoption["end_date"]) >= start_date
        ]

    def create_adoption(
        self, _connection: FakeStorage, bench_id: str, public_name: str,
        start_date: str, end_date: str, amount: str, *, today: date | None = None,
    ) -> int:
        current_date = today or park_today()
        name, start, end, cents = validate_booking(
            public_name, start_date, end_date, amount, today=current_date
        )
        if bench_id not in self.benches:
            raise BookingError("This bench does not exist.")
        if any(
            adoption["bench_id"] == bench_id
            and adoption["start_date"] <= end
            and adoption["end_date"] >= start
            for adoption in self.adoptions.values()
        ):
            raise BenchUnavailable(
                "Those dates overlap an existing adoption. Please choose other dates."
            )
        return self._store_adoption(
            bench_id=bench_id, public_name=name, start_date=start,
            end_date=end, amount_cents=cents,
        )

    def get_adoption(self, _connection: FakeStorage, adoption_id: int) -> dict | None:
        return self.adoptions.get(adoption_id)

    def _store_adoption(
        self, *, bench_id: str, public_name: str, start_date: str,
        end_date: str, amount_cents: int,
    ) -> int:
        adoption_id = len(self.adoptions) + 1
        adoption = {
            "id": adoption_id,
            "bench_id": bench_id,
            "location": self.benches[bench_id]["location"],
            "public_name": public_name,
            "start_date": start_date,
            "end_date": end_date,
            "amount_cents": amount_cents,
        }
        self.adoptions[adoption_id] = adoption
        existing_start = self.benches[bench_id]["start_date"]
        if existing_start is None or start_date < existing_start:
            self.benches[bench_id].update(
                adoption_id=adoption_id, public_name=public_name,
                start_date=start_date, end_date=end_date,
            )
        return adoption_id

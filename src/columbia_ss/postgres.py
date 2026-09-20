"""Postgres persistence for the bench adoption service."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from .domain import BenchUnavailable, BookingError, park_today, validate_booking


def connect(database_url: str) -> Connection[dict[str, Any]]:
    """Open a request-scoped Postgres connection."""
    return psycopg.connect(database_url, autocommit=True, row_factory=dict_row)


def list_benches(
    connection: Connection[dict[str, Any]], *, search: str = "", status: str = "",
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Find benches and their current or future reservation."""
    current_date = today or park_today()
    search = search.strip()
    pattern = f"%{search}%"
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM benches WHERE lower(id) = lower(%s)", (search,))
        exact_id = cursor.fetchone() is not None
        cursor.execute(
            """
            SELECT b.id, b.location, b.latitude, b.longitude,
                   a.id AS adoption_id, a.start_date, a.end_date, p.public_name
            FROM benches b
            LEFT JOIN LATERAL (
                SELECT id, adopter_id, start_date, end_date FROM adoptions
                WHERE bench_id = b.id AND end_date >= %s
                ORDER BY start_date LIMIT 1
            ) a ON true
            LEFT JOIN adopters p ON p.id = a.adopter_id
            WHERE (lower(b.id) = lower(%s)
                   OR (%s = false AND (b.id ILIKE %s OR b.location ILIKE %s)))
              AND (%s = '' OR (%s = 'available' AND a.id IS NULL)
                           OR (%s = 'adopted' AND a.id IS NOT NULL))
            ORDER BY CAST(SUBSTRING(b.id FROM 6) AS INTEGER)
            """,
            (current_date, search, exact_id, pattern, pattern, status, status, status),
        )
        return cursor.fetchall()


def list_adoptions_in_range(
    connection: Connection[dict[str, Any]], *, start_date: date, end_date: date,
) -> list[dict[str, Any]]:
    """Return every adoption that overlaps the requested chart window."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT a.bench_id, a.start_date, a.end_date, p.public_name
            FROM adoptions a
            JOIN adopters p ON p.id = a.adopter_id
            WHERE a.start_date <= %s AND a.end_date >= %s
            ORDER BY CAST(SUBSTRING(a.bench_id FROM 6) AS INTEGER), a.start_date
            """,
            (end_date, start_date),
        )
        return cursor.fetchall()


def get_bench(
    connection: Connection[dict[str, Any]], bench_id: str, *, today: date | None = None,
) -> dict[str, Any] | None:
    """Return one bench and its current or future reservation."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT b.id, b.location, b.latitude, b.longitude,
                   a.id AS adoption_id, a.start_date, a.end_date, p.public_name
            FROM benches b
            LEFT JOIN LATERAL (
                SELECT id, adopter_id, start_date, end_date FROM adoptions
                WHERE bench_id = b.id AND end_date >= %s
                ORDER BY start_date LIMIT 1
            ) a ON true
            LEFT JOIN adopters p ON p.id = a.adopter_id
            WHERE b.id = %s
            """,
            (today or park_today(), bench_id),
        )
        return cursor.fetchone()


def create_adoption(
    connection: Connection[dict[str, Any]], bench_id: str, public_name: str,
    start_date: str, end_date: str,
    amount: str, *, today: date | None = None,
) -> int:
    """Reserve one bench while holding its row lock."""
    current_date = today or park_today()
    name, start, end, cents = validate_booking(
        public_name, start_date, end_date, amount, today=current_date
    )
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM benches WHERE id = %s FOR UPDATE", (bench_id,))
            if cursor.fetchone() is None:
                raise BookingError("This bench does not exist.")
            cursor.execute(
                "SELECT 1 FROM adoptions WHERE bench_id = %s AND end_date >= %s LIMIT 1",
                (bench_id, current_date),
            )
            if cursor.fetchone():
                raise BenchUnavailable("This bench was already booked. Please choose another bench.")
            cursor.execute(
                "INSERT INTO adopters (public_name) VALUES (%s) RETURNING id", (name,)
            )
            adopter_id = cursor.fetchone()["id"]
            cursor.execute(
                """INSERT INTO adoptions
                   (bench_id, adopter_id, start_date, end_date, amount_cents)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (bench_id, adopter_id, start, end, cents),
            )
            return cursor.fetchone()["id"]


def get_adoption(
    connection: Connection[dict[str, Any]], adoption_id: int,
) -> dict[str, Any] | None:
    """Return a booking for its confirmation page."""
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT a.id, a.bench_id, a.start_date, a.end_date, a.amount_cents,
                      p.public_name, b.location
               FROM adoptions a
               JOIN adopters p ON p.id = a.adopter_id
               JOIN benches b ON b.id = a.bench_id
               WHERE a.id = %s""",
            (adoption_id,),
        )
        return cursor.fetchone()

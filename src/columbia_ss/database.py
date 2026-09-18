"""SQLite persistence and booking rules for the bench adoption demo."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

PARK_TIME_ZONE = ZoneInfo("America/New_York")
AMOUNT_PATTERN = re.compile(r"\d+(?:\.\d{1,2})?\Z")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class BookingError(ValueError):
    """A booking cannot be accepted."""


class BenchUnavailable(BookingError):
    """The bench has already been reserved."""


def park_today() -> date:
    """Return today's calendar date in the park's local time zone."""
    return datetime.now(PARK_TIME_ZONE).date()


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Open SQLite with consistent row and integrity settings."""
    connection = sqlite3.connect(str(database_path), timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database(database_path: str | Path) -> None:
    """Create the three tables and seed fictional demo records once."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS benches (
                id TEXT PRIMARY KEY,
                location TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS adopters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_name TEXT NOT NULL CHECK (length(trim(public_name)) BETWEEN 1 AND 80)
            );
            CREATE TABLE IF NOT EXISTS adoptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bench_id TEXT NOT NULL REFERENCES benches(id),
                adopter_id INTEGER NOT NULL REFERENCES adopters(id),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                CHECK (end_date > start_date)
            );
            CREATE INDEX IF NOT EXISTS adoptions_bench_dates
                ON adoptions (bench_id, end_date, start_date);
            """
        )
        connection.execute("BEGIN IMMEDIATE")
        try:
            if connection.execute("SELECT COUNT(*) FROM benches").fetchone()[0]:
                connection.commit()
                return
            benches = [
                (f"Bench{number}", f"Demo Zone {(number - 1) // 50 + 1} · Spot {(number - 1) % 50 + 1}")
                for number in range(1, 551)
            ]
            connection.executemany("INSERT INTO benches (id, location) VALUES (?, ?)", benches)
            today = park_today()
            for number in range(1, 31):
                adopter_id = connection.execute(
                    "INSERT INTO adopters (public_name) VALUES (?)",
                    (f"Demo Donor {number}",),
                ).lastrowid
                start = today - timedelta(days=30) if number <= 20 else today + timedelta(days=10)
                end = today + timedelta(days=60) if number <= 20 else today + timedelta(days=100)
                connection.execute(
                    """INSERT INTO adoptions
                       (bench_id, adopter_id, start_date, end_date, amount_cents)
                       VALUES (?, ?, ?, ?, ?)""",
                    (f"Bench{number}", adopter_id, start.isoformat(), end.isoformat(), 10000),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def validate_booking(
    public_name: str, start_date: str, end_date: str, amount: str, *, today: date | None = None
) -> tuple[str, str, str, int]:
    """Validate form input and return normalized values with integer cents."""
    name = public_name.strip()
    if not 1 <= len(name) <= 80:
        raise BookingError("Enter a public name between 1 and 80 characters.")
    if not DATE_PATTERN.fullmatch(start_date) or not DATE_PATTERN.fullmatch(end_date):
        raise BookingError("Enter valid start and end dates.")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as error:
        raise BookingError("Enter valid start and end dates.") from error
    if start < (today or park_today()):
        raise BookingError("The start date cannot be before today.")
    if end <= start:
        raise BookingError("The end date must be after the start date.")
    if end > (today or park_today()) + timedelta(days=90):
        raise BookingError("The end date must be within 90 days of today.")
    if not AMOUNT_PATTERN.fullmatch(amount):
        raise BookingError("Enter an amount in USD with no more than two decimal places.")
    try:
        cents = int(Decimal(amount) * 100)
    except (InvalidOperation, ValueError) as error:
        raise BookingError("Enter a valid amount in USD.") from error
    if not 0 < cents <= 99_999_999_999:
        raise BookingError("Enter an amount greater than $0 and no more than $999,999,999.99.")
    return name, start.isoformat(), end.isoformat(), cents


def list_benches(
    connection: sqlite3.Connection, *, search: str = "", status: str = "", today: date | None = None
) -> list[sqlite3.Row]:
    """Find benches and their current or future reservation, if any."""
    current_date = (today or park_today()).isoformat()
    search = search.strip()
    pattern = f"%{search}%"
    zone = re.fullmatch(r"Demo Zone (\d+)", search, re.IGNORECASE)
    location_pattern = f"Demo Zone {int(zone.group(1))} · %" if zone else pattern
    exact_id = connection.execute(
        "SELECT 1 FROM benches WHERE id = ? COLLATE NOCASE", (search,)
    ).fetchone() is not None
    return connection.execute(
        """
        SELECT b.id, b.location, a.id AS adoption_id, a.start_date, a.end_date,
               p.public_name
        FROM benches b
        LEFT JOIN adoptions a ON a.id = (
            SELECT id FROM adoptions
            WHERE bench_id = b.id AND end_date >= ?
            ORDER BY start_date LIMIT 1
        )
        LEFT JOIN adopters p ON p.id = a.adopter_id
        WHERE (b.id = ? COLLATE NOCASE OR (? = 0 AND (b.id LIKE ? OR b.location LIKE ?)))
          AND (? = '' OR (? = 'available' AND a.id IS NULL)
                       OR (? = 'adopted' AND a.id IS NOT NULL))
        ORDER BY CAST(SUBSTR(b.id, 6) AS INTEGER)
        """,
        (current_date, search, int(exact_id), pattern, location_pattern, status, status, status),
    ).fetchall()


def get_bench(connection: sqlite3.Connection, bench_id: str, *, today: date | None = None) -> sqlite3.Row | None:
    """Return one bench and its current or future reservation."""
    current_date = (today or park_today()).isoformat()
    return connection.execute(
        """
        SELECT b.id, b.location, a.id AS adoption_id, a.start_date, a.end_date,
               p.public_name
        FROM benches b
        LEFT JOIN adoptions a ON a.id = (
            SELECT id FROM adoptions
            WHERE bench_id = b.id AND end_date >= ?
            ORDER BY start_date LIMIT 1
        )
        LEFT JOIN adopters p ON p.id = a.adopter_id
        WHERE b.id = ?
        """,
        (current_date, bench_id),
    ).fetchone()


def create_adoption(
    connection: sqlite3.Connection,
    bench_id: str,
    public_name: str,
    start_date: str,
    end_date: str,
    amount: str,
    *,
    today: date | None = None,
) -> int:
    """Atomically reserve a bench and return the new adoption ID."""
    current_date = today or park_today()
    name, start, end, cents = validate_booking(
        public_name, start_date, end_date, amount, today=current_date
    )
    connection.execute("BEGIN IMMEDIATE")
    try:
        if connection.execute("SELECT 1 FROM benches WHERE id = ?", (bench_id,)).fetchone() is None:
            raise BookingError("This bench does not exist.")
        if connection.execute(
            "SELECT 1 FROM adoptions WHERE bench_id = ? AND end_date >= ? LIMIT 1",
            (bench_id, current_date.isoformat()),
        ).fetchone():
            raise BenchUnavailable("This bench was already booked. Please choose another bench.")
        adopter_id = connection.execute(
            "INSERT INTO adopters (public_name) VALUES (?)", (name,)
        ).lastrowid
        adoption_id = connection.execute(
            """INSERT INTO adoptions
               (bench_id, adopter_id, start_date, end_date, amount_cents)
               VALUES (?, ?, ?, ?, ?)""",
            (bench_id, adopter_id, start, end, cents),
        ).lastrowid
        connection.commit()
        return adoption_id
    except Exception:
        connection.rollback()
        raise


def get_adoption(connection: sqlite3.Connection, adoption_id: int) -> sqlite3.Row | None:
    """Get a booking for its confirmation page."""
    return connection.execute(
        """SELECT a.id, a.bench_id, a.start_date, a.end_date, a.amount_cents,
                  p.public_name, b.location
           FROM adoptions a
           JOIN adopters p ON p.id = a.adopter_id
           JOIN benches b ON b.id = a.bench_id
           WHERE a.id = ?""",
        (adoption_id,),
    ).fetchone()

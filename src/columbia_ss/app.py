"""Flask pages for browsing and adopting fictional park benches."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

from . import database, postgres
from .database import BenchUnavailable, BookingError, park_today, validate_booking


def _as_date(value: date | str) -> date:
    """Normalize dates returned by SQLite and Postgres."""
    return value if isinstance(value, date) else date.fromisoformat(value)


def _availability_overview(benches, *, today: date) -> tuple[dict | None, list[dict]]:
    """Build the next-available highlight and 90-day availability map."""
    horizon_days = 90
    next_available = next(
        (bench for bench in benches if bench["adoption_id"] is None), None
    )

    map_rows = []
    for bench in benches:
        bar = None
        if bench["adoption_id"] is not None:
            start = max(_as_date(bench["start_date"]), today)
            end = min(_as_date(bench["end_date"]), today + timedelta(days=horizon_days))
            if start <= end:
                bar = {
                    "left": max(0, (start - today).days) / horizon_days * 100,
                    "width": max(1.5, (end - start).days / horizon_days * 100),
                    "start_date": _as_date(bench["start_date"]),
                    "end_date": _as_date(bench["end_date"]),
                }
        map_rows.append({"bench": bench, "bar": bar})
    return next_available, map_rows


def create_app(database_path: str | Path | None = None) -> Flask:
    """Construct the app, using Postgres when DATABASE_URL is configured."""
    static_folder = Path(__file__).resolve().parents[2] / "public" / "static"
    app = Flask(__name__, static_folder=str(static_folder), static_url_path="/static")
    app.config["DATABASE_URL"] = None if database_path else os.environ.get("DATABASE_URL")
    app.config["DATABASE"] = str(
        database_path or os.environ.get("COLUMBIA_SS_DB") or Path.cwd() / "instance" / "benches.sqlite3"
    )
    if os.environ.get("VERCEL") and not app.config["DATABASE_URL"]:
        raise RuntimeError("DATABASE_URL is required on Vercel; refusing to use local SQLite")
    storage = postgres if app.config["DATABASE_URL"] else database
    if storage is database:
        database.initialize_database(app.config["DATABASE"])

    def db():
        if "database" not in g:
            g.database = storage.connect(app.config["DATABASE_URL"] or app.config["DATABASE"])
        return g.database

    @app.teardown_appcontext
    def close_database(_error):
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    @app.context_processor
    def template_helpers():
        today = park_today()
        return {
            "today": today.isoformat(),
            "latest_end_date": (today + timedelta(days=90)).isoformat(),
            "money": lambda cents: f"${cents // 100:,}.{cents % 100:02d}",
        }

    @app.get("/")
    def directory():
        search = request.args.get("q", "").strip()[:100]
        status = request.args.get("status", "")
        if status not in ("", "available", "adopted"):
            status = ""
        all_benches = storage.list_benches(db(), search=search, status=status)
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        page_size = 24
        pages = max(1, (len(all_benches) + page_size - 1) // page_size)
        page = min(page, pages)
        benches = all_benches[(page - 1) * page_size : page * page_size]
        counts = storage.list_benches(db())
        adopted_count = sum(bench["adoption_id"] is not None for bench in counts)
        today = park_today()
        next_available, availability_rows = _availability_overview(counts, today=today)
        return render_template(
            "directory.html",
            benches=benches,
            search=search,
            status=status,
            page=page,
            pages=pages,
            total=len(all_benches),
            bench_count=len(counts),
            adopted_count=adopted_count,
            next_available=next_available,
            availability_rows=availability_rows,
            map_dates=[today + timedelta(days=offset) for offset in (0, 30, 60, 90)],
        )

    @app.get("/benches/<bench_id>")
    def bench_detail(bench_id: str):
        bench = storage.get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        return render_template("bench.html", bench=bench)

    @app.get("/benches/<bench_id>/adopt")
    def adoption_form(bench_id: str):
        bench = storage.get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        if bench["adoption_id"] is not None:
            return redirect(url_for("bench_detail", bench_id=bench_id))
        return render_template("adopt.html", bench=bench, values={}, error=None)

    @app.post("/benches/<bench_id>/review")
    def review_adoption(bench_id: str):
        bench = storage.get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        values = {
            "public_name": request.form.get("public_name", ""),
            "start_date": request.form.get("start_date", ""),
            "end_date": request.form.get("end_date", ""),
            "amount": request.form.get("amount", ""),
        }
        if bench["adoption_id"] is not None:
            return render_template(
                "adopt.html", bench=bench, values=values,
                error="This bench was already booked. Please choose another bench."
            ), 409
        try:
            name, start, end, cents = validate_booking(**values)
        except BookingError as error:
            return render_template("adopt.html", bench=bench, values=values, error=str(error)), 400
        return render_template(
            "review.html", bench=bench, public_name=name, start_date=start,
            end_date=end, amount=values["amount"], amount_cents=cents,
        )

    @app.post("/benches/<bench_id>/confirm")
    def confirm_adoption(bench_id: str):
        values = {
            "public_name": request.form.get("public_name", ""),
            "start_date": request.form.get("start_date", ""),
            "end_date": request.form.get("end_date", ""),
            "amount": request.form.get("amount", ""),
        }
        try:
            adoption_id = storage.create_adoption(db(), bench_id, **values)
        except BenchUnavailable as error:
            bench = storage.get_bench(db(), bench_id)
            return render_template("booking_error.html", bench=bench, error=str(error)), 409
        except BookingError as error:
            bench = storage.get_bench(db(), bench_id)
            if bench is None:
                abort(404)
            return render_template("adopt.html", bench=bench, values=values, error=str(error)), 400
        return redirect(url_for("confirmation", adoption_id=adoption_id), code=303)

    @app.get("/adoptions/<int:adoption_id>")
    def confirmation(adoption_id: int):
        adoption = storage.get_adoption(db(), adoption_id)
        if adoption is None:
            abort(404)
        return render_template("confirmation.html", adoption=adoption)

    return app

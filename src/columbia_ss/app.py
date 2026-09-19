"""Flask pages for browsing and adopting park benches."""

from __future__ import annotations

import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import postgres
from .domain import BenchUnavailable, BookingError, park_today, validate_booking

load_dotenv()

IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}


def _as_date(value: date | str) -> date:
    """Normalize dates returned by storage backends and test doubles."""
    return value if isinstance(value, date) else date.fromisoformat(value)


def _availability_overview(
    benches, adoptions, *, today: date,
) -> tuple[dict | None, list[dict]]:
    """Build the next-available highlight and adoption timeline."""
    history_days = 60
    future_days = 90
    window_start = today - timedelta(days=history_days)
    window_end = today + timedelta(days=future_days)
    window_days = (window_end - window_start).days
    next_available = next(
        (bench for bench in benches if bench["adoption_id"] is None), None
    )

    map_rows = []
    bars_by_bench: dict[str, list[dict]] = {}
    for adoption in adoptions:
        start = max(_as_date(adoption["start_date"]), window_start)
        end = min(_as_date(adoption["end_date"]), window_end)
        if start <= end:
            bars_by_bench.setdefault(adoption["bench_id"], []).append(
                {
                    "left": (start - window_start).days / window_days * 100,
                    "width": max(0.75, (end - start).days / window_days * 100),
                    "start_date": _as_date(adoption["start_date"]),
                    "end_date": _as_date(adoption["end_date"]),
                }
            )

    for bench in benches:
        map_rows.append({"bench": bench, "bars": bars_by_bench.get(bench["id"], [])})
    return next_available, map_rows


def create_app(
    database_url: str | None = None, *, storage_backend: Any = postgres,
) -> Flask:
    """Construct the Postgres-backed application."""
    static_folder = Path(__file__).resolve().parents[2] / "public" / "static"
    image_folder = Path(__file__).resolve().parents[2] / "img"
    app = Flask(__name__, static_folder=str(static_folder), static_url_path="/static")
    app.config["BENCH_IMAGE_FOLDER"] = image_folder
    app.config["DATABASE_URL"] = database_url or os.environ.get("DATABASE_URL")
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("DATABASE_URL is required")
    storage = storage_backend

    def random_bench_image() -> str | None:
        """Choose an image from the repository's bench image folder."""
        image_names = sorted(
            path.name
            for path in app.config["BENCH_IMAGE_FOLDER"].iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        return random.choice(image_names) if image_names else None

    def db():
        if "database" not in g:
            g.database = storage.connect(app.config["DATABASE_URL"])
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
        map_status = request.args.get("status", "")
        if map_status not in ("available", "adopted"):
            map_status = "all"
        benches = storage.list_benches(db())
        adopted_count = sum(bench["adoption_id"] is not None for bench in benches)
        today = park_today()
        map_start = today - timedelta(days=60)
        map_end = today + timedelta(days=90)
        timeline_adoptions = storage.list_adoptions_in_range(
            db(), start_date=map_start, end_date=map_end
        )
        next_available, availability_rows = _availability_overview(
            benches, timeline_adoptions, today=today
        )
        map_benches = [
            {
                "id": bench["id"],
                "location": bench["location"],
                "latitude": bench["latitude"],
                "longitude": bench["longitude"],
                "available": bench["adoption_id"] is None,
                "adoption_end_date": (
                    _as_date(bench["end_date"]).isoformat()
                    if bench["end_date"] is not None
                    else None
                ),
                "detail_url": url_for("bench_detail", bench_id=bench["id"]),
                "action_url": url_for(
                    "adoption_form" if bench["adoption_id"] is None else "bench_detail",
                    bench_id=bench["id"],
                ),
                "action_label": (
                    "Adopt this bench" if bench["adoption_id"] is None else "View bench"
                ),
            }
            for bench in benches
        ]
        return render_template(
            "directory.html",
            bench_count=len(benches),
            adopted_count=adopted_count,
            next_available=next_available,
            availability_rows=availability_rows,
            map_benches=map_benches,
            map_status=map_status,
            map_dates=[
                {
                    "date": map_start + timedelta(days=offset),
                    "left": offset / 150 * 100,
                }
                for offset in (0, 30, 90, 120, 150)
            ],
            map_today=today,
            today_position=40,
        )

    @app.get("/benches/<bench_id>")
    def bench_detail(bench_id: str):
        bench = storage.get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        return render_template(
            "bench.html", bench=bench, bench_image=random_bench_image()
        )

    @app.get("/bench-images/<path:filename>")
    def bench_image(filename: str):
        """Serve an image selected from the repository's image folder."""
        if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
            abort(404)
        return send_from_directory(app.config["BENCH_IMAGE_FOLDER"], filename)

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

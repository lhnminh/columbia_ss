"""Flask pages for browsing and adopting fictional park benches."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

from .database import (
    BenchUnavailable,
    BookingError,
    connect,
    create_adoption,
    get_adoption,
    get_bench,
    initialize_database,
    list_benches,
    park_today,
    validate_booking,
)


def create_app(database_path: str | Path | None = None) -> Flask:
    """Construct the demo app and initialize its local database."""
    app = Flask(__name__)
    app.config["DATABASE"] = str(
        database_path or os.environ.get("COLUMBIA_SS_DB") or Path.cwd() / "instance" / "benches.sqlite3"
    )
    initialize_database(app.config["DATABASE"])

    def db():
        if "database" not in g:
            g.database = connect(app.config["DATABASE"])
        return g.database

    @app.teardown_appcontext
    def close_database(_error):
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    @app.context_processor
    def template_helpers():
        return {
            "today": park_today().isoformat(),
            "money": lambda cents: f"${cents // 100:,}.{cents % 100:02d}",
        }

    @app.get("/")
    def directory():
        search = request.args.get("q", "").strip()[:100]
        status = request.args.get("status", "")
        if status not in ("", "available", "adopted"):
            status = ""
        all_benches = list_benches(db(), search=search, status=status)
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        page_size = 24
        pages = max(1, (len(all_benches) + page_size - 1) // page_size)
        page = min(page, pages)
        benches = all_benches[(page - 1) * page_size : page * page_size]
        counts = list_benches(db())
        adopted_count = sum(bench["adoption_id"] is not None for bench in counts)
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
        )

    @app.get("/benches/<bench_id>")
    def bench_detail(bench_id: str):
        bench = get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        return render_template("bench.html", bench=bench)

    @app.get("/benches/<bench_id>/adopt")
    def adoption_form(bench_id: str):
        bench = get_bench(db(), bench_id)
        if bench is None:
            abort(404)
        if bench["adoption_id"] is not None:
            return redirect(url_for("bench_detail", bench_id=bench_id))
        return render_template("adopt.html", bench=bench, values={}, error=None)

    @app.post("/benches/<bench_id>/review")
    def review_adoption(bench_id: str):
        bench = get_bench(db(), bench_id)
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
            adoption_id = create_adoption(db(), bench_id, **values)
        except BenchUnavailable as error:
            bench = get_bench(db(), bench_id)
            return render_template("booking_error.html", bench=bench, error=str(error)), 409
        except BookingError as error:
            bench = get_bench(db(), bench_id)
            if bench is None:
                abort(404)
            return render_template("adopt.html", bench=bench, values=values, error=str(error)), 400
        return redirect(url_for("confirmation", adoption_id=adoption_id), code=303)

    @app.get("/adoptions/<int:adoption_id>")
    def confirmation(adoption_id: int):
        adoption = get_adoption(db(), adoption_id)
        if adoption is None:
            abort(404)
        return render_template("confirmation.html", adoption=adoption)

    return app

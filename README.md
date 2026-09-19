# Bench by Bench

A responsive bench-adoption service for Van Cortlandt Park. Visitors can explore a prototype geographic map of the bench inventory, filter by availability, see current or future adoptions, and reserve an available bench for chosen calendar dates and a recorded USD amount. No online payment is taken.

## Run locally

Use Python 3.13 (the version in `.python-version`):

```sh
uv sync
cp .env.example .env
# Edit .env and replace the example DATABASE_URL with your Neon pooled URL.
uv run python -m columbia_ss.admin migrate
uv run python -m columbia_ss.admin seed
uv run columbia-ss
```

Open <http://127.0.0.1:5000>. Local development loads `DATABASE_URL` from the ignored `.env` file, while Vercel supplies the same variable through Project Settings. Both environments exercise the same Postgres persistence code. Bench1–Bench30 receive varied active and future initial timelines; Bench31 is available for exercising the booking flow. All 550 benches receive stable generated coordinates grouped across 11 park areas. These are prototype positions, not surveyed bench locations.

## Test

```sh
uv run python -m unittest discover -s tests -v
```

## Adoption rules

- A booking uses the real current date in `America/New_York`. The donor chooses a start date no earlier than today and an end date after the start date.
- The end date is inclusive. The bench becomes available the next day.
- A future-dated booking reserves the bench immediately. The directory labels it **Adopted** and displays its dates.
- The amount is stored exactly as integer cents; it is not a payment. A public name is stored for each booking, without contact details or accounts.
- A booking is committed in one Postgres transaction with a bench-row lock, so a competing submission cannot also reserve the same bench.
- Public bookings must end within 90 days of the current New York date.

The app uses three tables: `benches`, `adopters`, and `adoptions`. Each bench stores the generated latitude and longitude used by the Leaflet and OpenStreetMap view.

## Hosted site on Vercel

The public site is available at <https://columbia-ss.vercel.app/>.

The root `app.py` exports the Flask application for Vercel. Select the `columbia-ss` database in the Neon project, then set `DATABASE_URL` to its **pooled** Postgres connection string locally and in both the Preview and Production Vercel environments. **Use the same database URL in both Vercel environments**: bookings and resets are shared. The app refuses to start anywhere without `DATABASE_URL`. Keep the URL out of Git.

After creating the Neon database, run these commands from the repository root with `DATABASE_URL` set in your shell:

```sh
uv run python -m columbia_ss.admin migrate
uv run python -m columbia_ss.admin seed
```

`migrate` creates the three tables and index, adds coordinate columns to existing installations, and backfills any missing prototype positions. `seed` adds 550 benches and 30 initial adoptions in one transaction. Running either command again preserves existing bookings. App startup does neither operation.

To generate new timelines for the 30 initial adoptions without changing visitor bookings, run:

```sh
uv run python -m columbia_ss.admin refresh-timelines
```

The command first verifies that all 30 expected initial records are present. If that check fails, it changes nothing.

To verify Postgres behavior before deployment, set `TEST_DATABASE_URL` to a **direct, non-pooled** connection string for a database where you can create a temporary schema, then run the test command above. The integration tests create and remove their own uniquely named schema and cover concurrent booking and reset. The direct URL is needed because the tests use a session-level `search_path`. Without `TEST_DATABASE_URL`, those tests are skipped.

To reset the **shared** application database manually:

```sh
uv run python -m columbia_ss.admin reset --yes
```

The reset deletes all visitor and initial bookings and adopters, then restores the starting state in one transaction. It affects Preview and Production immediately. There is no public reset endpoint. Run it only when you intend to clear all bookings.

Before opening the public site, configure a Vercel Firewall rate limit for `POST /benches/*/confirm`, test it on Preview, and review the public name display policy. Use `vercel dev` with a configured database to test the hosted entry point, deploy a Preview, and verify browsing, CSS, booking, concurrency, and persistence across a redeploy before promoting Production. The stylesheet is in `public/static/style.css` for Vercel static serving.

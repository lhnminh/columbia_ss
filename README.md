# Bench by Bench

A responsive bench-adoption demo for a **fictional** inventory inspired by Van Cortlandt Park. Visitors can search 550 sample benches, see current or future adoptions, and reserve an available bench for chosen calendar dates and a recorded USD amount. No payment is taken.

## Run locally

Use Python 3.13 (the version in `.python-version`):

```sh
uv sync
uv run columbia-ss
```

Open <http://127.0.0.1:5000>. The app creates `instance/benches.sqlite3` on first run and seeds Bench1 through Bench550. Bench1–Bench30 have fictional sample adoptions; Bench31 is available for trying the booking flow. The local database persists bookings between restarts. To start over, remove only `instance/benches.sqlite3` while the server is stopped, then run the app again.

Set `COLUMBIA_SS_DB` to an alternate SQLite file path if you want to keep a separate demo database.

## Test

```sh
uv run python -m unittest discover -s tests -v
```

## Demo rules

- A booking uses the real current date in `America/New_York`. The donor chooses a start date no earlier than today and an end date after the start date.
- The end date is inclusive. The bench becomes available the next day.
- A future-dated booking reserves the bench immediately. The directory labels it **Adopted** and displays its dates.
- The amount is stored exactly as integer cents; it is not a payment. A public name is stored for each booking, without contact details or accounts.
- A booking is committed in one SQLite write transaction so a competing submission cannot also reserve the same bench.
- Public bookings must end within 90 days of the current New York date.

The app uses three tables: `benches`, `adopters`, and `adoptions`. This is a demo, not a real park inventory or payment service.

## Hosted demo on Vercel

The public demo is available at <https://columbia-ss.vercel.app/>.

The root `app.py` exports the Flask application for Vercel. Select the `columbia-ss` database in the Neon project, then set `DATABASE_URL` to its **pooled** Postgres connection string in both the Preview and Production Vercel environments. **Use the same database URL in both environments**: bookings and resets are shared. The app refuses to start on Vercel without `DATABASE_URL`, rather than writing to temporary SQLite storage. Keep the URL out of Git.

After creating the Neon database, run these commands from the repository root with `DATABASE_URL` set in your shell:

```sh
uv run python -m columbia_ss.admin migrate
uv run python -m columbia_ss.admin seed
```

`migrate` creates the three tables and index. `seed` adds 550 fictional benches and 30 sample bookings in one transaction. Running either command again preserves existing bookings. App startup does neither operation.

To verify Postgres behavior before deployment, set `TEST_DATABASE_URL` to a **direct, non-pooled** connection string for a database where you can create a temporary schema, then run the test command above. The integration tests create and remove their own uniquely named schema and cover concurrent booking and reset. The direct URL is needed because the tests use a session-level `search_path`. Without `TEST_DATABASE_URL`, those tests are skipped.

To reset the **shared** demo database manually:

```sh
uv run python -m columbia_ss.admin reset --yes
```

The reset deletes all visitor and sample bookings and adopters, then restores the fictional starting state in one transaction. It affects Preview and Production immediately. There is no public reset endpoint. Run it only when you intend to clear all bookings.

Before opening the public site, configure a Vercel Firewall rate limit for `POST /benches/*/confirm`, test it on Preview, and review the public name display policy. Use `vercel dev` with a configured database to test the hosted entry point, deploy a Preview, and verify browsing, CSS, booking, concurrency, and persistence across a redeploy before promoting Production. The stylesheet is in `public/static/style.css` for Vercel static serving.

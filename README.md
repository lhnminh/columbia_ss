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

The app uses three tables: `benches`, `adopters`, and `adoptions`. This is a demo, not a real park inventory or payment service.

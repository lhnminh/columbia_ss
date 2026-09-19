# Future plan: deploy the bench demo to Vercel

## Migration decision

Keep the Flask frontend and booking flow, but standardize all environments on **Neon Postgres**. Vercel supports Flask and Python 3.13, while a local SQLite file cannot provide durable, shared booking state across Vercel Functions. Neon is the selected database provider for this migration. See the [Flask deployment guide](https://vercel.com/docs/frameworks/backend/flask), [Python runtime guide](https://vercel.com/docs/functions/runtimes/python), and [Neon integration](https://vercel.com/integrations/neon).

This is a future deployment project, not a change to the current local demo. It is **not** a configuration-only deploy: the database layer and initialization flow need work first.

## Work packages

1. **Make the app deployable.** Add a Vercel-recognized `app` entry point that calls `create_app()` without starting Flask's development server. Keep `uv run columbia-ss` for local use. Confirm Vercel builds the project with Python 3.13 and the dependencies in `pyproject.toml`. Move the stylesheet to `public/static/style.css` so its existing `/static/style.css` URL can be served as a static asset. Vercel documents both the entry-point convention and `public/**` static assets in its [Flask guide](https://vercel.com/docs/frameworks/backend/flask).
2. **Add persistent storage.** Provision Neon Postgres, then implement the existing `benches`, `adopters`, and `adoptions` schema there. Keep the same public name, inclusive date range, and integer-cent amount rules. Use the same `DATABASE_URL`-configured Postgres path locally and on Vercel. Use a transaction that locks the selected bench row before checking and inserting a booking; preserve the current guarantee that only one unexpired booking can reserve a bench. Use Neon's pooled connection string for Vercel Functions. See [Postgres on Vercel](https://vercel.com/docs/postgres) and [Neon pooling](https://neon.com/docs/connect/connection-pooling).
3. **Move initialization out of app startup.** Use a repeatable Postgres schema migration and a separate, idempotent seed command in every environment. Run them explicitly, not on every process start. Start with fresh fictional data.
4. **Configure environments.** Give Preview and Production the same Neon database connection, set credentials through Vercel environment variables, and keep secrets out of Git. Test with `vercel dev`, then deploy a Preview before Production. Preview tests and resets affect Production data. Vercel documents [environment-specific variables](https://vercel.com/docs/environment-variables) and the [preview-to-production workflow](https://vercel.com/docs/projects/deploy-from-cli).
5. **Verify and protect the public demo.** On Preview, test directory/search/filter pages, CSS loading, adoption review and confirmation, persistence after a new deployment, New York date boundaries, exact amounts, and two simultaneous bookings for one bench. Keep the site public, add a manual operator reset, cap booking dates, and rate-limit confirmations before opening it broadly. Vercel offers [rate limiting](https://vercel.com/docs/vercel-firewall/vercel-waf/rate-limiting). Only promote after the Preview checks pass.

## Completion criteria

- The deployed site retains bookings across requests, function instances, and redeployments.
- Local development, Preview, and Production all use Postgres; no environment has a SQLite fallback.
- The three-table relationships and no-overlapping-booking rule work under concurrent requests.
- The responsive pages and static stylesheet load at the public URL.
- Booking dates and amounts behave exactly as they do locally, and no payment is collected.
- The local `uv run columbia-ss` workflow and automated tests still work.

## Decisions before implementation

- Provision one Neon database and configure its URL for both Preview and Production.
- Start with fresh fictional bookings; do not import local demo bookings.
- Keep the hosted demo public. Add an operator-only manual reset command, a booking horizon, and rate limiting for confirmations.

Rough effort: **2–4 engineering days** for the app/database changes and verification, plus provider setup and any review or approval time. This is an estimate, not a deployment commitment.

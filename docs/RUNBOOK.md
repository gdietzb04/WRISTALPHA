# WRISTALPHA local runbook

## Safety posture

WRISTALPHA is single-user and local-first. Published ports bind to loopback. Forecasts are
statistical estimates derived partly from biased and stale ask prices; they are not investment
advice. Rankings remain disabled until walk-forward rank IC is positive, statistically
distinguishable from zero, and all net-cost assumptions are sourced.

## First start

1. Copy .env.example to .env.
2. Replace the database password with a long URL-safe local secret.
3. Fill only sourced values in config/default.yaml. Unknowns remain null.
4. Start Docker Desktop.
5. Run docker compose up --build -d.
6. Open http://127.0.0.1:5173; API health is http://127.0.0.1:8000/health.

The API applies Alembic migrations before starting. The scheduler runs one instance, coalesces
missed jobs, and reports a blocked outcome when required configuration is absent.

## Source acquisition

HTML sources are disabled until the URL and every CSS selector are verified against the live
source and robots.txt permits access. A 403 or 429 stops acquisition immediately. Do not add
CAPTCHA solving, proxy rotation, IP rotation, session spoofing, or aggressive retries. Switch to a
licensed API or a manual CSV when a source blocks automation.

Auction results from Phillips, Christie's, Sotheby's, and Antiquorum use the documented auction
CSV adapter and are stored as verified transaction anchors. Never convert a delisted listing into
a sale.

## Verification

Run uv sync --frozen --extra dev, then ruff check, ruff format --check, mypy, and pytest with
coverage. In frontend run npm ci and npm run build. Validate with docker compose config.

With Docker running, also run docker compose up --build -d db, alembic upgrade head, alembic
check, and a downgrade/upgrade cycle against a disposable database.

## Recovery

- Acquisition blocked: inspect the structured warning and use licensed API or CSV.
- Database unavailable: confirm Docker Desktop, .env, and docker compose ps.
- Migration failed: preserve the volume, capture logs, and do not stamp the database manually.
- Model verdict non-actionable: do not override it; acquire more verified data and rerun validation.
- Data-quality failure: fix the source or transform and rerun from immutable raw inputs.

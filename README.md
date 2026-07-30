# WRISTALPHA

WRISTALPHA is a single-user, local-first research application for luxury-watch asks and verified
transactions. It normalizes source data, constructs hedonic reference indices, builds
point-in-time features, forecasts returns with uncertainty, validates rankings out of sample,
tracks holdings, and gates recommendations and alerts behind statistical and data-quality checks.

Marketplace listings are biased asks, not transactions. Delisting is ambiguous and never becomes
a sale automatically. Forecasts are statistical estimates, not investment advice.

## Implemented phases

- P0: reproducible Python/Node builds, Docker Compose, CI, strict linting and typing.
- P1: point-in-time SQLAlchemy schema, Alembic migrations, adapter contract, licensed-API stub,
  and manual listing CSV.
- P2: robots-aware Playwright HTML infrastructure, jittered rate limiting, exponential backoff,
  fail-closed 403/429 handling, content-addressed raw cache, and first-class auction CSV results.
- P3: conservative cleaning, exact-first reference resolution, logged winsorization, hedonic
  time-dummy indices, standard errors, thin-reference shrinkage, and data-quality gates.
- P4: point-in-time momentum, volatility, liquidity, price-cut, retail-premium, brand, and sourced
  macro features with database look-ahead protection.
- P5: LightGBM ranking, ARIMA/EGARCH, three-state Markov regime model, ensemble forecasts, purged
  walk-forward validation, and an explicit non-actionable verdict.
- P6: budget/liquidity/concentration constrained recommendations plus deduplicated, rate-limited
  alerts.
- P7: FastAPI dashboard projection and responsive React research terminal with portfolio,
  next-buy, reference uncertainty, and model-health views.
- P8: scheduler, structured logging, loopback-only deployment, automatic migrations, CI, and the
  operations runbook.

## Start locally

1. Copy .env.example to .env and replace the placeholder with a long URL-safe local password.
2. Keep unknown values null in config/default.yaml until a source is available.
3. Start Docker Desktop.
4. Run docker compose up --build -d.
5. Open http://127.0.0.1:5173.

The API health endpoint is http://127.0.0.1:8000/health. Operational procedures and recovery
steps are in docs/RUNBOOK.md.

## Manual listing CSV

Required columns:

source, external_id, fetched_at, title, price, currency, url

Optional columns:

brand, reference_hint, production_year, condition, box, papers, seller_type, seller_country,
vat_included, warranty_remaining_months, service_history, description

Timestamps require a UTC offset. Unknown values stay empty.

## Manual auction CSV

Required columns:

auction_house, external_id, sold_at, realized_price, currency, source_url, title

Optional columns:

hammer_price, buyer_premium, lot_number, sale_name, brand, reference_hint

Supported houses are Phillips, Christie's, Sotheby's, and Antiquorum. Values must come from
verified result records; no fee or realized-price field is inferred.

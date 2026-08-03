# WRISTALPHA

WRISTALPHA is a single-user, local-first research application for luxury-watch asks and verified
transactions. It normalizes source data, constructs hedonic reference indices, builds
point-in-time features, forecasts returns with uncertainty, validates rankings out of sample,
tracks holdings, and gates recommendations and alerts behind statistical and data-quality checks.

Marketplace listings are biased asks, not transactions. Delisting is ambiguous and never becomes
a sale automatically. Forecasts are statistical estimates, not investment advice.

## Start

On Windows, double-click **Start WRISTALPHA.cmd** or run:

```powershell
.\wristalpha.ps1 start
```

The launcher starts Docker Desktop when necessary, creates a protected local database secret on
first use, pulls the GitHub-built images, verifies their build provenance, waits for every service
to become healthy, and opens http://127.0.0.1:5173. It requires Docker Desktop and an authenticated
GitHub CLI (`gh auth login`) so image attestations can be verified before execution.

Common operations:

```powershell
.\wristalpha.ps1 status
.\wristalpha.ps1 logs
.\wristalpha.ps1 update
.\wristalpha.ps1 stop
```

Use `.\wristalpha.ps1 rebuild` only when testing local source changes. Normal startup never builds
images on your machine. Operational procedures and recovery guidance are in
[docs/RUNBOOK.md](docs/RUNBOOK.md).

## Security posture

- API, database, and dashboard ports bind only to `127.0.0.1`.
- Database credentials live in a Git-ignored, ACL-protected secret file and are mounted only into
  services that need them.
- Release images are built by SHA-pinned GitHub Actions, include SBOM/provenance metadata, and are
  verified by the launcher before execution.
- Application containers run without Linux capabilities, cannot gain privileges, and use
  read-only root filesystems.
- The launcher never deletes the database volume, weakens source blocking, fabricates
  transactions, or overrides data-quality and model-actionability gates.

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

## Manual imports

Listing CSV required columns:

```text
source, external_id, fetched_at, title, price, currency, url
```

Optional listing columns:

```text
brand, reference_hint, production_year, condition, box, papers, seller_type, seller_country,
vat_included, warranty_remaining_months, service_history, description
```

Auction CSV required columns:

```text
auction_house, external_id, sold_at, realized_price, currency, source_url, title
```

Optional auction columns:

```text
hammer_price, buyer_premium, lot_number, sale_name, brand, reference_hint
```

Supported auction houses are Phillips, Christie's, Sotheby's, and Antiquorum. Values must come
from verified result records; no fee or realized-price field is inferred.

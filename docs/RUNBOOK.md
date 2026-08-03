# WRISTALPHA local runbook

## Safety posture

WRISTALPHA is single-user and local-first. Published ports bind to loopback. Forecasts are
statistical estimates derived partly from biased and stale ask prices; they are not investment
advice. Rankings remain disabled until walk-forward rank IC is positive, statistically
distinguishable from zero, and all net-cost assumptions are sourced.

## First start

Prerequisites:

- Docker Desktop
- GitHub CLI authenticated with `gh auth login`

Then double-click `Start WRISTALPHA.cmd` or run:

```powershell
.\wristalpha.ps1 start
```

The launcher:

1. Starts Docker Desktop if necessary.
2. Generates a 256-bit local database secret, or migrates a strong password from an existing
   `.env` without changing it.
3. Validates the Compose model.
4. Pulls the API and frontend images from GitHub Container Registry.
5. Verifies both GitHub build attestations and fails closed if verification fails.
6. Starts the stack and waits for database, API, and frontend health checks.
7. Opens http://127.0.0.1:5173 only after the API reports healthy.

The API applies Alembic migrations before starting. The scheduler runs one instance, coalesces
missed jobs, and reports a blocked outcome when required source configuration is absent.

## Operations

```powershell
.\wristalpha.ps1 status
.\wristalpha.ps1 logs
.\wristalpha.ps1 update
.\wristalpha.ps1 stop
```

`update` pulls and verifies current release images before recreating changed services. `stop`
preserves containers and the database volume. No launcher command deletes stored data.

To test source changes locally:

```powershell
.\wristalpha.ps1 rebuild
```

This is the only launcher command that invokes the local Docker builder. Local builds do not carry
GitHub attestations and are deliberately separate from normal release startup.

To run a specific attested release, set `WRISTALPHA_IMAGE_TAG` to its release or `sha-...` tag
for the current PowerShell session, then run `start`.

## Secret handling

The generated password is stored at `.wristalpha/secrets/postgres_password`, which is ignored by
Git and restricted to the current Windows user and the local system account. Compose mounts it as
a file only into PostgreSQL, API, and scheduler containers. It is not placed in Compose metadata,
command-line arguments, or logs.

Do not copy this secret into source-controlled configuration. If restoring an existing PostgreSQL
volume, restore its matching secret as well.

## Image release

Merges to `main` build API and frontend images in GitHub Actions. The workflow uses
least-privilege `GITHUB_TOKEN` permissions, immutable action SHAs, BuildKit provenance, an SBOM,
and GitHub artifact attestations. The resulting packages must remain connected to this repository.

GitHub creates new GHCR packages as private. After the first successful publication, an
administrator must make `wristalpha-api` and `wristalpha-frontend` public once so the public
launcher can pull them anonymously. GitHub does not allow a public package to be made private
again; treat that one-time setting as an explicit release decision.

## Source acquisition

HTML sources remain disabled until the URL and every CSS selector are verified against the live
source and robots.txt permits access. A 403 or 429 stops acquisition immediately. Do not add
CAPTCHA solving, proxy rotation, IP rotation, session spoofing, or aggressive retries. Switch to a
licensed API or a manual CSV when a source blocks automation.

Auction results from Phillips, Christie's, Sotheby's, and Antiquorum use the documented auction
CSV adapter and are stored as verified transaction anchors. Never convert a delisted listing into
a sale.

## Verification

Backend:

```powershell
uv sync --frozen --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=wristalpha --cov-report=term-missing
```

Frontend:

```powershell
cd frontend
npm ci
npm run build
```

Validate both Compose models with a disposable secret file before using them. Test migrations
against a disposable database and preserve production/local research volumes during recovery.

## Recovery

- Image verification failed: do not bypass it; inspect the GitHub publication run and attestation.
- GHCR pull denied: confirm both packages are public or authenticate Docker to the authorized
  registry account.
- Database authentication failed after upgrading: restore the password that initialized the
  existing volume; do not delete the volume.
- Acquisition blocked: inspect the structured warning and use a licensed API or CSV.
- Migration failed: preserve the volume, capture logs, and do not stamp the database manually.
- Model verdict non-actionable: do not override it; acquire more verified data and rerun validation.
- Data-quality failure: fix the source or transform and rerun from immutable raw inputs.

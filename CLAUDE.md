# Being Watched — Project Context

This file is read automatically by Claude Code at the start of every session
in this repo. Keep it updated as the project evolves — it's the persistent
memory that replaces claude.ai Project instructions for local work.

## What this is

A personal daily investing dashboard, built primarily as a **data engineering
and analytics engineering learning project** — not a product. Three explicit
goals, in priority order:

1. Deep hands-on skill building (SQL-first, since that's the strongest skill;
   Python is a growth area)
2. A logically sound, defensible ELT workflow
3. Real data quality and validation throughout, not bolted on at the end

Secondary framing: this started life as an "investment news & signal
monitoring tool" idea — explicitly an **information monitoring / awareness
tool, not a prediction model**. It answers "what happened and where should I
look," never "what will happen." Keep that boundary in any feature that gets
added later (alerts, digests, etc.) — no forecasting, no trading signals
framed as predictions.

Career context: this project targets the analytics-engineer skill stack
(SQL-heavy, dbt, warehouse, light Python) as a portfolio artifact.

## Dashboard scope (five sections)

- **Bond Market & Market Open Indicators** — Treasury yields, DXY, index futures
- **Macroeconomic Indicators** — CPI, Core PCE, NFP (+ optional unemployment,
  average hourly earnings)
- **Market Sentiment** — SPX, Nasdaq, DJIA, VIX
- **Sector Leaders** — NVDA, AAPL, MSFT, AMZN + ETFs (QQQ, SMH, XLK)
- **Personal Watchlist**

## Architecture

**Pattern: ELT, not ETL.** Extract and Load are plain Python, outside dbt.
Transform is dbt, and dbt only ever transforms — it never extracts or loads.

```
API → raw table (untouched) → staging model (light cleanup) → mart (fact/dim) → tests
```

- **Data sources (three-API architecture, deliberately chosen over yfinance):**
  - **Polygon/Massive** — market data (prices, indices, futures, sector leaders, watchlist)
  - **FRED** — macroeconomic data (CPI, Core PCE, NFP, Treasury yields)
  - **Finnhub** — supplemental market data, economic calendar
  - yfinance was explicitly rejected: unofficial/scraping-based, no clear
    personal-use licensing. Preference throughout is official, licensed APIs
    even at added cost.
- **Warehouse:** DuckDB, local file (`warehouse.duckdb`). Zero setup, free,
  standard SQL. Migrate to BigQuery later once the logic is proven, for the
  "cloud warehouse" resume line.
- **Ingestion:** Python (`requests` to start; `dlt` planned later for
  pagination/incremental loading).
- **Transformation:** dbt-core + `dbt-duckdb` adapter. Three-layer DAG:
  **staging → intermediate → marts**. Star schema dimensional model.
- **Orchestration:** cron first. Do not reach for Airflow/Dagster until cron
  and the pipeline pattern are proven.
- **Version control:** git. Non-negotiable for portfolio credibility.

## Reference documents

- `docs/API_INGESTION_SPEC.md` — authoritative source contract for API
  ingestion across Massive/Polygon, FRED, and Finnhub: exact fields to
  capture per endpoint, transformation formulas, refresh cadence, and
  data-quality/reconciliation rules. This file is **not** auto-loaded the
  way CLAUDE.md is — consult it explicitly before writing or modifying any
  ingestion or transformation code, and keep it in sync with the pipeline
  as it changes.

## Key modeling decisions (don't relitigate these without a good reason)

- **Grain discipline drives table design.** CPI, Core PCE, and NFP each get
  their **own fact table** (`fct_cpi`, `fct_core_pce`, `fct_nfp`) rather than
  one consolidated macro table — different release cadences and structures
  mean forcing them together would blur the grain.
- **Every fact table must have a one-sentence grain statement.** E.g. for
  Treasury yields: *one yield reading, for one maturity, on one date.* If the
  grain can't be stated cleanly, the table is designed wrong.
- **Raw data is the source of truth.** Land it untouched first. If a
  transformation has a bug, fix the SQL and re-run against the same raw
  data — never re-hit the API to recover. Casting/type conversion is a
  transformation and belongs in staging, not in the loader (e.g. FRED's `.`
  for missing values is stored as-is in raw, converted to `NULL` in staging).
- **Staging models do only light cleanup** — rename, cast, standardize. No
  joins, no business logic, no aggregation. One staging model per raw source
  table.
- **Intermediate models are added only when needed** — e.g. when pivoting 2Y
  and 10Y yields onto one row to compute the 2s10s spread. Don't add layers
  preemptively.
- **Data quality:** dbt generic tests (`not_null`, `unique`, `accepted_values`,
  `relationships`) plus `dbt-expectations` and `dbt_utils` (e.g. composite
  uniqueness tests on grain columns). Use `dbt build`, not `dbt run` + `dbt test`
  separately — it interleaves tests in DAG order so bad data never reaches
  a downstream model.

## Build philosophy

**Learn by doing, one full vertical slice first.** The current and immediate
focus is building **one complete pipeline end-to-end — FRED Treasury
yields — before touching Polygon or Finnhub.** The goal is to internalize the
full pattern (API → raw → staging → mart → tests → docs) once, then replicate
it for every other source rather than building all pipelines in parallel.

FRED was chosen as the first slice deliberately: official, free,
well-documented, daily-updated, low-volume, no pagination or futures-contract
complexity — it isolates the *pattern* from source-specific edge cases.

## Current status

- Environment setup in progress (Python via Homebrew, `.venv`, dbt-core,
  dbt-duckdb, DuckDB, requests) on macOS with VS Code.
- Project file/folder structure:
  ```
  beingwatched/
  ├── .env                      # FRED_API_KEY (git-ignored)
  ├── .gitignore
  ├── docs/
  │   └── API_INGESTION_SPEC.md   # authoritative ingestion contract, see below
  ├── ingestion/
  │   ├── fred_client.py          # shared fetch/hash helpers used by all FRED loaders
  │   ├── load_fred_yields.py     # DGS2 + DGS10 observations, plus series metadata
  │   ├── load_fred_cpi.py        # CPIAUCSL (headline) + CPILFESL (core)
  │   ├── load_fred_pce.py        # PCEPI (headline) + PCEPILFE (core)
  │   └── load_fred_nfp.py        # PAYEMS
  └── dbt/
      ├── dbt_project.yml
      ├── profiles.yml
      ├── packages.yml
      └── models/
          ├── staging/
          │   ├── _sources.yml
          │   ├── stg_fred__yields.sql
          │   ├── stg_fred__cpi.sql
          │   ├── stg_fred__pce.sql
          │   ├── stg_fred__nfp.sql
          │   ├── stg_fred__series_meta.sql   # unions series-meta across all 4 domains
          │   └── _staging.yml
          ├── intermediate/
          │   ├── int_treasury_yields_pivoted.sql
          │   └── _intermediate.yml
          └── marts/
              ├── fct_treasury_yields.sql
              ├── fct_treasury_spread.sql
              ├── fct_cpi.sql
              ├── fct_core_pce.sql
              ├── fct_nfp.sql
              └── _marts.yml
  ```
- FRED Treasury yields slice is complete and spec-compliant end-to-end:
  raw layer captures the full contract from `docs/API_INGESTION_SPEC.md`
  §4.4 (per-observation vintage window, request/response metadata,
  payload hash, full raw payload, plus series metadata from a second
  endpoint), staging does light cleanup only, an intermediate model
  pivots 2Y/10Y onto one row (the one case CLAUDE.md's own rules call
  out as justifying an intermediate model), and `fct_treasury_spread`
  computes the 2s10s spread and inversion flag.
- Macro fact tables (`fct_cpi`, `fct_core_pce`, `fct_nfp`) are built,
  replicating the same raw → staging → mart pattern via the shared
  `ingestion/fred_client.py` helpers. `fct_cpi` holds both headline and
  core CPI (long format, one row per measure per month, mirroring the
  `maturity_label` pattern in `fct_treasury_yields`) with MoM/YoY computed
  via `lag()` windows partitioned by measure. `fct_core_pce` is core-only
  per the locked modeling decision below; headline PCE (`PCEPILFE`'s
  sibling, `PCEPI`) is ingested and staged (`stg_fred__pce`) but has no
  mart yet since the dashboard scope only calls for Core PCE — revisit if
  that scope changes. `fct_nfp` holds the PAYEMS level plus
  `change_thousands` (never the level itself) via `lag()`. `mom_pct`/
  `yoy_pct`/`change_thousands` are legitimately null for the earliest
  1–12 months of history (no prior period to compare against) — this is
  expected, not a data quality bug.
- `dbt build` passes with 54 tests (0 errors) across 11 models; source
  freshness checks pass on all 8 raw tables (4 domains × observations +
  series metadata each).

## Conventions to follow

- Raw tables live in a `raw` schema, prefixed `raw_<source>__<entity>`
  (e.g. `raw.raw_fred__yields`).
- Staging models: `stg_<source>__<entity>` (e.g. `stg_fred__yields`),
  materialized as views.
- Marts: `fct_` for fact tables, `dim_` for dimension tables, materialized
  as physical tables.
- Every source table gets a freshness check (`warn_after` / `error_after`)
  to catch silent ingestion failures.
- API keys and secrets always via `.env`, never hardcoded, always
  git-ignored.
- Don't skip layers or add speculative complexity (no intermediate models,
  no orchestrator beyond cron, no incremental loading) until the simple
  version is proven working.

## Next steps after this slice works

1. `dim_dates` + `dim_tickers` — the shared spine other facts join to
2. Polygon prices pipeline → `fct_prices` (indices, sector leaders, ETFs, watchlist)
3. ~~Macro fact tables → `fct_cpi`, `fct_core_pce`, `fct_nfp`~~ — done
4. Finnhub economic calendar → `fct_economic_calendar`
5. Polygon futures → `fct_futures`
6. Incremental loading (replace drop-and-reload with append-only)
7. cron scheduling, then evaluate a real orchestrator

# Market Metrics — API Ingestion Reference

**Status:** Implementation-ready source contract
**Prepared for:** Mia's market monitoring pipeline
**As of:** 2026-07-27
**Cadence:** Hourly market refresh · daily macro refresh · economic-calendar polling
**Primary stack:** Massive (formerly Polygon.io) + FRED + Finnhub → dbt transformation layer

---

## How Claude Code should use this file

This document is the **authoritative ingestion contract** for the project. When writing or modifying ingestion code, treat it as the source of truth over any assumption or shortcut:

1. **Ingest every field listed in Section 4**, not just the fields a current dashboard displays. The raw layer is append-only and schema-complete by design — this is what avoids re-ingestion/backfill work later when a new metric or transformation needs a field that wasn't captured the first time.
2. **Never mutate or overwrite raw rows.** Corrections, revisions, and re-runs are handled by inserting new versioned rows (see Section 6), not by updating history in place.
3. **Do not use yfinance** or any unlisted source as a production data path.
4. When adding a new metric, extend the matrix in Section 3 and the relevant contract in Section 4 *before* writing the loader — don't let ad-hoc fields diverge from this file.
5. If a transformation rule changes, update Section 5 in the same PR as the code change. This file should never drift from what the pipeline actually does.

---

## 1. Scope and assumptions

**Watchlist:** U.S. 2-year and 10-year Treasury yields and their spread; U.S. Dollar Index (DXY); S&P 500, Nasdaq, Dow, VIX; S&P 500, Nasdaq-100, and Dow futures; QQQ, SMH, XLK; NVDA, AAPL, MSFT, AMZN; headline/core CPI, headline/core PCE, nonfarm payrolls.

**Naming decision:** "Nasdaq" = Nasdaq Composite (`I:COMP`). Nasdaq futures = E-mini Nasdaq-100 (`NQ`), which tracks a *different* index (Nasdaq-100, not Composite). Keep these two metrics separately named everywhere in the warehouse and dashboard — do not conflate them.

## 2. Provider decision

| Data domain | API | Why this source | Plan / access decision |
|---|---|---|---|
| Market prices — stocks, ETFs, indices, DXY | Massive | Directly sourced/normalized market feeds; consistent OHLC schemas; hourly and real-time options | Stocks Developer + Indices Starter for hourly monitoring (15-min delay). Upgrade to Stocks Advanced + Indices Advanced for real time. |
| Equity-index futures — ES, NQ, YM | Massive Futures | Contract metadata + contract-level OHLCV in one provider; native 1-hour resolution | Futures Developer = 10-min delayed; Futures Advanced = real time. Never hardcode one expiring contract. |
| Historical macro actuals — rates, CPI, PCE, payrolls | FRED | Federal Reserve Bank of St. Louis API with vintages/revision dates and authoritative series metadata | Free API key. Load raw levels and vintage fields; calculate rates of change downstream. |
| Upcoming releases — consensus and surprise | Finnhub Economic Calendar | Forward schedule plus estimate, previous, and actual values | Premium entitlement required. Poll repeatedly around release time and preserve every snapshot. |

**Baseline rule for every raw request:** store `source_name`, `endpoint`, `request_id`, `fetched_at_utc`, `response_status`, `payload_hash`, `next_url`/`cursor`, and the complete raw JSON payload — in addition to the promoted fields below. The "promoted columns" in Section 3 are the *minimum* typed fields dbt needs; Section 4 lists everything the raw layer must retain regardless of whether it's promoted yet.

## 3. Metric-to-source matrix

| Metric | API / identifier | Metric logic | Downstream transformation / guardrail |
|---|---|---|---|
| U.S. 2Y Treasury yield | FRED `series_id=DGS2` | Daily level: cast `observation.value` to decimal percent. Latest valid observation is the display value. | Preserve `realtime_start`/`realtime_end`. Do not fill weekends in raw. In marts, forward-fill only with `is_stale=true` and `age_days`. |
| U.S. 10Y Treasury yield | FRED `series_id=DGS10` | Same as 2Y. | Same freshness logic as 2Y. Optionally reconcile against Massive `/fed/v1/treasury-yields`. |
| 10Y minus 2Y spread | Derived from DGS10 and DGS2 | `spread_bps = (yield_10y_pct - yield_2y_pct) × 100` on the same observation date. | Inner join on date; never subtract values from different dates. Store `inversion_flag = spread_bps < 0`. |
| U.S. Dollar Index (DXY) | Massive Indices, expected `I:DXY` | Hourly OHLC index values. Latest close is the display level; `hourly_return = close / lag(close) - 1`. | Resolve ticker once through `/v3/reference/tickers` search and **fail deployment** if it does not map to the licensed U.S. Dollar Index. |
| S&P 500 futures | Massive Futures `product_code=ES` | 1-hour contract OHLCV; active front-contract series for dashboard, settlement for daily comparison. | Build contract selector and continuous series. Preserve contract bars unadjusted. Track roll gap and roll date. |
| Nasdaq-100 futures | Massive Futures `product_code=NQ` | Same as ES. Display name must say **Nasdaq-100 futures**, not Nasdaq Composite futures. | Same volume-led roll logic and continuous-series fields as ES. |
| Dow futures | Massive Futures `product_code=YM` | Same as ES; contract ticker changes by expiry month. | Same volume-led roll logic and continuous-series fields as ES. |
| S&P 500 | Massive Indices `I:SPX` | Hourly OHLC index level; latest close; hourly and regular-session changes. | Index bars have no trade volume. Do not populate volume with zero — leave null. |
| Nasdaq Composite | Massive Indices `I:COMP` | Hourly OHLC index level; latest close; hourly and regular-session changes. | Keep separate from `I:NDX` and NQ futures. Use exchange calendar for valid sessions. |
| Dow Jones Industrial Average | Massive Indices `I:DJI` | Hourly OHLC index level; latest close; hourly and regular-session changes. | No volume field for index aggregates; retain null. |
| VIX | Massive Indices `I:VIX` | Hourly OHLC index level; latest close and point change. | Treat as an index level, not a return asset. Do not annualize or convert to decimal unless a separate modeled field requires it. |
| QQQ / SMH / XLK | Massive Stocks | Adjusted OHLCV and VWAP. Derive `hourly_return`, `day_return`, `gap_return`, regular-session close. | Use `adjusted=true`. Classify premarket/regular/after-hours; do not mix sessions in a single custom hour. |
| NVDA / AAPL / MSFT / AMZN | Massive Stocks | Adjusted OHLCV and VWAP. Same common market metrics as ETFs. | Same split-adjustment and session logic. Reprocess overlap window after corporate-action corrections. |
| Headline CPI (MoM/YoY) | FRED `CPIAUCSL` + Finnhub calendar | `MoM = 100 × (level/lag_1 - 1)`; `YoY = 100 × (level/lag_12 - 1)`. Finnhub supplies scheduled estimate/actual. | Map calendar rows by country=US, event name, unit, and measure basis. Retain FRED revisions; compare like-for-like SA measures. |
| Core CPI (MoM/YoY) | FRED `CPILFESL` + Finnhub calendar | Same formulas as headline CPI, using core CPI index. | Do not infer core/headline only from event text without a mapping table. Quarantine unknown names. |
| Headline PCE (MoM/YoY) | FRED `PCEPI` + Finnhub calendar | MoM/YoY from index level; calendar fields provide market expectation and release actual. | Validate unit and seasonal-adjustment basis. Keep release period separate from release date. |
| Core PCE (MoM/YoY) | FRED `PCEPILFE` + Finnhub calendar | Same formulas as headline PCE, using core PCE index. | Preserve revised prior value from calendar separately from the stored previous release version. |
| Nonfarm payrolls (monthly change) | FRED `PAYEMS` + Finnhub calendar | `nfp_change_thousands = PAYEMS[t] - PAYEMS[t-1]`. Calendar actual/estimate normally represent the monthly change. | Do not treat PAYEMS level as payroll gain. Store release-period month; track revisions to current and prior months. |

## 4. Raw ingestion contracts — exhaustive field manifests

> Every field listed here must land in the raw layer, even fields not immediately displayed. They exist for auditability, pagination, reconciliation, and later transformation. Dropping a field to "save space" is the exact mistake this document is meant to prevent — it's what forces a re-ingestion pass later.

### 4.1 Massive Stocks — stocks and ETFs

**Endpoint:** `GET /v2/aggs/ticker/{stocksTicker}/range/1/minute/{from}/{to}?adjusted=true&sort=asc&limit=50000`
Minute bars are recommended because downstream hourly bars can be aligned to regular-market boundaries; direct 1/hour bars may mix session regimes.

| Location | Fields to ingest | Purpose |
|---|---|---|
| Root | `ticker`, `adjusted`, `queryCount`, `resultsCount`, `status`, `request_id`, `next_url` | Request audit, adjustment state, completeness, pagination |
| Each `results[]` bar | `t`, `o`, `h`, `l`, `c`, `v`, `vw`, `n`, `otc` | `t` = bar start epoch ms; OHLC; volume; VWAP; transaction count; optional OTC flag |
| Pipeline metadata | `source_name`, `endpoint`, `requested_from`, `requested_to`, `fetched_at_utc`, `payload_hash`, `raw_payload` | Idempotency, lineage, replay, schema-drift protection |

### 4.2 Massive Indices — SPX, COMP, DJI, VIX, DXY

**Endpoint:** `GET /v2/aggs/ticker/{indicesTicker}/range/1/minute/{from}/{to}?sort=asc&limit=50000`
Resolve and store reference metadata via `GET /v3/reference/tickers` **before** enabling an index.

| Location | Fields to ingest | Purpose |
|---|---|---|
| Root | `ticker`, `queryCount`, `resultsCount`/`count`, `status`, `request_id`, `next_url` | Request audit, result counts, pagination. Accept `resultsCount` or `count` defensively. |
| Each `results[]` bar | `t`, `o`, `h`, `l`, `c` | Index bar start epoch ms and OHLC index values. No trade volume exists in this schema. |
| Reference identity | `ticker`, `name`, `market`, `locale`, `active`, `source_feed`; retain full reference payload | Prevents a display label from silently mapping to the wrong licensed index |

### 4.3 Massive Futures — ES, NQ, YM

**Contract discovery:** `GET /futures/v1/contracts?product_code={ES|NQ|YM}&active=true&date={date}`
**Bar endpoint:** `GET /futures/v1/aggs/{contract_ticker}?resolution=1hour&window_start.gte={from_ns}&window_start.lt={to_ns}&limit=50000`

| Location | Fields to ingest | Purpose |
|---|---|---|
| Contract root | `request_id`, `status`, `next_url` | Audit and pagination |
| Each contract | `active`, `date`, `days_to_maturity`, `first_trade_date`, `group_code`, `last_trade_date`, `max_order_quantity`, `min_order_quantity`, `name`, `product_code`, `settlement_date`, `settlement_tick_size`, `spread_tick_size`, `ticker`, `trade_tick_size`, `trading_venue`, `type` | Point-in-time contract selection, roll logic, expiry safety, data validation |
| Bar root | `request_id`, `status`, `next_url` | Audit and pagination |
| Each aggregate bar | `ticker`, `window_start`, `session_end_date`, `open`, `high`, `low`, `close`, `volume`, `transactions`, `dollar_volume`, `settlement_price` | Contract OHLCV, trading date, liquidity, daily settlement reconciliation |

### 4.4 FRED — yields and macro actuals

**Endpoint:** `GET https://api.stlouisfed.org/fred/series/observations?series_id={id}&file_type=json&units=lin&observation_start={date}&realtime_start=1776-07-04&realtime_end=9999-12-31`
For revision-sensitive backfills, use `output_type=2` or targeted `vintage_dates`.

| Location | Fields to ingest | Purpose |
|---|---|---|
| Request identity | `series_id` (from request), `units`, `output_type`, `file_type`, `order_by`, `sort_order` | Reproducible interpretation of the returned values |
| Root | `realtime_start`, `realtime_end`, `observation_start`, `observation_end`, `count`, `offset`, `limit` | Coverage and pagination audit |
| Each `observations[]` row | `date`, `value`, `realtime_start`, `realtime_end` | Observation period, value, and the validity interval of that vintage |
| Series metadata request | `id`, `title`, `observation_start`, `observation_end`, `frequency`, `frequency_short`, `units`, `units_short`, `seasonal_adjustment`, `seasonal_adjustment_short`, `last_updated`, `popularity`, `notes` | Unit and seasonal-adjustment validation; human-readable lineage |

### 4.5 Finnhub Economic Calendar

**Endpoint:** `GET https://finnhub.io/api/v1/calendar/economic?from={YYYY-MM-DD}&to={YYYY-MM-DD}`
Query a rolling window (e.g. 14 days back through 30 days forward); poll more frequently around known U.S. releases.

**Schema-drift rule:** Finnhub calendar events do not expose a durable event ID in the documented payload. Build `event_key_hash` from normalized country, event, scheduled time, and unit — but keep the full source JSON so later schema additions can be backfilled.

| Location | Fields to ingest | Purpose |
|---|---|---|
| Root | `economicCalendar` | Array container; retain full root payload |
| Each event | `actual`, `country`, `estimate`, `event`, `impact`, `prev`, `time`, `unit` | Release value, geography, consensus, name, importance, prior, scheduled time, unit |
| Required pipeline additions | `fetched_at_utc`, `event_key_hash`, `source_event_json`, `event_status`, `mapping_version` | Version history, deterministic identity, replay, controlled mapping |

## 5. Transformation specifications

| Output | Input → model | Logic | Required guardrail / fields |
|---|---|---|---|
| Market hourly bars | `int_market_minute_bars` → `fct_market_hourly` | Convert `t` from epoch ms to UTC and America/New_York. Classify session. Aggregate regular session into 09:30–10:30, 10:30–11:30, etc.; aggregate extended sessions separately. | `open`=first; `high`=max; `low`=min; `close`=last; `volume`=sum; `vwap`=sum(vw×v)/sum(v); `transactions`=sum(n). Do not create bars with no observations. |
| Daily market metrics | `fct_market_hourly` → `mart_market_latest` | `latest_price`=latest eligible close; `previous_regular_close`=last regular close from prior session; `day_change`=latest_price−previous_regular_close; `day_change_pct`=day_change/previous_regular_close | Add `data_as_of_utc`, `source_delay_minutes`, `is_market_open`, `is_stale`, `minutes_since_update` |
| Continuous futures | raw contracts + contract bars → `fct_futures_continuous` | Candidate contracts must be active and outside an expiry safety window. Roll when next contract's daily volume exceeds current contract for two consecutive sessions, or apply a documented fixed-roll policy. | Store `active_contract`, `roll_from`, `roll_to`, `roll_date`, `roll_gap`, `raw_close`, `adjusted_close`, `back_adjustment`. Never overwrite contract bars. |
| Treasury curve | FRED DGS2 + DGS10 → `fct_rates_daily` | Join by `observation_date`; `spread_bps=(DGS10-DGS2)×100` | No cross-date fallback. Forward-filled dashboard rows must carry `source_observation_date` and `is_stale`. |
| Inflation rates | FRED index levels → `fct_macro_observation` | MoM=100×(level/lag1−1); YoY=100×(level/lag12−1). Calculate after sorting by observation period, not ingestion timestamp. | Retain level, derived value, `formula_version`, and vintage validity. Do not ask FRED to return transformed units as the sole stored fact. |
| Nonfarm payroll change | PAYEMS level → `fct_macro_observation` | `change_thousands`=level−lag1(level) | Retain current-month and prior-month revisions by FRED vintage. Never label the PAYEMS level itself as monthly payroll gain. |
| Economic release lifecycle | Finnhub snapshots → `int_release_versions` → current/history marts | `status`=scheduled when actual is null; released when actual is present; revised when a later snapshot changes actual or prev | Append snapshot versions. Build `fct_economic_release_current` for dashboard and `fct_economic_release_history` for audit. |
| Surprise metrics | Release current/history | `surprise`=actual−estimate; `surprise_pct`=(actual−estimate)/abs(estimate) only when estimate≠0 | Keep numeric surprise neutral. Any market-positive/negative interpretation must be metric-specific and versioned. |

## 6. Economic-release state model

Scheduled and actual values belong to the same logical release, but the pipeline should not model them as one mutable raw row. **The raw feed is append-only**; dbt produces a current-state table and a version-history table.

| Model | Grain | Core columns | Purpose |
|---|---|---|---|
| `raw_finnhub_economic_calendar_snapshot` | One API event per fetch time | `event_key_hash`, `fetched_at_utc`, `actual`, `estimate`, `prev`, `country`, `event`, `impact`, `time`, `unit`, `source_event_json` | Immutable ingestion history |
| `dim_economic_metric` | One normalized release measure | `metric_id`, `display_name`, `country`, `event_pattern`, `unit`, `frequency`, `basis`, `directionality`, `mapping_version` | Controlled mapping for headline/core and MoM/YoY distinctions |
| `fct_economic_release_history` | One version per release change | `metric_id`, `release_period`, `scheduled_at_utc`, `version_valid_from`, `version_valid_to`, `estimate`, `previous_reported`, `actual`, `status` | Audit estimate changes, initial actual, and revisions |
| `fct_economic_release_current` | One latest row per metric/release period | All current values plus `surprise`, `surprise_pct`, `released_at_utc`, `last_seen_at_utc` | Simple dashboard consumption |

## 7. Data-quality and reconciliation rules

| Check | Rule | Cadence |
|---|---|---|
| Completeness | Follow `next_url` until null. Compare received row count with `resultsCount`/`count` where provided. Alert on truncated requests. | Every ingestion run |
| Idempotency | Merge market bars on source + ticker + raw bar timestamp; FRED on `series_id` + `observation_date` + `realtime_start` + `realtime_end`; calendar on `event_key_hash` + `fetched_at_utc`. | Every load |
| OHLC validity | `low ≤ min(open, close) ≤ max(open, close) ≤ high`; volume/transactions cannot be negative. | Every bar |
| Freshness | Persist `data_as_of` and expected provider delay. Flag stale rather than silently presenting old values as current. | Every dashboard refresh |
| Missing bars | A missing provider bar is null/missing, not a zero-price or zero-volume bar. Use the exchange calendar before raising an incident. | Every time series |
| Corporate actions | Use `adjusted=true` for stock/ETF charts; re-fetch an overlap window so split adjustments and corrections can update history. | Daily reprocessing |
| Macro unit checks | Validate FRED series units, frequency, and seasonal adjustment against the metadata table before promoting a new series. | On series onboarding and metadata change |
| Cross-source checks | Reconcile DGS2/DGS10 against Massive Treasury daily values when available; compare latest index/futures snapshots with aggregate close within expected timing tolerance. | Daily and on anomalies |
| Release mapping | Quarantine unmapped or ambiguously mapped Finnhub event names. Never default an unknown event to headline/core or MoM/YoY. | Every calendar load |
| Revisions | Never update away a FRED vintage or Finnhub release snapshot. Surface initial vs. latest actual where it matters. | Every macro release |

## 8. Refresh cadence

| Dataset | Cadence | Incremental window | Operational note |
|---|---|---|---|
| Stocks / ETFs / indices / DXY | Every 15 minutes or hourly | Pull with a two-session overlap; transform completed minutes into session-aligned hours | Hourly monitoring does not require a real-time plan; accept the documented delay and expose it |
| Futures bars | Every 10 minutes or hourly | Query active contract(s) with overlap; refresh contract metadata daily | At roll windows, load both current and next contracts |
| FRED yields | Daily after source update | Refresh recent 10 business days; run full vintage backfill on a slower schedule | FRED is not an hourly Treasury-yield feed |
| FRED CPI/PCE/PAYEMS | Daily plus release-day run | Refresh recent observations and vintage metadata; monthly full revision check | Compute derived metrics only after successful series validation |
| Finnhub calendar | Every 6 hours normally; every 5–15 minutes around tracked releases | Rolling past/future date window; append each changed snapshot | Respect plan rate limits and record the fetch timestamp |

**Hourly Treasury limitation:** `DGS2` and `DGS10` are daily series. If an hourly rates signal becomes necessary, add 2-year and 10-year Treasury futures (`ZT` and `ZN`) as explicitly labeled proxies. Do not relabel futures-price movements as hourly cash yields.

## 9. Recommended implementation order

| Phase | Deliverable |
|---|---|
| Phase 1 | Create instrument and metric mapping seeds; implement Massive/FRED/Finnhub raw loaders with full-payload retention |
| Phase 2 | Build normalized market minute bars, contract reference data, FRED vintages, and calendar snapshot history |
| Phase 3 | Build session-aligned hourly bars, daily latest metrics, Treasury spread, macro rates of change, and release surprises |
| Phase 4 | Add continuous futures roll logic, cross-source reconciliation, freshness SLAs, and anomaly alerts |

## 10. Official API references

- FRED series observations: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- Finnhub economic calendar: https://finnhub.io/docs/api/economic-calendar
- Massive stock aggregate bars: https://massive.com/docs/rest/stocks/aggregates/custom-bars
- Massive index aggregate bars: https://massive.com/docs/rest/indices/aggregates/custom-bars
- Massive index overview and source notes: https://massive.com/docs/rest/indices/overview
- Massive futures aggregate bars: https://massive.com/docs/rest/futures/aggregates
- Massive futures contract reference: https://massive.com/docs/rest/futures/contracts
- Massive Treasury yields (reconciliation option): https://massive.com/docs/rest/economy/treasury-yields

Provider schemas, entitlements, and plan pricing can change. Validate the documented response against a sandbox response before production deployment, and treat schema changes as a controlled migration rather than silently dropping new fields.

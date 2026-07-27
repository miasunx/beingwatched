import hashlib
import os
import uuid
from datetime import datetime, timezone

import duckdb
import requests

FRED_KEY = os.environ["FRED_API_KEY"]
SERIES = {"DGS10": "10Y", "DGS2": "2Y"}
DB_PATH = "warehouse.duckdb"
OBSERVATIONS_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
SERIES_ENDPOINT = "https://api.stlouisfed.org/fred/series"


def payload_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode()).hexdigest()


def fetch_observations(series_id: str) -> dict:
    """Extract: pull one FRED series' observations, keeping the full raw contract."""
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "units": "lin",
        "output_type": 1,
        "order_by": "observation_date",
        "sort_order": "desc",
        "observation_start": "1776-07-04",
        "limit": 400,
    }
    resp = requests.get(OBSERVATIONS_ENDPOINT, params=params, timeout=30)
    raw_text = resp.text
    resp.raise_for_status()
    return {
        "params": params,
        "body": resp.json(),
        "raw_text": raw_text,
        "status": resp.status_code,
        "request_id": str(uuid.uuid4()),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def fetch_series_metadata(series_id: str) -> dict:
    """Extract: pull series-level metadata for onboarding/unit validation (spec section 4.4)."""
    params = {"series_id": series_id, "api_key": FRED_KEY, "file_type": "json"}
    resp = requests.get(SERIES_ENDPOINT, params=params, timeout=30)
    raw_text = resp.text
    resp.raise_for_status()
    return {
        "body": resp.json(),
        "raw_text": raw_text,
        "status": resp.status_code,
        "request_id": str(uuid.uuid4()),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_observation_rows(series_id: str, maturity_label: str, fetch: dict) -> list[dict]:
    params, body = fetch["params"], fetch["body"]
    phash = payload_hash(fetch["raw_text"])
    rows = []
    for obs in body["observations"]:
        rows.append({
            "series_id": series_id,
            "maturity_label": maturity_label,
            "obs_date": obs["date"],
            "value": obs["value"],
            "obs_realtime_start": obs["realtime_start"],
            "obs_realtime_end": obs["realtime_end"],
            "request_units": params["units"],
            "request_output_type": str(params["output_type"]),
            "request_file_type": params["file_type"],
            "request_order_by": params["order_by"],
            "request_sort_order": params["sort_order"],
            "response_realtime_start": body["realtime_start"],
            "response_realtime_end": body["realtime_end"],
            "response_observation_start": body["observation_start"],
            "response_observation_end": body["observation_end"],
            "response_count": body["count"],
            "response_offset": body["offset"],
            "response_limit": body["limit"],
            "source_name": "fred",
            "endpoint": OBSERVATIONS_ENDPOINT,
            "request_id": fetch["request_id"],
            "fetched_at_utc": fetch["fetched_at_utc"],
            "response_status": fetch["status"],
            "payload_hash": phash,
            "raw_payload": fetch["raw_text"],
        })
    return rows


def build_series_meta_row(fetch: dict) -> dict:
    series = fetch["body"]["seriess"][0]
    phash = payload_hash(fetch["raw_text"])
    return {
        "series_id": series["id"],
        "title": series["title"],
        "series_observation_start": series["observation_start"],
        "series_observation_end": series["observation_end"],
        "frequency": series["frequency"],
        "frequency_short": series["frequency_short"],
        "units": series["units"],
        "units_short": series["units_short"],
        "seasonal_adjustment": series["seasonal_adjustment"],
        "seasonal_adjustment_short": series["seasonal_adjustment_short"],
        "last_updated": series["last_updated"],
        "popularity": series["popularity"],
        "notes": series.get("notes"),
        "source_name": "fred",
        "endpoint": SERIES_ENDPOINT,
        "request_id": fetch["request_id"],
        "fetched_at_utc": fetch["fetched_at_utc"],
        "response_status": fetch["status"],
        "payload_hash": phash,
        "raw_payload": fetch["raw_text"],
    }


def main():
    yield_rows = []
    meta_rows = []
    for series_id, label in SERIES.items():
        yield_rows.extend(
            build_observation_rows(series_id, label, fetch_observations(series_id))
        )
        meta_rows.append(build_series_meta_row(fetch_series_metadata(series_id)))

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    con.execute("DROP TABLE IF EXISTS raw.raw_fred__yields;")
    con.execute("""
        CREATE TABLE raw.raw_fred__yields (
            series_id                   VARCHAR,
            maturity_label               VARCHAR,
            obs_date                     VARCHAR,
            value                        VARCHAR,
            obs_realtime_start           VARCHAR,
            obs_realtime_end             VARCHAR,
            request_units                VARCHAR,
            request_output_type          VARCHAR,
            request_file_type            VARCHAR,
            request_order_by             VARCHAR,
            request_sort_order           VARCHAR,
            response_realtime_start      VARCHAR,
            response_realtime_end        VARCHAR,
            response_observation_start   VARCHAR,
            response_observation_end     VARCHAR,
            response_count               INTEGER,
            response_offset              INTEGER,
            response_limit               INTEGER,
            source_name                  VARCHAR,
            endpoint                     VARCHAR,
            request_id                   VARCHAR,
            fetched_at_utc               VARCHAR,
            response_status              INTEGER,
            payload_hash                 VARCHAR,
            raw_payload                  VARCHAR
        );
    """)
    con.executemany(
        f"INSERT INTO raw.raw_fred__yields VALUES ({','.join(['?'] * 25)})",
        [tuple(r.values()) for r in yield_rows],
    )

    con.execute("DROP TABLE IF EXISTS raw.raw_fred__series_meta;")
    con.execute("""
        CREATE TABLE raw.raw_fred__series_meta (
            series_id                    VARCHAR,
            title                        VARCHAR,
            series_observation_start     VARCHAR,
            series_observation_end       VARCHAR,
            frequency                    VARCHAR,
            frequency_short              VARCHAR,
            units                        VARCHAR,
            units_short                  VARCHAR,
            seasonal_adjustment          VARCHAR,
            seasonal_adjustment_short    VARCHAR,
            last_updated                 VARCHAR,
            popularity                   INTEGER,
            notes                        VARCHAR,
            source_name                  VARCHAR,
            endpoint                     VARCHAR,
            request_id                   VARCHAR,
            fetched_at_utc               VARCHAR,
            response_status              INTEGER,
            payload_hash                 VARCHAR,
            raw_payload                  VARCHAR
        );
    """)
    con.executemany(
        f"INSERT INTO raw.raw_fred__series_meta VALUES ({','.join(['?'] * 20)})",
        [tuple(r.values()) for r in meta_rows],
    )

    n_yields = con.execute("SELECT count(*) FROM raw.raw_fred__yields").fetchone()[0]
    n_meta = con.execute("SELECT count(*) FROM raw.raw_fred__series_meta").fetchone()[0]
    con.close()
    print(f"Loaded {n_yields} raw rows into raw.raw_fred__yields")
    print(f"Loaded {n_meta} raw rows into raw.raw_fred__series_meta")


if __name__ == "__main__":
    main()

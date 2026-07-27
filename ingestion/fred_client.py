import hashlib
import uuid
from datetime import datetime, timezone

import requests

OBSERVATIONS_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
SERIES_ENDPOINT = "https://api.stlouisfed.org/fred/series"


def payload_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode()).hexdigest()


def fetch_observations(api_key: str, series_id: str, limit: int = 400) -> dict:
    """Extract: pull one FRED series' observations, keeping the full raw contract."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "units": "lin",
        "output_type": 1,
        "order_by": "observation_date",
        "sort_order": "desc",
        "observation_start": "1776-07-04",
        "limit": limit,
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


def fetch_series_metadata(api_key: str, series_id: str) -> dict:
    """Extract: pull series-level metadata for onboarding/unit validation (spec section 4.4)."""
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
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


SERIES_META_DDL = """
    CREATE TABLE {table} (
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
"""


def load_series_meta_table(con, schema_table: str, rows: list[dict]) -> int:
    """Load: drop-and-reload one raw_fred__<domain>_series_meta table."""
    con.execute(f"DROP TABLE IF EXISTS {schema_table};")
    con.execute(SERIES_META_DDL.format(table=schema_table))
    con.executemany(
        f"INSERT INTO {schema_table} VALUES ({','.join(['?'] * 20)})",
        [tuple(r.values()) for r in rows],
    )
    return con.execute(f"SELECT count(*) FROM {schema_table}").fetchone()[0]

import os

import duckdb

from fred_client import (
    OBSERVATIONS_ENDPOINT,
    build_series_meta_row,
    fetch_observations,
    fetch_series_metadata,
    load_series_meta_table,
    payload_hash,
)

FRED_KEY = os.environ["FRED_API_KEY"]
SERIES_ID = "PAYEMS"
DB_PATH = "warehouse.duckdb"


def build_observation_rows(series_id: str, fetch: dict) -> list[dict]:
    params, body = fetch["params"], fetch["body"]
    phash = payload_hash(fetch["raw_text"])
    rows = []
    for obs in body["observations"]:
        rows.append({
            "series_id": series_id,
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


def main():
    nfp_rows = build_observation_rows(SERIES_ID, fetch_observations(FRED_KEY, SERIES_ID))
    meta_rows = [build_series_meta_row(fetch_series_metadata(FRED_KEY, SERIES_ID))]

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    con.execute("DROP TABLE IF EXISTS raw.raw_fred__nfp;")
    con.execute("""
        CREATE TABLE raw.raw_fred__nfp (
            series_id                   VARCHAR,
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
        f"INSERT INTO raw.raw_fred__nfp VALUES ({','.join(['?'] * 24)})",
        [tuple(r.values()) for r in nfp_rows],
    )

    n_meta = load_series_meta_table(con, "raw.raw_fred__nfp_series_meta", meta_rows)

    n_nfp = con.execute("SELECT count(*) FROM raw.raw_fred__nfp").fetchone()[0]
    con.close()
    print(f"Loaded {n_nfp} raw rows into raw.raw_fred__nfp")
    print(f"Loaded {n_meta} raw rows into raw.raw_fred__nfp_series_meta")


if __name__ == "__main__":
    main()

import os
import requests
import duckdb
from datetime import datetime, timezone

FRED_KEY = os.environ["FRED_API_KEY"]
SERIES = {"DGS10": "10Y", "DGS2": "2Y"}
DB_PATH = "warehouse.duckdb"

def fetch_series(series_id: str) -> list[dict]:
    """Extract: pull one FRED series as raw observations."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 400,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["observations"]

def main():
    loaded_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for series_id, label in SERIES.items():
        for obs in fetch_series(series_id):
            rows.append({
                "series_id": series_id,
                "maturity_label": label,
                "obs_date": obs["date"],
                "value": obs["value"],
                "_loaded_at": loaded_at,
                "_source": "fred",
            })

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    con.execute("DROP TABLE IF EXISTS raw.raw_fred__yields;")
    con.execute("""
        CREATE TABLE raw.raw_fred__yields (
            series_id      VARCHAR,
            maturity_label VARCHAR,
            obs_date       VARCHAR,
            value          VARCHAR,
            _loaded_at     VARCHAR,
            _source        VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO raw.raw_fred__yields VALUES (?,?,?,?,?,?)",
        [tuple(r.values()) for r in rows],
    )
    n = con.execute("SELECT count(*) FROM raw.raw_fred__yields").fetchone()[0]
    con.close()
    print(f"Loaded {n} raw rows into raw.raw_fred__yields")

if __name__ == "__main__":
    main()
    
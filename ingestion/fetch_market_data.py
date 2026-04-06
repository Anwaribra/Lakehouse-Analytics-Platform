from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import requests
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("ingestion")

DEFAULT_COINS = ("bitcoin", "ethereum", "solana", "cardano")
YF_TICKERS = ("BTC-USD", "ETH-USD", "SOL-USD")


def _s3_client() -> Any:
    endpoint = os.environ.get("MINIO_ENDPOINT_URL", "http://localhost:9000")
    key = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("MINIO_ROOT_USER", "minioadmin")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get(
        "MINIO_ROOT_PASSWORD", "minioadmin"
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _put_parquet_df(s3: Any, bucket: str, key: str, df: pd.DataFrame) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue(), ContentType="application/octet-stream")
    LOG.info("s3://%s/%s (%s rows)", bucket, key, len(df))


def fetch_coingecko_simple_prices(coin_ids: tuple[str, ...]) -> pd.DataFrame:
    """CoinGecko free API — no key."""
    ids = ",".join(coin_ids)
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ids,
        "vs_currencies": "usd",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    raw = r.json()
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for coin_id, payload in raw.items():
        rows.append(
            {
                "coin_id": coin_id,
                "price_usd": payload.get("usd"),
                "usd_24h_vol": payload.get("usd_24h_vol"),
                "usd_24h_change": payload.get("usd_24h_change"),
                "last_updated_at": payload.get("last_updated_at"),
                "ingested_at": now.isoformat(),
                "source": "coingecko_simple",
            }
        )
    return pd.DataFrame(rows)


def fetch_yfinance_ohlcv(tickers: tuple[str, ...], period: str = "90d") -> pd.DataFrame:
    """Historical daily OHLCV — long format for Parquet."""
    data = yf.download(
        list(tickers),
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data.empty:
        LOG.warning("yfinance returned no rows")
        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "ingested_at",
            ]
        )

    frames: list[pd.DataFrame] = []
    now = datetime.now(timezone.utc).isoformat()
    if isinstance(data.columns, pd.MultiIndex):
        level0 = data.columns.get_level_values(0)
        for t in tickers:
            if t not in level0:
                continue
            sub = data[t].copy().reset_index()
            if "Date" in sub.columns:
                sub.rename(columns={"Date": "date"}, inplace=True)
            elif "Datetime" in sub.columns:
                sub.rename(columns={"Datetime": "date"}, inplace=True)
            sub["ticker"] = t
            sub["ingested_at"] = now
            frames.append(sub)
    else:
        t = tickers[0]
        sub = data.reset_index()
        if "Date" in sub.columns:
            sub.rename(columns={"Date": "date"}, inplace=True)
        sub["ticker"] = t
        sub["ingested_at"] = now
        frames.append(sub)

    if not frames:
        LOG.warning("yfinance: no matching tickers in response")
        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "ingested_at",
            ]
        )

    out = pd.concat(frames, ignore_index=True)
    out.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        },
        inplace=True,
    )
    cols = ["date", "ticker", "open", "high", "low", "close", "volume", "ingested_at"]
    for c in cols:
        if c not in out.columns:
            out[c] = None
    return out[cols]


def load_kaggle_backup_csv(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        LOG.info("Kaggle backup CSV not found at %s — skipping", path)
        return None
    df = pd.read_csv(path)
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["source"] = "kaggle_backup"
    return df


def main() -> int:
    bucket = os.environ.get("MINIO_BUCKET", "lakehouse")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    s3 = _s3_client()

    coin_ids = tuple(
        x.strip()
        for x in os.environ.get("COINGECKO_COIN_IDS", ",".join(DEFAULT_COINS)).split(",")
        if x.strip()
    )
    yf_tickers = tuple(
        x.strip().upper()
        for x in os.environ.get("YFINANCE_TICKERS", ",".join(YF_TICKERS)).split(",")
        if x.strip()
    )

    # --- CoinGecko (Bronze)
    try:
        cg = fetch_coingecko_simple_prices(coin_ids)
        key = f"bronze/coingecko/coingecko_prices_{ts}.parquet"
        _put_parquet_df(s3, bucket, key, cg)
    except Exception as e:
        LOG.exception("CoinGecko ingestion failed: %s", e)
        return 1

    # --- yfinance (Bronze)
    try:
        yf_df = fetch_yfinance_ohlcv(yf_tickers)
        key = f"bronze/yfinance/yfinance_ohlcv_{day}_{ts}.parquet"
        _put_parquet_df(s3, bucket, key, yf_df)
    except Exception as e:
        LOG.exception("yfinance ingestion failed: %s", e)
        return 1

    # --- Optional Kaggle-style CSV backup (Bronze) not used for now
    backup = os.environ.get("KAGGLE_CSV_PATH", "/opt/airflow/ingestion/data/backup.csv")
    backup_path = Path(backup)
    bk_df = load_kaggle_backup_csv(backup_path)
    if bk_df is not None and not bk_df.empty:
        key = f"bronze/kaggle_backup/kaggle_backup_{ts}.parquet"
        _put_parquet_df(s3, bucket, key, bk_df)

    LOG.info("Bronze ingestion complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

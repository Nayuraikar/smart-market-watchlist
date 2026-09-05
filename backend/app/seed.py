import asyncio
import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import Instrument


# Recognizable NSE large caps plus a small set of widely held growth names.
# Keep Yahoo Finance's .NS suffix because it is also the provider identifier.
# This is deliberately a fixed, curated catalog: seeding must not depend on
# external metadata or market-data availability.

TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",

    "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",

    "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
    "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "TMCV.NS",

    "BAJAJFINSV.NS", "HCLTECH.NS", "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",

    "SBILIFE.NS", "HDFCLIFE.NS", "INDUSINDBK.NS", "BPCL.NS", "TECHM.NS",
    "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "HINDALCO.NS", "TATACONSUM.NS",

    "ETERNAL.NS", "IRCTC.NS", "DMART.NS",

    # Additional IT and financial-services coverage.
    "LTM.NS", "PERSISTENT.NS", "COFORGE.NS", "SHRIRAMFIN.NS",
]


METADATA_FETCH_DELAY_SECONDS = 3.0
MAX_METADATA_ATTEMPTS_PER_RUN = 5
# Conservative pace against an unofficial, rate-limited-by-provider API.


def _safe_fallback_name(ticker: str) -> str:
    return ticker.split(".")[0]


def _fetch_metadata(
    ticker: str,
) -> tuple[str | None, str | None, str | None]:
    """
    Returns (name, sector, industry) on success,
    or (None, None, None) on failure.

    name=None signals 'do not overwrite' and the caller decides
    the fallback behavior.
    """
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info

        name = info.get("longName") or info.get("shortName")
        sector = info.get("sector")
        industry = info.get("industry")

        if not name:
            return None, None, None

        return name, sector, industry

    except Exception as exc:
        print(f"  [metadata failed] {ticker}: {exc}")
        return None, None, None


async def ensure_instruments_exist() -> int:
    """
    Phase A: insert bare rows for every ticker not already present.

    Pure DB operation. No network calls, so this can never be blocked
    by yfinance.
    """
    rows = [
        {
            "ticker": ticker,
            "name": _safe_fallback_name(ticker),
            "exchange": "NSE",
            "instrument_type": "EQUITY",
            "sector": None,
            "industry": None,
            "active": True,
        }
        for ticker in TICKERS
    ]

    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Instrument).values(rows)

        stmt = stmt.on_conflict_do_nothing(
            index_elements=["ticker"]
        )

        result = await session.execute(stmt)
        await session.commit()

        return result.rowcount


async def backfill_metadata() -> dict:
    """
    Phase B: for every instrument still missing sector/industry,
    retry yfinance.

    Safe to re-run any number of times. Only touches rows that
    still need metadata.

    Stops early if Yahoo is clearly rate-limiting this run.
    """
    stats = {
        "already_complete": 0,
        "backfilled": 0,
        "still_failed": 0,
        "skipped_this_run": 0,
    }

    consecutive_failures = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Instrument).where(
                Instrument.ticker.in_(TICKERS),
                (Instrument.sector.is_(None))
                | (Instrument.industry.is_(None)),
            )
        )

        pending = result.scalars().all()

        for instrument in pending:
            if consecutive_failures >= MAX_METADATA_ATTEMPTS_PER_RUN:
                stats["skipped_this_run"] += 1
                continue

            name, sector, industry = _fetch_metadata(instrument.ticker)

            if name is not None:
                instrument.name = name
                instrument.sector = sector
                instrument.industry = industry

                stats["backfilled"] += 1
                consecutive_failures = 0

                print(f"[metadata] success: {instrument.ticker}")

            else:
                stats["still_failed"] += 1
                consecutive_failures += 1

                print(
                    f"[metadata] failed: {instrument.ticker} "
                    f"({consecutive_failures}/{MAX_METADATA_ATTEMPTS_PER_RUN})"
                )

            time.sleep(METADATA_FETCH_DELAY_SECONDS)

        await session.commit()

        stats["already_complete"] = len(TICKERS) - len(pending)

    return stats


async def main() -> None:
    inserted = await ensure_instruments_exist()

    print(
        f"\nPhase A — instrument universe: "
        f"{inserted} newly inserted, "
        f"{len(TICKERS) - inserted} already existed. "
        f"{len(TICKERS)} total defined."
    )

    print(
        "\nPhase B — metadata backfill "
        "(retrying rows missing sector/industry)..."
    )

    stats = await backfill_metadata()

    print("\nSeed complete")

    print(
        f"{len(TICKERS)} tickers defined, "
        f"{len(TICKERS)} expected catalog entries"
    )

    print("\nMetadata:")
    print(
        f"  already complete (from a prior run): "
        f"{stats['already_complete']}"
    )
    print(
        f"  backfilled this run:                 "
        f"{stats['backfilled']}"
    )
    print(
        f"  still failed (will retry next run):  "
        f"{stats['still_failed']}"
    )
    print(
        f"  skipped this run:                     "
        f"{stats['skipped_this_run']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
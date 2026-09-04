import asyncio
import time
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db import AsyncSessionLocal
from app.models import Instrument

# NIFTY 50 (yfinance .NS suffix) + a handful of extras for demo variety.
# Broader universe discovery is explicitly deferred — Phase 3.6 scope only.
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",
    "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",
    "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
    "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "TATAMOTORS.NS",
    "BAJAJFINSV.NS", "HCLTECH.NS", "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "SBILIFE.NS", "HDFCLIFE.NS", "INDUSINDBK.NS", "BPCL.NS", "TECHM.NS",
    "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "HINDALCO.NS", "TATACONSUM.NS",
    "ZOMATO.NS", "IRCTC.NS", "DMART.NS",
]

METADATA_FETCH_DELAY_SECONDS = 3.0
MAX_METADATA_ATTEMPTS_PER_RUN = 5   # conservative pace against an unofficial, unrate-limited-by-us API


def _safe_fallback_name(ticker: str) -> str:
    return ticker.split(".")[0]


def _fetch_metadata(ticker: str) -> tuple[str | None, str | None, str | None]:
    """Returns (name, sector, industry) on success, or (None, None, None) on failure.
    name=None signals 'do not overwrite' — caller decides the fallback."""
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
    """Phase A: insert bare rows for every ticker not already present.
    Pure DB operation — no network calls, so this can never be blocked by yfinance."""
    rows = [
        {
            "ticker": t,
            "name": _safe_fallback_name(t),
            "exchange": "NSE",
            "instrument_type": "EQUITY",
            "sector": None,
            "industry": None,
            "active": True,
        }
        for t in TICKERS
    ]
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Instrument).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker"])
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def backfill_metadata() -> dict:
    """Phase B: for every instrument still missing sector/industry, retry yfinance.
    Safe to re-run any number of times — only touches rows that still need it.
    Stops early if Yahoo is clearly rate-limiting this run (circuit breaker)."""
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
                (Instrument.sector.is_(None)) | (Instrument.industry.is_(None))
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
                print(f"[metadata] failed: {instrument.ticker} "
                      f"({consecutive_failures}/{MAX_METADATA_ATTEMPTS_PER_RUN})")

            time.sleep(METADATA_FETCH_DELAY_SECONDS)

        await session.commit()
        stats["already_complete"] = len(TICKERS) - len(pending)

    return stats


async def main() -> None:
    inserted = await ensure_instruments_exist()
    print(f"\nPhase A — instrument universe: {inserted} newly inserted, "
          f"{len(TICKERS) - inserted} already existed. {len(TICKERS)} total present.")

    print("\nPhase B — metadata backfill (retrying rows missing sector/industry)...")
    stats = await backfill_metadata()

    print(f"\nSeed complete")
    print(f"{len(TICKERS)} tickers processed, {len(TICKERS)} instruments present")
    print(f"\nMetadata:")
    print(f"  already complete (from a prior run): {stats['already_complete']}")
    print(f"  backfilled this run:                 {stats['backfilled']}")
    print(f"  still failed (will retry next run):  {stats['still_failed']}")


if __name__ == "__main__":
    asyncio.run(main())
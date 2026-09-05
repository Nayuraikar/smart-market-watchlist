import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import Instrument


# Names and demo parameters are committed alongside the replay files.
CATALOG_PATH = Path("data/demo_catalog.json")
if not CATALOG_PATH.exists():
    CATALOG_PATH = Path(__file__).resolve().parents[2] / "data/demo_catalog.json"
CATALOG = json.loads(CATALOG_PATH.read_text())["instruments"]
TICKERS = [row["ticker"] for row in CATALOG]


async def ensure_instruments_exist() -> int:
    """
    Phase A: insert bare rows for every ticker not already present.

    Pure DB operation. No network calls, so this can never be blocked
    by external services.
    """
    rows = [
        {
            "ticker": stock["ticker"],
            "name": stock["name"],
            "exchange": "NSE",
            "instrument_type": "EQUITY",
            "sector": stock["sector"],
            "industry": None,
            "active": True,
        }
        for stock in CATALOG
    ]

    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Instrument).values(rows)

        stmt = stmt.on_conflict_do_nothing(
            index_elements=["ticker"]
        )

        result = await session.execute(stmt)
        # Existing demo databases also receive the complete offline catalog.
        from sqlalchemy import update
        for stock in CATALOG:
            await session.execute(update(Instrument).where(Instrument.ticker == stock["ticker"]).values(
                name=stock["name"], sector=stock["sector"],
            ))
        await session.commit()

        return result.rowcount


async def main() -> None:
    inserted = await ensure_instruments_exist()
    print(f"Offline catalog ready: {inserted} inserted, {len(TICKERS)} defined.")


if __name__ == "__main__":
    asyncio.run(main())

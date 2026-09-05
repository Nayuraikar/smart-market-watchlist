"""
Reset market data for a fresh historical replay demo.

PRESERVED: users, instruments, watchlists, watchlist_items
CLEARED:   market_events, market_history, market_state
RESET:     watchlists.last_viewed_at
"""

import asyncio

from sqlalchemy import delete, update

from app.db import AsyncSessionLocal
from app.models import MarketEvent, MarketHistory, MarketState, Watchlist


async def main() -> None:
    print()
    print("=" * 64)
    print("RESETTING DEMO MARKET STATE")
    print("=" * 64)

    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketEvent))
        await db.execute(delete(MarketHistory))
        await db.execute(delete(MarketState))
        await db.execute(update(Watchlist).values(last_viewed_at=None))
        await db.commit()

    print("Market events   : CLEARED")
    print("Market history  : CLEARED")
    print("Market state    : CLEARED")
    print("Last viewed     : RESET")
    print()
    print("Users           : PRESERVED")
    print("Instruments     : PRESERVED")
    print("Watchlists      : PRESERVED")
    print("Watchlist items : PRESERVED")
    print()
    print("Reset complete.")


if __name__ == "__main__":
    asyncio.run(main())

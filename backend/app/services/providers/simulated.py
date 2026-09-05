"""Offline, repeating historical feed with current simulation timestamps."""

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.market import MarketObservation
from app.services.providers.replay import ReplayExhausted, ReplayProvider


class SimulatedMarketProvider(ReplayProvider):
    """Advance one saved observation per ticker per tick, looping at EOF.

    Prices and fundamentals are never generated or fetched. Only timestamps
    and source labels change, allowing normal freshness and event detection.
    A worker restart begins the deterministic sequence again.
    """

    def __init__(self, scenario_path: str | Path):
        super().__init__(scenario_path)
        if not self._timelines or any(not rows for rows in self._timelines.values()):
            raise ValueError("Simulation requires nonempty historical timelines")

    async def get_stock(self, ticker: str) -> MarketObservation:
        try:
            observation = await super().get_stock(ticker)
        except ReplayExhausted:
            self.reset(ticker)
            observation = await super().get_stock(ticker)
        return observation.model_copy(update={
            "observed_at": datetime.now(timezone.utc),
            "source": "synthetic-demo-replay" if observation.source.startswith("synthetic-demo") else "historical-simulation",
        })

    async def get_stocks(self, tickers: list[str]) -> list[MarketObservation]:
        # Instruments without saved data cannot be supplied by a live fallback.
        return [await self.get_stock(t) for t in tickers if t in self._timelines]

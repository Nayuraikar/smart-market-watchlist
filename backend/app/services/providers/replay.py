import json
from pathlib import Path
from app.schemas.market import MarketObservation


class ReplayProvider:
    """Feeds pre-recorded observations in order, one step per call per
    ticker — the resilience-testing backbone for Phase 9 failure injection.
    Scenario file shape: { "TICKER": [ {price, volume, observed_at, ...}, ... ] }
    """

    def __init__(self, scenario_path: str | Path):
        self._path = Path(scenario_path)
        with open(self._path) as f:
            raw = json.load(f)
        self._timelines: dict[str, list[MarketObservation]] = {
            ticker: [MarketObservation(ticker=ticker, **obs) for obs in observations]
            for ticker, observations in raw.items()
        }
        self._cursor: dict[str, int] = {ticker: 0 for ticker in self._timelines}

    async def get_stock(self, ticker: str) -> MarketObservation:
        timeline = self._timelines.get(ticker)
        if not timeline:
            raise ValueError(f"No replay data for {ticker}")
        idx = self._cursor[ticker]
        if idx >= len(timeline):
            raise StopIteration(f"Replay exhausted for {ticker}")
        obs = timeline[idx]
        self._cursor[ticker] += 1
        return obs

    async def get_stocks(self, tickers: list[str]) -> list[MarketObservation]:
        return [await self.get_stock(t) for t in tickers]

    async def search(self, query: str) -> list[dict]:
        return [{"ticker": t, "name": t} for t in self._timelines if query.upper() in t.upper()]

    def reset(self, ticker: str | None = None) -> None:
        if ticker:
            self._cursor[ticker] = 0
        else:
            self._cursor = {t: 0 for t in self._timelines}

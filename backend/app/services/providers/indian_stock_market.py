import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import yfinance as yf

from app.schemas.market import MarketObservation


class IndianStockMarketProvider:
    """Real provider backed by yfinance. Field mapping confirmed against
    actual yf_info_reliance.json fixture from Phase 2 — not assumed."""

    async def get_stock(self, ticker: str) -> MarketObservation:
        return await asyncio.to_thread(self._fetch_one, ticker)

    async def get_stocks(self, tickers: list[str]) -> list[MarketObservation]:
        return list(await asyncio.gather(*(self.get_stock(t) for t in tickers)))

    async def search(self, query: str) -> list[dict]:
        return await asyncio.to_thread(self._search_sync, query)

    def _fetch_one(self, ticker: str) -> MarketObservation:
        info = yf.Ticker(ticker).info

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        volume = info.get("regularMarketVolume") or info.get("volume")
        epoch = info.get("regularMarketTime")

        if price is None or volume is None or epoch is None:
            raise ValueError(f"Incomplete data from provider for {ticker}")

        def _dec(key: str) -> Decimal | None:
            val = info.get(key)
            return Decimal(str(val)) if val is not None else None

        return MarketObservation(
            ticker=ticker,
            price=Decimal(str(price)),
            previous_close=_dec("regularMarketPreviousClose"),
            volume=Decimal(str(volume)),
            market_cap=_dec("marketCap"),
            pe_ratio=_dec("trailingPE"),
            dividend_yield=_dec("dividendYield"),
            observed_at=datetime.fromtimestamp(epoch, tz=timezone.utc),
            source="yfinance",
        )

    def _search_sync(self, query: str) -> list[dict]:
        # NOTE: yf.Search API shape varies across yfinance versions — verify
        # against the installed version before relying on this in production.
        try:
            results = yf.Search(query).quotes
        except Exception:
            return []
        return [
            {"ticker": r.get("symbol"), "name": r.get("shortname") or r.get("longname")}
            for r in results
        ]

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

import yfinance as yf

from app.schemas.market import MarketObservation


logger = logging.getLogger(__name__)
YAHOO_BATCH_SIZE = 25


class IndianStockMarketProvider:
    """Real provider backed by yfinance. Field mapping confirmed against
    actual yf_info_reliance.json fixture from Phase 2 — not assumed."""

    async def get_stock(self, ticker: str) -> MarketObservation:
        return await asyncio.to_thread(self._fetch_one, ticker)

    async def get_stocks(self, tickers: list[str]) -> list[MarketObservation]:
        """Fetch a universe in Yahoo batches, retaining successful tickers.

        ``yf.download`` is Yahoo/yfinance's bulk endpoint, unlike the former
        implementation which launched one ``Ticker.info`` request per symbol.
        A bad or unavailable symbol is omitted from this result rather than
        raising for the entire universe; callers can therefore ingest the
        observations that Yahoo did return.  Fundamental fields are nullable
        in ``MarketObservation`` and are intentionally left absent here: the
        batch endpoint supplies market bars, not fabricated fundamentals.
        """
        observations: list[MarketObservation] = []
        for start in range(0, len(tickers), YAHOO_BATCH_SIZE):
            batch = tickers[start:start + YAHOO_BATCH_SIZE]
            try:
                observations.extend(await asyncio.to_thread(self._fetch_batch, batch))
            except Exception as exc:
                logger.warning("Yahoo batch failed for %s: %s", batch, exc)
                # A 429 normally applies to all subsequent requests too; stop
                # cleanly and retain observations from earlier batches.
                if self._is_rate_limited(exc):
                    logger.warning("Yahoo rate limit detected; stopping remaining batches")
                    break
        return observations

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

    def _fetch_batch(self, tickers: list[str]) -> list[MarketObservation]:
        if not tickers:
            return []

        # Five-minute bars provide a recent, monotonic timestamp for the
        # periodic ingestion worker. Five days stays within Yahoo's intraday
        # retention window while allowing the most recent completed bar to be
        # used outside market hours. auto_adjust=False keeps Close unadjusted.
        frame = yf.download(
            tickers=tickers,
            period="5d",
            interval="5m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        if frame.empty:
            logger.warning("Yahoo returned no market bars for batch %s", tickers)
            return []

        observations: list[MarketObservation] = []
        for ticker in tickers:
            try:
                observation = self._observation_from_batch(frame, ticker)
            except Exception as exc:
                # yfinance commonly returns a partial frame when one symbol is
                # invalid or unavailable. Keep processing the other symbols.
                logger.warning("Yahoo data unavailable for %s: %s", ticker, exc)
                continue
            observations.append(observation)
        return observations

    @staticmethod
    def _observation_from_batch(frame, ticker: str) -> MarketObservation:
        try:
            ticker_frame = frame[ticker]
        except KeyError as exc:
            raise ValueError("ticker absent from Yahoo batch response") from exc

        ticker_frame = ticker_frame.dropna(subset=["Close", "Volume"])
        if ticker_frame.empty:
            raise ValueError("no complete Close/Volume bar")

        latest = ticker_frame.iloc[-1]
        previous_close = (
            Decimal(str(ticker_frame.iloc[-2]["Close"]))
            if len(ticker_frame) > 1
            else None
        )
        observed_at = ticker_frame.index[-1].to_pydatetime()
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)

        return MarketObservation(
            ticker=ticker,
            price=Decimal(str(latest["Close"])),
            previous_close=previous_close,
            volume=Decimal(str(latest["Volume"])),
            observed_at=observed_at,
            source="yfinance",
        )

    @staticmethod
    def _is_rate_limited(exc: Exception) -> bool:
        message = str(exc).lower()
        return "429" in message or "rate limit" in message or "too many requests" in message

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

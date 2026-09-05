from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.services.providers.indian_stock_market import IndianStockMarketProvider
from app.services.ingestion import compute_data_quality


@pytest.mark.asyncio
async def test_get_stocks_uses_one_batch_request_and_keeps_partial_success(monkeypatch):
    index = pd.DatetimeIndex([
        datetime(2026, 9, 3, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 9, 3, 9, 20, tzinfo=ZoneInfo("Asia/Kolkata")),
    ])
    frame = pd.DataFrame({
        ("RELIANCE.NS", "Close"): [Decimal("1400"), Decimal("1425")],
        ("RELIANCE.NS", "Volume"): [1000, 1200],
        ("TCS.NS", "Close"): [Decimal("3500"), Decimal("3525")],
        ("TCS.NS", "Volume"): [2000, 2400],
    }, index=index)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return frame

    monkeypatch.setattr("app.services.providers.indian_stock_market.yf.download", fake_download)

    observations = await IndianStockMarketProvider().get_stocks([
        "RELIANCE.NS", "TCS.NS", "MISSING.NS",
    ])

    assert len(calls) == 1
    assert calls[0]["tickers"] == ["RELIANCE.NS", "TCS.NS", "MISSING.NS"]
    assert calls[0]["period"] == "5d"
    assert calls[0]["interval"] == "5m"
    assert [obs.ticker for obs in observations] == ["RELIANCE.NS", "TCS.NS"]
    assert observations[0].price == Decimal("1425")
    assert observations[0].previous_close == Decimal("1400")
    assert observations[0].observed_at == datetime(2026, 9, 3, 3, 50, tzinfo=timezone.utc)
    assert observations[0].observed_at.tzinfo == timezone.utc
    assert compute_data_quality(
        observations[0], observations[0].observed_at + timedelta(seconds=60), 120
    ) == "FRESH"


@pytest.mark.asyncio
async def test_get_stocks_retains_completed_batches_when_rate_limited(monkeypatch):
    provider = IndianStockMarketProvider()

    def fake_batch(batch):
        if batch[0] == "FIRST.NS":
            return [
                provider._observation_from_batch(
                    pd.DataFrame({
                        ("FIRST.NS", "Close"): [100],
                        ("FIRST.NS", "Volume"): [1000],
                    }, index=pd.DatetimeIndex([datetime(2026, 9, 4, tzinfo=timezone.utc)])),
                    "FIRST.NS",
                )
            ]
        raise RuntimeError("HTTP 429 too many requests")

    monkeypatch.setattr(provider, "_fetch_batch", fake_batch)
    tickers = ["FIRST.NS"] + [f"T{i}.NS" for i in range(25)]

    observations = await provider.get_stocks(tickers)

    assert [obs.ticker for obs in observations] == ["FIRST.NS"]

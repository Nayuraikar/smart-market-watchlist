import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.seed import TICKERS
from app.services.providers.simulated import SimulatedMarketProvider


SCENARIO = Path('data/scenarios/historical_update_57.json')
if not SCENARIO.exists():
    SCENARIO = Path(__file__).resolve().parents[2] / SCENARIO


@pytest.mark.asyncio
async def test_saved_values_repeat_with_current_timestamps(monkeypatch):
    # Any accidental attempt to obtain external market data must fail the test.
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Network access is forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    provider = SimulatedMarketProvider(SCENARIO)
    raw = json.loads(SCENARIO.read_text())
    assert set(TICKERS) == set(raw)
    ticker = TICKERS[0]
    start = datetime.now(timezone.utc)
    observations = [await provider.get_stock(ticker) for _ in range(len(raw[ticker]) + 1)]
    assert [float(o.price) for o in observations] == [float(r['price']) for r in raw[ticker]] + [float(raw[ticker][0]['price'])]
    assert all(o.observed_at >= start for o in observations)
    assert all(o.source == 'historical-simulation' for o in observations)
    assert observations[-1].observed_at > observations[0].observed_at
    assert await provider.get_stocks(['MISSING.NS']) == []
    rows = await provider.get_stocks(TICKERS)
    assert len(rows) == 57


def test_empty_scenario_fails(tmp_path):
    path = tmp_path / 'empty.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='nonempty'):
        SimulatedMarketProvider(path)


@pytest.mark.asyncio
async def test_saved_fundamentals_are_preserved_during_replay():
    raw = json.loads(SCENARIO.read_text())['RELIANCE.NS']
    provider = SimulatedMarketProvider(SCENARIO)
    for index in range(len(raw) + 1):
        row = await provider.get_stock('RELIANCE.NS')
        expected = raw[index % len(raw)]
        for field in ['market_cap', 'pe_ratio', 'dividend_yield']:
            value = getattr(row, field)
            assert (None if value is None else float(value)) == (None if expected[field] is None else float(expected[field]))

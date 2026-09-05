"""Validate every committed demo row, including signal/noise coverage."""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.seed import TICKERS
from app.schemas.market import MarketObservation

DATA = Path('data')
if not (DATA / 'demo_catalog.json').exists():
    DATA = Path(__file__).resolve().parents[2] / 'data'


def test_every_stock_has_complete_consistent_history_and_both_move_directions():
    baseline = json.loads((DATA / 'scenarios/demo_baseline_57.json').read_text())
    updates = json.loads((DATA / 'scenarios/demo_timeline_57.json').read_text())
    catalog = {row['ticker']: row for row in json.loads((DATA / 'demo_catalog.json').read_text())['instruments']}
    assert set(baseline) == set(updates) == set(catalog) == set(TICKERS)
    for ticker in TICKERS:
        assert len(baseline[ticker]) == 120
        assert len(updates[ticker]) == 60
        rows = baseline[ticker] + updates[ticker]
        times = [datetime.fromisoformat(row['observed_at']) for row in rows]
        assert times == sorted(set(times))
        directions = set()
        for index, row in enumerate(rows):
            observation = MarketObservation(ticker=ticker, **row)
            assert observation.source == 'synthetic-demo-v1'
            assert observation.price > 0 and observation.volume > 0
            assert observation.market_cap > 0 and observation.pe_ratio > 0
            assert observation.dividend_yield >= 0
            assert abs(observation.market_cap - observation.price * catalog[ticker]['demo_shares_outstanding']) <= Decimal('.01')
            assert abs(observation.pe_ratio - observation.price / Decimal(catalog[ticker]['demo_earnings_per_share'])) <= Decimal('.0051')
            if index:
                assert observation.previous_close == Decimal(rows[index - 1]['price'])
            move = (observation.price / observation.previous_close - 1) * 100
            directions.add('up' if move >= 2 else 'down' if move <= -2 else 'quiet')
        assert directions == {'up', 'down', 'quiet'}


def test_runtime_defaults_use_complete_demo_files():
    from app.services.providers.simulated import SimulatedMarketProvider
    import asyncio

    async def check():
        provider = SimulatedMarketProvider(DATA / 'scenarios/demo_timeline_57.json')
        rows = await provider.get_stocks(TICKERS)
        assert len(rows) == 57
        assert all(row.source == 'synthetic-demo-replay' for row in rows)
        assert all(row.market_cap is not None and row.pe_ratio is not None and row.dividend_yield is not None for row in rows)
    asyncio.run(check())

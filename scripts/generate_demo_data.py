"""Generate reproducible, fully populated synthetic scenarios. No network or DB.

Run from any directory: python3 scripts/generate_demo_data.py [--check]
The runtime reads the committed output JSON; generation is a development step.
"""
import argparse
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data/demo_catalog.json'
OUTPUT = ROOT / 'data/scenarios'
COUNT = 180
BASELINE_COUNT = 120


def money(value):
    return str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def generate():
    catalog = json.loads(CATALOG.read_text())['instruments']
    # Weekday demo sessions, deliberately not an exchange holiday calendar.
    day = date(2026, 9, 4)
    dates = []
    while len(dates) < COUNT:
        if day.weekday() < 5:
            dates.append(day)
        day -= timedelta(days=1)
    dates.reverse()
    baseline, timeline = {}, {}
    for stock in catalog:
        ticker = stock['ticker']
        anchor = Decimal(stock['anchor_price'])
        previous = anchor
        rows = []
        for step, day in enumerate(dates):
            seed = int(hashlib.sha256(f'demo-v1:{ticker}:{step}'.encode()).hexdigest()[:12], 16)
            # Alternating quiet, rally and pullback regimes, plus periodic
            # +/-3% moves to exercise the unchanged 2% event threshold.
            phase = step % 10
            if phase == 0:
                change = Decimal('0.030')
            elif phase == 1:
                change = Decimal('-0.029')
            else:
                drift = Decimal('0.0015') if (step // 20) % 2 == 0 else Decimal('-0.0015')
                noise = Decimal(seed % 1601 - 800) / 100000
                reversion = (anchor - previous) / anchor * Decimal('.06')
                change = drift + noise + reversion
            price = Decimal(money(previous * (1 + change)))
            volume_factor = Decimal('0.7') + Decimal(seed % 900) / 1000 + abs(change) * 25
            volume = max(1, int(stock['anchor_volume'] * volume_factor))
            eps = Decimal(stock['demo_earnings_per_share'])
            dividend = Decimal(stock['demo_annual_dividend'])
            rows.append({
                'price': str(price), 'previous_close': money(previous), 'volume': str(volume),
                'market_cap': money(price * stock['demo_shares_outstanding']),
                'pe_ratio': money(price / eps),
                'dividend_yield': money(dividend / price * 100),
                'observed_at': datetime.combine(day, time(10), timezone.utc).isoformat(),
                'source': 'synthetic-demo-v1',
            })
            previous = price
        baseline[ticker] = rows[:BASELINE_COUNT]
        timeline[ticker] = rows[BASELINE_COUNT:]
    files = {'demo_baseline_57.json': baseline, 'demo_timeline_57.json': timeline}
    manifest = {
        'version': 1, 'classification': 'SYNTHETIC_DEMO_NOT_ACTUAL_MARKET_HISTORY',
        'generator': 'scripts/generate_demo_data.py', 'catalog': 'data/demo_catalog.json',
        'tickers': len(catalog), 'observations_per_ticker': COUNT,
        'baseline_observations': BASELINE_COUNT, 'replay_observations': COUNT - BASELINE_COUNT,
        'start_date': dates[0].isoformat(), 'end_date': dates[-1].isoformat(),
        'calendar': 'Weekdays only; exchange holidays are not modeled.',
        'units': {'price': 'INR', 'market_cap': 'INR', 'volume': 'shares', 'pe_ratio': 'multiple', 'dividend_yield': 'percentage points (0.46 means 0.46%)'},
        'provenance': 'Price/volume anchors from existing saved historical_update_57.json. All generated prices, volumes and fundamentals are synthetic illustrative values. No market API is called.',
        'runtime': 'Replay JSON in order with current timestamps; repeat 60-row timeline at EOF. Restart begins at row zero. Loop transitions are simulated, not actual market events.',
    }
    files['demo_manifest.json'] = manifest
    return {name: json.dumps(data, indent=2) + '\n' for name, data in files.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if committed files differ from deterministic output')
    args = parser.parse_args()
    for name, content in generate().items():
        path = OUTPUT / name
        if args.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit(f'Out-of-date demo data: {path}. Run scripts/generate_demo_data.py.')
        else:
            path.write_text(content)
    print('Demo data verified.' if args.check else 'Saved 10,260 complete demo observations for 57 instruments.')


if __name__ == '__main__':
    main()

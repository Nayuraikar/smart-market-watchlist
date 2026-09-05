"""One-time yfinance collection. Never imported or run by the application.

python scripts/collect_historical_data.py --start 2025-01-01 --end 2026-01-01
End is exclusive. Existing captured rows survive failed/partial downloads.
Optional --snapshots collects fundamentals as of collection time, not as of
historical price dates. Those values are explicitly documented in the manifest.
"""
import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path


def number(value):
    try:
        return str(float(value)) if value is not None and math.isfinite(float(value)) else None
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2025-01-01')
    parser.add_argument('--end', default='2026-01-01')
    parser.add_argument('--snapshots', action='store_true')
    args = parser.parse_args()
    if not date.fromisoformat(args.start) < date.fromisoformat(args.end) <= datetime.now(timezone.utc).date():
        parser.error('Use a completed historical date range; end is exclusive.')
    import yfinance as yf
    data = Path('data')
    if not (data / 'demo_catalog.json').exists():
        data = Path(__file__).resolve().parents[2] / 'data'
    scenarios = data / 'scenarios'
    catalog = json.loads((data / 'demo_catalog.json').read_text())['instruments']
    baseline = json.loads((scenarios / 'historical_baseline_57.json').read_text())
    updates = json.loads((scenarios / 'historical_update_57.json').read_text())
    downloaded, retained = {}, []
    tickers = [stock['ticker'] for stock in catalog]
    frame = yf.download(tickers, start=args.start, end=args.end, interval='1d',
                        auto_adjust=True, group_by='ticker', threads=4, progress=False)
    for ticker in tickers:
        try:
            history = frame[ticker].dropna(subset=['Close', 'Volume'])
            if len(history) < 10:
                raise ValueError('Insufficient historical coverage')
            snapshot = {}
            if args.snapshots:
                try:
                    info = yf.Ticker(ticker).info
                    snapshot = {'market_cap': number(info.get('marketCap')), 'pe_ratio': number(info.get('trailingPE')),
                                'dividend_yield': number(info.get('dividendYield'))}
                except Exception as exc:
                    print(f'{ticker}: snapshot unavailable ({type(exc).__name__}); preserving missing fields', flush=True)
            rows, previous = [], None
            for timestamp, row in history.iterrows():
                price, volume = number(row['Close']), number(row['Volume'])
                if price is None or float(price) <= 0 or volume is None or float(volume) < 0:
                    continue
                observed = timestamp.to_pydatetime()
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if previous is not None:
                    rows.append(dict(price=price, previous_close=previous, volume=volume,
                        market_cap=snapshot.get('market_cap'), pe_ratio=snapshot.get('pe_ratio'),
                        dividend_yield=snapshot.get('dividend_yield'), observed_at=observed.isoformat(),
                        source='yfinance-historical-adjusted'))
                previous = price
            if len(rows) < 9:
                raise ValueError('Insufficient valid observations')
            split = max(2, len(rows) - 60)
            baseline[ticker], updates[ticker] = rows[:split], rows[split:]
            downloaded[ticker] = {'rows': len(rows), 'first_date': rows[0]['observed_at'], 'last_date': rows[-1]['observed_at']}
            print(f'{ticker}: saved {len(rows)} genuine historical observations', flush=True)
        except Exception as exc:
            retained.append(ticker)
            print(f'{ticker}: keeping prior captured data ({type(exc).__name__})', flush=True)
    if not downloaded:
        raise SystemExit('No successful downloads. Existing historical files unchanged.')
    manifest = dict(provider='yfinance', collection_time=datetime.now(timezone.utc).isoformat(),
        requested_start=args.start, requested_end_exclusive=args.end,
        price_basis='Yahoo adjusted daily close; prior close is previous adjusted observation',
        fundamentals='Collection-time snapshot, not historical daily fundamentals' if args.snapshots else 'Not supplied by historical candles; null, never fabricated',
        downloaded=downloaded, retained_prior_captures=retained,
        runtime='Offline replay only; no yfinance calls from startup, API or worker')
    for name, content in [('historical_baseline_57.json', baseline), ('historical_update_57.json', updates), ('historical_manifest.json', manifest)]:
        target = scenarios / name
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(content, indent=2) + '\n')
        temporary.replace(target)
    print(f'Collection complete: {len(downloaded)} refreshed; {len(retained)} retained.', flush=True)


if __name__ == '__main__':
    main()

import { useId, useState } from 'react';
import { PriceHistoryPoint } from '../../types/instrument';

const priceLabel = (value: number) => `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
const timeLabel = (value: string) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

export default function PriceHistoryChart({ points, ticker }: { points: PriceHistoryPoint[]; ticker: string }) {
  const [range, setRange] = useState(180);
  const [selected, setSelected] = useState<number | null>(null);
  const gradientId = useId();
  const visible = points.slice(-range);
  if (visible.length < 2) {
    return <section className="bg-white border border-slate-200 rounded-xl p-6"><h2 className="font-bold">Price history</h2><p className="text-sm text-slate-500 mt-2">Waiting for at least two saved observations.</p></section>;
  }
  const prices = visible.map(point => Number(point.price));
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  const padding = Math.max((high - low) * 0.1, high * 0.001);
  const min = low - padding;
  const max = high + padding;
  const x = (index: number) => 70 + index / (prices.length - 1) * 710;
  const y = (price: number) => 220 - (price - min) / (max - min) * 190;
  const line = prices.map((price, index) => `${x(index)},${y(price)}`).join(' ');
  const index = selected === null ? prices.length - 1 : Math.min(selected, prices.length - 1);
  const change = (prices[prices.length - 1] / prices[0] - 1) * 100;
  const color = change >= 0 ? '#059669' : '#e11d48';

  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 space-y-4" aria-label={`${ticker} replayed price history`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Price history</h2>
          <p className="text-xs text-slate-500">Saved historical observations · updates every 5 seconds</p>
        </div>
        <div className="flex gap-1" aria-label="Chart observation range">
          {[30, 90, 180].map(count => <button key={count} type="button" aria-pressed={range === count} onClick={() => { setRange(count); setSelected(null); }} className={`px-3 py-1.5 rounded-lg text-xs font-bold ${range === count ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>{count} points</button>)}
        </div>
      </div>
      <div className="flex flex-wrap justify-between gap-3 text-sm">
        <p className="font-mono font-bold">{priceLabel(prices[index])} <span className="font-sans text-xs font-normal text-slate-500">{timeLabel(visible[index].timestamp)}</span></p>
        <p style={{ color }}>{change >= 0 ? '+' : ''}{change.toFixed(2)}% over {visible.length} observations</p>
      </div>
      <svg viewBox="0 0 800 255" role="img" aria-label={`${ticker}: ${priceLabel(prices[0])} to ${priceLabel(prices[prices.length - 1])}, low ${priceLabel(low)}, high ${priceLabel(high)}`} className="w-full">
        <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity="0.18" /><stop offset="100%" stopColor={color} stopOpacity="0.01" /></linearGradient></defs>
        {[min, (min + max) / 2, max].map(tick => <g key={tick}><line x1="70" x2="780" y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" strokeDasharray="4 4" /><text x="62" y={y(tick) + 4} textAnchor="end" fontSize="11" fill="#64748b">{Math.round(tick).toLocaleString('en-IN')}</text></g>)}
        <polygon points={`70,220 ${line} 780,220`} fill={`url(#${gradientId})`} />
        <polyline points={line} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" />
        <line x1={x(index)} x2={x(index)} y1="30" y2="220" stroke="#94a3b8" strokeDasharray="3 3" />
        <circle cx={x(index)} cy={y(prices[index])} r="4" fill={color} />
        <text x="70" y="247" fontSize="11" fill="#64748b">{timeLabel(visible[0].timestamp)}</text>
        <text x="780" y="247" textAnchor="end" fontSize="11" fill="#64748b">{timeLabel(visible[visible.length - 1].timestamp)}</text>
      </svg>
      <label className="block text-xs text-slate-500">Explore an observation
        <input className="block w-full mt-2 accent-emerald-600" type="range" min="0" max={visible.length - 1} value={index} onChange={event => setSelected(Number(event.target.value))} aria-label="Explore saved price observation" aria-valuetext={`${priceLabel(prices[index])}, ${timeLabel(visible[index].timestamp)}`} />
      </label>
      <p className="text-xs text-slate-500">Low {priceLabel(low)} · High {priceLabel(high)} · Observations are evenly spaced; historical sessions are compressed into simulation ticks.</p>
    </section>
  );
}

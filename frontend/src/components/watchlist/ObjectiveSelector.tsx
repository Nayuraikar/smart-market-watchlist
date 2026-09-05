import { Objective } from '../../types/market';

interface ObjectiveSelectorProps {
  currentObjective: Objective;
  onChange: (obj: Objective) => void;
}
const OBJECTIVES: { value: Objective; label: string; description: string }[] = [
  {
    value: 'GROWTH',
    label: 'Growth',
    description: 'The change feed prioritizes events relevant to a growth-oriented investor.',
  },
  {
    value: 'VALUE',
    label: 'Value',
    description: 'The same underlying events are evaluated through the value lens.',
  },
  {
    value: 'STABILITY',
    label: 'Stability',
    description: 'The same underlying events are evaluated through the stability lens.',
  },
];

export default function ObjectiveSelector({ currentObjective, onChange }: ObjectiveSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Viewing objective"
      className="inline-flex p-1 bg-slate-100 rounded-lg border border-slate-200 gap-1 shadow-inner"
    >
      {OBJECTIVES.map(({ value, label, description }) => {
        const isActive = currentObjective === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            aria-pressed={isActive}
            title={`${label}: ${description}`}
            className={`
              flex items-center justify-center px-3 sm:px-5 py-2 rounded-md text-xs font-bold transition-all duration-150
              focus:outline-none focus:ring-2 focus:ring-emerald-500
              ${isActive
                ? 'bg-white text-emerald-700 shadow-sm border border-slate-200'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }
            `}
          >
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );
}

import { Objective } from '../../types/market';
import { TrendingUp, DollarSign, Shield } from 'lucide-react';

interface ObjectiveSelectorProps {
  currentObjective: Objective;
  onChange: (obj: Objective) => void;
}

const OBJECTIVES: { value: Objective; label: string; description: string; icon: typeof TrendingUp }[] = [
  {
    value: 'GROWTH',
    label: 'Growth',
    description: 'Revenue, earnings & momentum',
    icon: TrendingUp,
  },
  {
    value: 'VALUE',
    label: 'Value',
    description: 'Fundamentals, multiples & yield',
    icon: DollarSign,
  },
  {
    value: 'STABILITY',
    label: 'Stability',
    description: 'Low volatility & balance sheet strength',
    icon: Shield,
  },
];

export default function ObjectiveSelector({ currentObjective, onChange }: ObjectiveSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Viewing objective"
      className="flex flex-col sm:flex-row gap-2"
    >
      {OBJECTIVES.map(({ value, label, description, icon: Icon }) => {
        const isActive = currentObjective === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            aria-pressed={isActive}
            title={`${label}: ${description}`}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold
              transition-all border
              focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500
              ${isActive
                ? 'bg-white text-blue-700 border-blue-300 shadow-sm ring-1 ring-blue-200'
                : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-white hover:text-slate-900 hover:border-slate-300 hover:shadow-sm'
              }
            `}
          >
            <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} aria-hidden="true" />
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );
}

import type { OddsPoint } from '../types';

type Props = {
  history: OddsPoint[] | undefined;
};

const width = 520;
const height = 240;
const padding = 32;

export function OddsChart({ history }: Props) {
  if (!history || history.length === 0) {
    return <div className="text-sm text-slate-400">No price history yet</div>;
  }

  const points = history.map((h, idx) => ({
    x: (idx / Math.max(history.length - 1, 1)) * (width - padding * 2) + padding,
    y: height - (h.price_yes * (height - padding * 2) + padding),
    prob: h.price_yes,
    ts: h.timestamp
  }));
  const latest = history[history.length - 1];
  const grid = [0.25, 0.5, 0.75];

  return (
    <div className="rounded-xl border border-slate-800 bg-gradient-to-b from-sky-500/10 via-slate-900/70 to-slate-900/70 p-4 shadow-inner">
      <div className="mb-2 flex items-center justify-between text-sm text-slate-300">
        <span>YES price</span>
        <span>{(latest.price_yes * 100).toFixed(1)}%</span>
      </div>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id="lineGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
          </linearGradient>
        </defs>
        {grid.map((g) => {
          const y = height - (g * (height - padding * 2) + padding);
          return (
            <line
              key={g}
              x1={padding}
              x2={width - padding}
              y1={y}
              y2={y}
              stroke="#1f2937"
              strokeDasharray="4 4"
            />
          );
        })}
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="#334155"
          strokeWidth="1"
        />
        <line
          x1={padding}
          y1={padding}
          x2={padding}
          y2={height - padding}
          stroke="#334155"
          strokeWidth="1"
        />
        <polyline
          fill="url(#lineGradient)"
          stroke="none"
          points={[
            `${padding},${height - padding}`,
            ...points.map((p) => `${p.x},${p.y}`),
            `${width - padding},${height - padding}`
          ].join(' ')}
          opacity="0.7"
        />
        <polyline
          fill="none"
          stroke="#38bdf8"
          strokeWidth="2.5"
          points={points.map((p) => `${p.x},${p.y}`).join(' ')}
        />
        {points.map((p, idx) => (
          <g key={p.ts ?? idx}>
            <circle cx={p.x} cy={p.y} r="3.5" fill="#38bdf8" stroke="#0ea5e9" strokeWidth="1.2" />
            <text x={p.x + 6} y={p.y - 6} className="text-xs" fill="#cbd5e1">
              {(p.prob * 100).toFixed(0)}%
            </text>
          </g>
        ))}
        <text
          x={width - padding}
          y={height - padding + 18}
          textAnchor="end"
          className="text-xs"
          fill="#cbd5e1"
        >
          time →
        </text>
        <text x={padding - 12} y={padding - 10} textAnchor="end" className="text-xs" fill="#cbd5e1">
          prob
        </text>
      </svg>
    </div>
  );
}

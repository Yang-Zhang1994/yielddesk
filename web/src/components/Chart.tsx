import type { Line } from '../types'

const W = 640
const H = 260
const PAD = { left: 48, right: 12, top: 12, bottom: 28 }
const COLORS = ['#2563eb', '#dc2626', '#059669', '#d97706']

/** Line chart in plain SVG. Spreads (in bp) get a zero line, so inversion is visible at a glance. */
export function Chart({ lines, unit }: { lines: Line[]; unit: '%' | 'bp' }) {
  const all = lines.flatMap((l) => l.points)
  if (all.length < 2) return null
  const dates = [...new Set(all.map((p) => p.date))].sort()
  const values = all.map((p) => p.value)
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  if (unit === 'bp') { lo = Math.min(lo, 0); hi = Math.max(hi, 0) }
  if (hi === lo) { hi += 1; lo -= 1 }
  const x = (d: string) => PAD.left + (dates.indexOf(d) / (dates.length - 1)) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + ((hi - v) / (hi - lo)) * (H - PAD.top - PAD.bottom)
  const ticks = [lo, (lo + hi) / 2, hi]

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={lines.map((l) => l.label).join(', ')}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" className="tick">{t.toFixed(unit === 'bp' ? 0 : 2)}</text>
          </g>
        ))}
        {unit === 'bp' && <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} className="zero" />}
        <text x={PAD.left} y={H - 8} className="tick">{dates[0]}</text>
        <text x={W - PAD.right} y={H - 8} textAnchor="end" className="tick">{dates[dates.length - 1]}</text>
        {lines.map((l, i) => (
          <polyline key={l.series + i} data-testid="series-line" fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth={2}
            points={l.points.map((p) => `${x(p.date).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')} />
        ))}
      </svg>
      <figcaption>
        {lines.map((l, i) => (
          <span key={l.series + i} className="legend"><i style={{ background: COLORS[i % COLORS.length] }} />{l.label}</span>
        ))}
        <span className="unit">{unit === 'bp' ? 'basis points' : 'percent'}</span>
      </figcaption>
    </figure>
  )
}

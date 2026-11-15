import { fmt, fmtDelta, METRIC_KEYS, METRICS, TRUST_LIMIT } from '../meta'
import type { History } from '../useTelemetry'
import type { Frame, MetricKey } from '../types'
import { StatusBadge, type Tone } from './Status'

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <svg className="spark" aria-hidden="true" />
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, Math.abs(max) * 0.02, 0.1)
  const mid = (max + min) / 2
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * 100).toFixed(2)},${(14 - ((v - mid) / span) * 24).toFixed(2)}`)
    .join(' ')
  return (
    <svg className="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

interface Props {
  frame: Frame
  history: History
  onOpen: (key: MetricKey) => void
}

export function VitalsGrid({ frame, history, onOpen }: Props) {
  return (
    <section aria-label="Vitals" className="vitals-grid">
      {METRIC_KEYS.map((key) => {
        const v = frame.vitals[key]
        const meta = METRICS[key]
        const untrusted = v.sqi < TRUST_LIMIT
        const tone: Tone = untrusted ? 'none' : v.status
        return (
          <button key={key} type="button" className={`card vital tone-edge-${tone}`} onClick={() => onOpen(key)}>
            <span className="vital-name">{meta.name}</span>
            {untrusted ? (
              <span className="vital-value vital-untrusted">Sensor check</span>
            ) : (
              <span className="vital-value num">
                <b>{fmt(v.value, meta.decimals)}</b>
                <small>{v.unit}</small>
              </span>
            )}
            <span className="vital-delta num muted">
              {untrusted ? 'Reading not trusted' : `${fmtDelta(v.delta, meta.decimals)} vs baseline`}
            </span>
            <span className={`spark-wrap tone-${tone}`}>
              <Sparkline values={history[key]} />
            </span>
            <StatusBadge tone={tone} />
          </button>
        )
      })}
    </section>
  )
}

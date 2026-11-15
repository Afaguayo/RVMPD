import { STATUS_WORD } from '../meta'
import type { LinkMode } from '../useTelemetry'
import type { Frame } from '../types'
import { StatusIcon } from './Status'

export type ViewMode = 'console' | 'hud'

interface Props {
  frame: Frame
  mode: LinkMode
  view: ViewMode
  onView: (v: ViewMode) => void
  onRadiation: () => void
}

export function StatusBar({ frame, mode, view, onView, onRadiation }: Props) {
  const { global, radiation } = frame
  const pct = (n: number) => Math.round(n * 100)
  return (
    <header className="statusbar">
      <div className="statusbar-row">
        <h1 className="brand">VITALIS</h1>
        <span className={`global tone-${global.status}`}>
          <StatusIcon tone={global.status} size={18} />
          <span>{STATUS_WORD[global.status]}</span>
        </span>
        <div className="segmented" role="group" aria-label="Display mode">
          {(['console', 'hud'] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => onView(v)}>
              {v === 'console' ? 'Console' : 'HUD'}
            </button>
          ))}
        </div>
      </div>
      <div className="statusbar-row statusbar-meta">
        <button
          type="button"
          className={`pill tone-${radiation.status}`}
          onClick={onRadiation}
          aria-label={`Radiation ${STATUS_WORD[radiation.status]}: ${radiation.dose_rate_usv_h} microsieverts per hour, ${radiation.dose_total_msv} millisieverts total`}
        >
          <StatusIcon tone={radiation.status} />
          <span className="num">
            {radiation.dose_rate_usv_h.toFixed(1)} µSv/h · {radiation.dose_total_msv.toFixed(3)} mSv
          </span>
        </button>
        <span className="badge num">
          SQI {pct(global.sqi)}% · {pct(global.confidence)}% conf
        </span>
        <span className="badge">Link {global.link}</span>
        {mode === 'demo' && <span className="badge badge-demo">Demo data</span>}
      </div>
    </header>
  )
}

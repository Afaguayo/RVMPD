import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { BodyFigure, type SheetTarget } from './components/BodyFigure'
import { BottomSheet } from './components/BottomSheet'
import { CheckIn } from './components/CheckIn'
import { DemoControl } from './components/DemoControl'
import { Hud } from './components/Hud'
import { Insights } from './components/Insights'
import { Oscilloscope } from './components/Oscilloscope'
import { SpaceWeather } from './components/SpaceWeather'
import { StoredData } from './components/StoredData'
import { StatusBar, type ViewMode } from './components/StatusBar'
import { Tasks } from './components/Tasks'
import { VitalsGrid } from './components/VitalsGrid'
import { METRICS, type SheetKey } from './meta'
import { useTelemetry } from './useTelemetry'
import type { Checkin, MetricKey } from './types'

const isSheetKey = (m: string): m is MetricKey | 'radiation' => m in METRICS

export default function App() {
  const { frame, mode, history, waves, setScenario } = useTelemetry()
  const [view, setView] = useState<ViewMode>('console')
  const [sheet, setSheet] = useState<SheetTarget | null>(null)
  const [checkins, setCheckins] = useState<Checkin[]>([])
  const redSeen = useRef(new Set<string>())

  const closeSheet = useCallback(() => setSheet(null), [])
  const openMetric = useCallback((key: SheetKey) => setSheet({ title: key === 'mood' ? 'Sleep and mood' : METRICS[key].name, keys: [key] }), [])

  const loadCheckins = useCallback(() => {
    api.checkins().then(setCheckins).catch(() => undefined)
  }, [])
  useEffect(loadCheckins, [loadCheckins])

  // Open the sheet once per red alert. Tracked by metric so a backend that re-issues alert ids cannot reopen it.
  useEffect(() => {
    if (!frame) return
    const active = new Set(frame.alerts.filter((a) => a.level === 'red').map((a) => a.metric))
    for (const m of redSeen.current) if (!active.has(m)) redSeen.current.delete(m)
    for (const m of active) {
      if (redSeen.current.has(m)) continue
      redSeen.current.add(m)
      if (isSheetKey(m)) openMetric(m)
    }
  }, [frame, openMetric])

  if (!frame) {
    return (
      <div className="app">
        <p className="connecting" role="status">Connecting to telemetry…</p>
      </div>
    )
  }

  return (
    <div className="app">
      <StatusBar frame={frame} mode={mode} view={view} onView={setView} onRadiation={() => openMetric('radiation')} />
      <main>
        <Oscilloscope waves={waves} />
        {view === 'hud' ? (
          <Hud frame={frame} />
        ) : (
          <>
            <VitalsGrid frame={frame} history={history} onOpen={openMetric} />
            <Insights />
          </>
        )}
        <BodyFigure frame={frame} onOpen={setSheet} />
        <SpaceWeather />
        <CheckIn checkins={checkins} onSaved={loadCheckins} />
        <Tasks />
        <StoredData />
        <DemoControl current={frame.scenario} onSelect={setScenario} />
      </main>
      <BottomSheet target={sheet} frame={frame} latestCheckin={checkins[0]} onClose={closeSheet} />
    </div>
  )
}

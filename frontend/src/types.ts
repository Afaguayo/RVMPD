export type Status = 'green' | 'amber' | 'red'

export type MetricKey = 'hr' | 'hrv_rmssd' | 'spo2' | 'temp' | 'resp_rate' | 'bp_sys'

export interface Vital {
  value: number
  unit: string
  baseline: number
  delta: number
  status: Status
  p_adj: number
  sqi: number
}

export interface Wave {
  fs: number
  ecg: number[]
  ppg: number[]
  resp: number[]
}

export interface Radiation {
  dose_rate_usv_h: number
  dose_total_msv: number
  status: Status
}

export interface Global {
  status: Status
  confidence: number
  sqi: number
  link: string
}

export interface Alert {
  id: string
  t: number
  metric: string
  level: Status
  origin: 'physiological' | 'artifact'
  title: string
  explanation: string
  guidance: string[]
}

export interface Frame {
  type: 'frame'
  t: number
  scenario: string
  wave: Wave
  vitals: Record<MetricKey, Vital>
  radiation: Radiation
  global: Global
  alerts: Alert[]
}

export interface Scenario {
  id: string
  name: string
  description: string
}

export interface Checkin {
  id: number | string
  t: string
  mood: number
  sleep_hours: number
  note: string
}

export interface SpaceWeather {
  source: string
  proton_flux_pfu: number
  s_scale: number
  updated: string
}

export interface HistoryPoint {
  t: string
  value: number
  status: Status
}

export interface HistoryResponse {
  metric: string
  points: HistoryPoint[]
}

export interface AlertLogEntry {
  id: number | string
  t: string
  metric: string
  level: Status
  origin: Alert['origin']
  title: string
}

export interface Stats {
  rows: number
  first: string
  last: string
  size_kb: number
}

export type Likelihood = 'low' | 'medium' | 'high'

export interface Finding {
  condition: string
  likelihood: Likelihood
  evidence: string[]
  action: string
}

export interface AnalysisReport {
  id: number
  t: string
  window_minutes: number
  engine: 'local' | 'llm'
  model: string | null
  summary: string
  findings: Finding[]
  facts: string[]
  data_points: number
  disclaimer: string
}

'use client'

import { useState, useEffect, useTransition, useRef, useMemo } from 'react'
import {
  WatershedSummary,
  WatershedDetail,
  BasinSummary,
  LiveRiskResult,
  IoTReading,
  DataStatus,
  MwsGeoJsonCollection,
  MwsGeoJsonFeature,
  LulcBasinSummary,
  WaterQualityRecord,
  WaterQualitySummary,
  EvidenceItem,
  MwsReport,
  BasinReport,
  MonthlyHealthPoint,
  BatchUploadResponse,
  ProcessedPhotoResult,
  ObservationMarkerData,
  WatershedInterventions,
  WatershedRisk,
  WatershedLULC,
  WatershedCropAdvisory,
} from '../lib/types'
import {
  fetchWatersheds,
  fetchBasinSummary,
  fetchWatershedProfile,
  fetchLatestTelemetry,
  postLiveTelemetry,
  simulateTelemetryInference,
  fetchMwsBoundariesGeoJson,
  fetchLulcSummary,
  fetchWaterQualitySummary,
  fetchWaterQualityMws,
  fetchCropAdvisory,
  fetchFieldObservations,
  uploadFieldPhotos,
  fetchMwsReport,
  fetchBasinReport,
  getMwsReportCsvUrl,
  getBasinReportCsvUrl,
} from '../lib/api'
import { GisMap } from '../components/GisMap'
import { Gis3DTerrain } from '../components/Gis3DTerrain'
import { useLanguage } from '../lib/i18n/LanguageContext'
import { LanguageSelector } from '../components/LanguageSelector'
import { Translations } from '../lib/i18n/types'
import { CropSuggestions } from '../components/CropSuggestions'
import { CropIntelligenceScreen } from '../components/CropIntelligenceScreen'
import { Language, translations } from '../lib/translations'

type Mode = 'simulation' | 'live'
type Screen =
  | 'Dashboard'
  | 'Water Quality'
  | 'Crop Intelligence'
  | 'IoT Network'
  | 'Micro-Watershed Profile'
  | 'GIS Explorer'
  | 'LULC Analysis'
  | 'Field Observations'
  | 'Reports & Exports'

const screens: Screen[] = [
  'Dashboard',
  'Water Quality',
  'Crop Intelligence',
  'IoT Network',
  'Micro-Watershed Profile',
  'GIS Explorer',
  'LULC Analysis',
  'Field Observations',
  'Reports & Exports',
]

const navIcons: Record<Screen, string> = {
  Dashboard: '▦',
  'Water Quality': '≋',
  'Crop Intelligence': '🌱',
  'IoT Network': '⌁',
  'Micro-Watershed Profile': '⌂',
  'GIS Explorer': '⌖',
  'LULC Analysis': '▤',
  'Field Observations': '◉',
  'Reports & Exports': '⇩',
}

const modeCopy = {
  simulation: {
    label: 'Simulation',
    source: 'Synthetic inputs',
    detail: 'Model 1 & Model 2 Pipeline',
    status: 'Scenario active',
  },
  live: {
    label: 'Live IoT',
    source: 'Live sensor telemetry',
    detail: 'Online Model 2 Isolation Forest',
    status: 'Live pipeline active',
  },
}

const CHRONO_MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatChronological12Months(trend: MonthlyHealthPoint[]): (MonthlyHealthPoint & { displayMonth: string; displayYear: number })[] {
  if (!trend || trend.length === 0) return []
  const firstPt = trend[0]
  let startMonthIdx = CHRONO_MONTH_NAMES.indexOf(firstPt.month)
  if (startMonthIdx === -1) startMonthIdx = 9 // Default October
  const baseYear = firstPt.year || 2024

  return trend.slice(0, 12).map((pt, i) => {
    const totalMonthIdx = startMonthIdx + i
    const monthIdx = totalMonthIdx % 12
    const yearOffset = Math.floor(totalMonthIdx / 12)
    const displayMonth = CHRONO_MONTH_NAMES[monthIdx]
    const displayYear = baseYear + yearOffset
    return {
      ...pt,
      displayMonth,
      displayYear,
    }
  })
}

function SourceBadge({ mode, small = false }: { mode: Mode; small?: boolean }) {
  const { dict } = useLanguage()
  const sourceLabel = mode === 'live' ? dict.header.liveIot : dict.header.simulation
  return (
    <span className={`source-badge ${mode} ${small ? 'small' : ''}`}>
      <span className="source-dot" />
      {sourceLabel}
    </span>
  )
}

function ConnectionStatusBadge({
  status,
  timestamp,
}: {
  status: 'CONNECTING' | 'CONNECTED' | 'OFFLINE / NO DATA'
  timestamp?: string | null
}) {
  const isConn = status === 'CONNECTED'
  const isConnecting = status === 'CONNECTING'

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '3px 8px',
          borderRadius: '4px',
          fontSize: '10px',
          fontWeight: 800,
          letterSpacing: '0.04em',
          background: isConn ? '#e8f5e9' : isConnecting ? '#eff6ff' : '#ffebee',
          border: `1px solid ${isConn ? '#2e7d32' : isConnecting ? '#3b82f6' : '#ba1a1a'}`,
          color: isConn ? '#1b5e20' : isConnecting ? '#1d4ed8' : '#b71c1c',
          textTransform: 'uppercase',
        }}
      >
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: isConn ? '#2e7d32' : isConnecting ? '#3b82f6' : '#ba1a1a',
          }}
        />
        {status}
      </span>
      {timestamp && (
        <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
          {isConn ? 'Latest:' : 'Last reading:'} {timestamp}
        </span>
      )}
    </div>
  )
}

function Header({
  mode,
  setMode,
  screen,
  setScreen,
  mws,
  setMws,
  watersheds,
  apiStatus,
  lang,
  setLang,
}: {
  mode: Mode
  setMode: (mode: Mode) => void
  screen: Screen
  setScreen: (screen: Screen) => void
  mws: string
  setMws: (mws: string) => void
  watersheds: WatershedSummary[]
  apiStatus: DataStatus
  lang: Language
  setLang: (lang: Language) => void
}) {
  const { dict } = useLanguage()
  const t = translations[lang] || translations.en

  const navLabels: Record<string, string> = {
    Dashboard: dict.header.navDashboard,
    'Crop Intelligence': t.screens?.['Crop Intelligence'] || 'Crop Intelligence',
    'Water Quality': dict.header.navWaterQuality,
    'GIS Explorer': dict.header.navGisExplorer,
    'Reports & Exports': dict.header.navReports,
  }

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">⌁</div>
        <div>
          <strong>JALDRISHTI</strong>
          <span>{dict.header.brandSubtitle}</span>
        </div>
      </div>
      <nav className="topnav" aria-label="Primary navigation">
        {['Dashboard', 'Crop Intelligence', 'Water Quality', 'GIS Explorer', 'Reports & Exports'].map((item) => (
          <button
            className={screen === item ? 'active' : ''}
            key={item}
            onClick={() => setScreen(item as Screen)}
          >
            {navLabels[item] || t.screens?.[item] || item}
          </button>
        ))}
      </nav>
      <label className="mws-control">
        <span>{dict.header.mwsLabel}</span>
        <select
          aria-label="Micro-watershed"
          value={mws}
          onChange={(event) => setMws(event.target.value)}
          disabled={apiStatus === 'unavailable' || apiStatus === 'loading'}
        >
          <option value="ALL">
            {apiStatus === 'loading'
              ? dict.header.loadingMws
              : apiStatus === 'unavailable'
              ? dict.header.mwsUnavailable
              : dict.header.allMwsOption}
          </option>
          {watersheds.map((item) => (
            <option key={item.id} value={item.id}>
              {item.MWS} · {item.dominant_class || 'Catchment'} ({item.id})
            </option>
          ))}
        </select>
      </label>
      <div className="mode-control" role="group" aria-label="Data mode">
        <span className="mode-label">{dict.header.dataModeLabel}</span>
        <button
          aria-pressed={mode === 'simulation'}
          className={mode === 'simulation' ? 'selected' : ''}
          onClick={() => setMode('simulation')}
        >
          {dict.header.simulation}
        </button>
        <button
          aria-pressed={mode === 'live'}
          className={mode === 'live' ? 'selected live' : ''}
          onClick={() => setMode('live')}
        >
          {dict.header.liveIot}
        </button>
      </div>
      <LanguageSelector />
    </header>
  )
}

function Sidebar({
  screen,
  setScreen,
  mode,
  apiStatus,
  lang,
}: {
  screen: Screen
  setScreen: (screen: Screen) => void
  mode: Mode
  apiStatus: DataStatus
  lang: Language
}) {
  const { dict } = useLanguage()
  const t = translations[lang] || translations.en

  const screenLabels: Record<Screen, string> = {
    Dashboard: dict.sidebar.dashboard,
    'Crop Intelligence': t.screens?.['Crop Intelligence'] || 'Crop Intelligence',
    'Water Quality': dict.sidebar.waterQuality,
    'IoT Network': dict.sidebar.iotNetwork,
    'Micro-Watershed Profile': dict.sidebar.mwsProfile,
    'GIS Explorer': dict.sidebar.gisExplorer,
    'LULC Analysis': dict.sidebar.lulcAnalysis,
    'Field Observations': dict.sidebar.fieldObs,
    'Reports & Exports': dict.sidebar.reports,
  }

  return (
    <aside className="sidebar">
      <div className="workspace">
        <span className="workspace-kicker">{dict.sidebar.workspaceLabel}</span>
        <strong>{dict.sidebar.shiggaonBasin}</strong>
        <span>{dict.sidebar.karnatakaIndia}</span>
      </div>
      <div className="side-nav">
        {screens.map((item) => (
          <button
            key={item}
            onClick={() => setScreen(item)}
            className={screen === item ? 'current' : ''}
          >
            <span className="nav-icon">{navIcons[item]}</span>
            {screenLabels[item] || t.screens?.[item] || item}
          </button>
        ))}
      </div>
      <div className={`connection-card ${apiStatus === 'unavailable' ? 'live' : mode}`}>
        <div className="connection-title">
          <span className="source-dot" />
          {apiStatus === 'unavailable'
            ? dict.sidebar.apiDisconnected
            : mode === 'simulation'
            ? dict.sidebar.simScenario
            : dict.sidebar.liveTelemetry}
        </div>
        <p>
          {apiStatus === 'unavailable'
            ? dict.sidebar.apiDisconnectedDesc
            : mode === 'simulation'
            ? dict.sidebar.simScenarioDesc
            : dict.sidebar.liveTelemetryDesc}
        </p>
        <span className="last-seen">
          {apiStatus === 'unavailable'
            ? dict.sidebar.statusOffline
            : apiStatus === 'loading'
            ? dict.sidebar.statusConnecting
            : dict.sidebar.statusConnected}
        </span>
      </div>
      <div className="user-card">
        <div className="avatar">RM</div>
        <div>
          <strong>R. Mehta</strong>
          <span>{dict.sidebar.districtAnalyst}</span>
        </div>
        <span>⋮</span>
      </div>
    </aside>
  )
}

function Metric({
  label,
  sublabel,
  value,
  unit,
  trend,
  tone = 'green',
}: {
  label: string
  sublabel?: string
  value: string
  unit?: string
  trend?: string
  tone?: string
}) {
  return (
    <div className="metric">
      <span className="metric-label">
        {label}
        {sublabel && (
          <span
            style={{
              display: 'block',
              fontSize: '8.5px',
              fontWeight: 500,
              letterSpacing: '0.02em',
              textTransform: 'none',
              color: 'var(--muted)',
              marginTop: '1px',
            }}
          >
            {sublabel}
          </span>
        )}
      </span>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      {trend && <span className={`trend ${tone}`}>{trend}</span>}
    </div>
  )
}

function Panel({
  title,
  eyebrow,
  children,
  action,
  onAction,
}: {
  title: string
  eyebrow?: string
  children: React.ReactNode
  action?: string
  onAction?: () => void
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action && (
          <button className="text-action" onClick={onAction}>
            {action} →
          </button>
        )}
      </div>
      {children}
    </section>
  )
}

export function getLocalizedRiskCategory(
  category: string | null | undefined,
  riskDict?: Translations['risk'] | Translations
): string {
  if (!riskDict) return category || 'LOW'
  const rd = 'risk' in riskDict ? riskDict.risk : riskDict
  const cat = (category || 'LOW').toUpperCase()
  if (cat === 'CRITICAL') return rd.critical
  if (cat === 'HIGH') return rd.high
  if (cat === 'MODERATE') return rd.moderate
  if (cat === 'LOW') return rd.low
  return category || rd.low
}

function getDriverDisplay(
  driver?: string,
  scoreOrRiskDict?: number | null | Translations['risk'] | Translations,
  maybeRiskDict?: Translations['risk'] | Translations
) {
  let score: number | null = null
  let riskDict: Translations['risk'] | undefined = undefined

  if (typeof scoreOrRiskDict === 'number' || scoreOrRiskDict === null) {
    score = scoreOrRiskDict
    if (maybeRiskDict) {
      riskDict = 'risk' in maybeRiskDict ? maybeRiskDict.risk : maybeRiskDict
    }
  } else if (scoreOrRiskDict && typeof scoreOrRiskDict === 'object') {
    riskDict = 'risk' in scoreOrRiskDict ? scoreOrRiskDict.risk : scoreOrRiskDict
  }

  if (!driver || driver === 'None') {
    return {
      label: riskDict?.assessedBaseline ?? 'Assessed Baseline',
      icon: '⚖️',
      scoreStr: typeof score === 'number' ? score.toFixed(1) : '—',
    }
  }
  const lower = driver.toLowerCase()
  let icon = '⚡'
  let label = driver
  if (lower.includes('water') || lower.includes('stress')) {
    icon = '💧'
    label = riskDict?.waterStress ?? 'Water Stress'
  } else if (lower.includes('flood') || lower.includes('runoff')) {
    icon = '🌊'
    label = riskDict?.floodRunoff ?? 'Flood / Runoff'
  } else if (lower.includes('eco')) {
    icon = '🌿'
    label = riskDict?.ecosystemPressure ?? 'Ecosystem Pressure'
  } else if (lower.includes('anomaly') || lower.includes('ml')) {
    icon = '🤖'
    label = riskDict?.mlAnomaly ?? 'ML Anomaly'
  }
  return {
    icon,
    label,
    scoreStr: typeof score === 'number' ? score.toFixed(1) : '—',
  }
}

/**
 * Authoritative Risk Category Mapping:
 * Thresholds:
 *   < 40:       LOW
 *   40–<55:     MODERATE
 *   55–<70:     HIGH
 *   >= 70:      CRITICAL
 *
 * Resolves legacy spatial integration inconsistency where units between 55 and 70
 * (such as 4D4F2k2 with risk 67.0) were stored as CRITICAL, ensuring 67.0 displays
 * as HIGH while preserving authoritative baseline categories (e.g. 43.12 -> LOW).
 */
export function getDisplayRiskCategory(
  category: string | null | undefined,
  score: number | null | undefined
): string {
  if (typeof score === 'number') {
    if (score >= 70) return 'CRITICAL'
    if (score >= 55) return 'HIGH'
    if (score < 40) return 'LOW'
  }
  return category || 'LOW'
}

function Dashboard({
  mode,
  setScreen,
  basin,
  watersheds,
  selectedProfile,
  liveTelemetry,
  apiStatus,
  gisBoundaries,
  gisStatus,
  gisError,
  onSelectMws,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  basin: BasinSummary | null
  watersheds: WatershedSummary[]
  selectedProfile: WatershedDetail | null
  liveTelemetry: LiveRiskResult | null
  apiStatus: DataStatus
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  onSelectMws: (mwsId: string) => void
}) {
  const { dict, t } = useLanguage()
  const isLiveMode = mode === 'live'
  const isOffline = apiStatus === 'unavailable'
  const isLoading = apiStatus === 'loading'

  // Interactive triage and map hover state
  const [hoveredMwsId, setHoveredMwsId] = useState<string | null>(null)
  const [showAllPriority, setShowAllPriority] = useState<boolean>(false)
  const [statusTableFilter, setStatusTableFilter] = useState<'priority' | 'all'>('priority')

  // If live mode, verify genuine live telemetry exists
  const hasLiveTelemetry = isLiveMode && liveTelemetry !== null && liveTelemetry.source === 'live' && !liveTelemetry.is_stale
  const isStale = isLiveMode && liveTelemetry !== null && Boolean(liveTelemetry.is_stale)
  const connectionStatus: 'CONNECTING' | 'CONNECTED' | 'OFFLINE / NO DATA' = isOffline
    ? 'OFFLINE / NO DATA'
    : !liveTelemetry
    ? 'CONNECTING'
    : isStale
    ? 'OFFLINE / NO DATA'
    : 'CONNECTED'
  const telemetryUnavailable = isLiveMode && (!hasLiveTelemetry || isStale)

  // Compute display values from REAL backend data when available
  let healthIndexStr = '—'
  let monitoredAreaStr = '—'
  let mwsCountStr = '—'
  let openActionsStr = '—'

  if (isOffline) {
    healthIndexStr = '—'
    monitoredAreaStr = '—'
    mwsCountStr = '—'
    openActionsStr = '—'
  } else if (isLoading) {
    healthIndexStr = '...'
    monitoredAreaStr = '...'
    mwsCountStr = '...'
    openActionsStr = '...'
  } else if (isLiveMode) {
    // In Live mode: strictly show live telemetry state; never fall back to simulation!
    if (hasLiveTelemetry && liveTelemetry && !isStale) {
      healthIndexStr = `${Math.round(100 - liveTelemetry.live_risk_score)}`
      mwsCountStr = liveTelemetry.MWS || liveTelemetry.id
      monitoredAreaStr = basin?.total_area_km2 != null ? `${basin.total_area_km2}` : '966.2'
      openActionsStr =
        liveTelemetry.compound_alert_level === 'HIGH ALERT' ||
        liveTelemetry.compound_alert_level === 'EMERGENCY'
          ? `1 ${dict.dashboard.activeAction}`
          : '0'
    } else {
      healthIndexStr = '—'
      mwsCountStr = '—'
      monitoredAreaStr = basin?.total_area_km2 != null ? `${basin.total_area_km2}` : '966.2'
      openActionsStr = '—'
    }
  } else if (selectedProfile) {
    // Single watershed selected
    const r = selectedProfile.risk?.final_risk_score
    healthIndexStr = r !== undefined ? `${Math.round(100 - r)}` : '—'
    monitoredAreaStr = basin?.total_area_km2 != null ? `${basin.total_area_km2}` : '966.2'
    mwsCountStr = selectedProfile.MWS
    openActionsStr = selectedProfile.interventions?.primary_intervention ? `1 ${dict.dashboard.activeAction}` : '0'
  } else if (basin) {
    // Basin-wide
    healthIndexStr = `${basin.basin_health_index}`
    monitoredAreaStr = `${basin.total_area_km2}`
    mwsCountStr = `${basin.watershed_count}`
    openActionsStr = `${basin.high_count + basin.critical_count}`
  }

  // Real 12-month trend from backend (individual watershed profile or basin-wide)
  const currentTrend = selectedProfile?.monthly_trend || basin?.monthly_trend || []

  // Authoritative Priority Micro-watersheds:
  // Categorically prioritize CRITICAL first (>=70), HIGH second (55–<70), then MODERATE (40–<55),
  // ordered descending by final_risk_score within categories.
  const priorityWatersheds = useMemo(() => {
    const categoryWeight: Record<string, number> = {
      CRITICAL: 4,
      HIGH: 3,
      MODERATE: 2,
      LOW: 1,
    }
    return [...watersheds]
      .map((w) => {
        const display_category = getDisplayRiskCategory(w.risk_category, w.final_risk_score)
        return {
          ...w,
          display_category,
        }
      })
      .filter(
        (w) =>
          w.final_risk_score !== null &&
          (w.display_category === 'CRITICAL' || w.display_category === 'HIGH' || w.display_category === 'MODERATE')
      )
      .sort((a, b) => {
        const catDiff = (categoryWeight[b.display_category] || 0) - (categoryWeight[a.display_category] || 0)
        if (catDiff !== 0) return catDiff
        return (b.final_risk_score || 0) - (a.final_risk_score || 0)
      })
  }, [watersheds])

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {selectedProfile
              ? `MICRO-WATERSHED ${selectedProfile.MWS} (${selectedProfile.id})`
              : dict.dashboard.executiveOverview}
          </span>
          <h1>
            {selectedProfile
              ? `${selectedProfile.MWS} ${dict.dashboard.mwsHealthAndInterventions}`
              : dict.dashboard.watershedHealthAtGlance}
          </h1>
          <p>
            {selectedProfile
              ? `${dict.dashboard.slusiCodeLabel}: ${selectedProfile.MWS} | ${dict.dashboard.gisIdLabel}: ${selectedProfile.id} | ${dict.dashboard.dominantLulcLabel}: ${selectedProfile.lulc?.dominant_class || 'Classified'}`
              : dict.dashboard.decisionSupportSubtitle}
          </p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          {isLiveMode && (
            <ConnectionStatusBadge
              status={connectionStatus}
              timestamp={liveTelemetry?.timestamp}
            />
          )}
          <button className="outline-button" onClick={() => setScreen('Reports & Exports')}>
            {dict.dashboard.exportBriefing} ↗
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc} (
          <code>http://localhost:8000</code>).
        </div>
      )}

      {/* Dedicated Physical ESP32 Live Sensor Strip when in Live IoT Mode */}
      {isLiveMode && (
        <div
          style={{
            background: 'var(--card-bg, #ffffff)',
            border: '1px solid var(--border-color, #e2e8f0)',
            borderRadius: '8px',
            padding: '16px 20px',
            marginBottom: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '10px',
              borderBottom: '1px solid var(--border-color, #f1f5f9)',
              paddingBottom: '10px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '11px', fontWeight: 800, letterSpacing: '0.05em', color: 'var(--muted)' }}>
                PHYSICAL ESP32 TELEMETRY NODE
              </span>
              <code style={{ fontSize: '11px', fontWeight: 700 }}>
                {liveTelemetry?.device_id || 'ESP32_SHIGGAON_NODE_01'}
              </code>
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                · MWS: <strong>{liveTelemetry?.MWS || '4D4F2m3'}</strong> ({liveTelemetry?.id || 'g_mws.240575'})
              </span>
            </div>
            <ConnectionStatusBadge
              status={connectionStatus}
              timestamp={liveTelemetry?.timestamp}
            />
          </div>

          {!hasLiveTelemetry || isStale ? (
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '6px',
                background: '#fffbeb',
                border: '1px solid #fde68a',
                color: '#92400e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '16px' }}>⏳</span>
                <strong>Waiting for live telemetry</strong>
                <span style={{ fontSize: '12px' }}>
                  — Connect physical ESP32 node or send POST to <code>/api/v1/telemetry</code>
                </span>
              </div>
              <span style={{ fontSize: '11px', fontWeight: 700 }}>
                STATUS: {connectionStatus}
              </span>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '12px',
              }}
            >
              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Rainfall</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                  {typeof (liveTelemetry?.rainfall_mm_hr ?? liveTelemetry?.rainfall_mm) === 'number'
                    ? `${(liveTelemetry?.rainfall_mm_hr ?? liveTelemetry?.rainfall_mm ?? 0).toFixed(1)} mm/hr`
                    : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  z-score: {typeof liveTelemetry?.rainfall_z_score === 'number' ? liveTelemetry.rainfall_z_score.toFixed(2) : '—'}
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Soil Moisture</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                  {typeof liveTelemetry?.soil_moisture_pct === 'number'
                    ? `${liveTelemetry.soil_moisture_pct.toFixed(1)} %`
                    : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  saturation index
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Surface Water Level</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                  {typeof liveTelemetry?.water_level_cm === 'number'
                    ? `${liveTelemetry.water_level_cm.toFixed(1)} cm`
                    : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  check-dam level
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Turbidity</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                  {typeof liveTelemetry?.turbidity_ntu === 'number'
                    ? `${liveTelemetry.turbidity_ntu.toFixed(1)} NTU`
                    : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  sediment siltation
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Isolation Forest Anomaly</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: (liveTelemetry?.live_ml_anomaly_score ?? 0) >= 70 ? '#b91c1c' : (liveTelemetry?.live_ml_anomaly_score ?? 0) >= 50 ? '#d97706' : '#15803d' }}>
                  {typeof liveTelemetry?.live_ml_anomaly_score === 'number' ? liveTelemetry.live_ml_anomaly_score.toFixed(1) : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  ML anomaly score
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Compound Alert Level</span>
                <strong style={{ fontSize: '16px', fontWeight: 800, color: liveTelemetry?.compound_alert_level === 'HIGH ALERT' || liveTelemetry?.compound_alert_level === 'EMERGENCY' ? '#b91c1c' : liveTelemetry?.compound_alert_level === 'WARNING' ? '#d97706' : '#15803d' }}>
                  {liveTelemetry?.compound_alert_level || 'NORMAL'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  {liveTelemetry?.compound_event_type || 'Hydrological state'}
                </span>
              </div>

              <div style={{ padding: '10px 12px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--muted)', display: 'block', textTransform: 'uppercase' }}>Final Risk Score</span>
                <strong style={{ fontSize: '18px', fontWeight: 800, color: (liveTelemetry?.live_risk_score ?? 0) >= 55 ? '#b91c1c' : '#15803d' }}>
                  {typeof liveTelemetry?.live_risk_score === 'number' ? liveTelemetry.live_risk_score.toFixed(1) : '—'}
                </strong>
                <span style={{ fontSize: '10.5px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                  {liveTelemetry?.live_risk_category || 'Assessed'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {!isOffline && !isLiveMode && telemetryUnavailable && (
        <div className="notice warning">
          <strong>{dict.dashboard.waitingForLiveTelemetryWarning}</strong> {dict.dashboard.waitingForLiveTelemetryDesc}{' '}
          <code>/api/v1/telemetry</code>.
        </div>
      )}

      {!isOffline && hasLiveTelemetry && liveTelemetry && !isStale && (
        <div
          className="notice"
          style={{
            background:
              liveTelemetry.compound_alert_level === 'HIGH ALERT' || liveTelemetry.compound_alert_level === 'EMERGENCY'
                ? '#ffebee'
                : '#e8f5e9',
            border: `1px solid ${
              liveTelemetry.compound_alert_level === 'HIGH ALERT' || liveTelemetry.compound_alert_level === 'EMERGENCY'
                ? '#ba1a1a'
                : '#2e7d32'
            }`,
          }}
        >
          <strong>{dict.dashboard.liveAlertNoticeTitle.replace('{level}', liveTelemetry.compound_alert_level || '')}</strong> {dict.dashboard.liveAlertMicroWatershed}{' '}
          <code>{liveTelemetry.MWS || liveTelemetry.id}</code> ({liveTelemetry.id}) · {dict.dashboard.liveAlertLiveRisk}: {typeof liveTelemetry.live_risk_score === 'number' ? liveTelemetry.live_risk_score.toFixed(1) : '—'} ({liveTelemetry.live_risk_category}) · {dict.dashboard.liveAlertMlAnomaly}: {typeof liveTelemetry.live_ml_anomaly_score === 'number' ? liveTelemetry.live_ml_anomaly_score.toFixed(1) : '—'} · {dict.dashboard.liveAlertEvent}: {liveTelemetry.compound_event_type}. {dict.dashboard.liveAlertAction}: {liveTelemetry.recommended_action}.
        </div>
      )}

      <div className="metric-grid">
        <Metric
          label={dict.dashboard.healthIndexLabel}
          sublabel={dict.dashboard.healthIndexSublabel}
          value={healthIndexStr}
          unit="/100"
          trend={
            isOffline
              ? dict.dashboard.offlineStatusText
              : isLiveMode
              ? hasLiveTelemetry && liveTelemetry
                ? dict.dashboard.liveTelemetryRiskText.replace('{score}', String(liveTelemetry.live_risk_score))
                : dict.dashboard.waitingForTelemetryText
              : selectedProfile
              ? dict.dashboard.model2RiskText.replace('{score}', String(selectedProfile.risk?.final_risk_score ?? '—'))
              : dict.dashboard.basinAvgRiskText.replace('{score}', String(basin?.average_risk_score ?? '—'))
          }
          tone={
            Number(healthIndexStr) < 50
              ? 'red'
              : Number(healthIndexStr) < 70
              ? 'amber'
              : 'green'
          }
        />
        <Metric
          label={selectedProfile ? dict.dashboard.selectedMwsCodeLabel : dict.dashboard.mwsCountLabel}
          value={mwsCountStr}
          trend={selectedProfile ? `GIS ID: ${selectedProfile.id}` : dict.dashboard.slusiOfficialUnits}
        />
        <Metric
          label={dict.dashboard.monitoredAreaLabel}
          value={monitoredAreaStr}
          unit="km²"
          trend={dict.dashboard.talukBasinExtent}
        />
        <Metric
          label={dict.dashboard.priorityFieldActionsLabel}
          value={openActionsStr}
          trend={
            selectedProfile
              ? selectedProfile.interventions?.risk_category || 'Assessed'
              : `${basin?.critical_count || 0} ${dict.dashboard.criticalCountText}, ${basin?.high_count || 0} ${dict.dashboard.highCountText}`
          }
          tone="red"
        />
      </div>

      <div className="dashboard-map-row">
        <Panel
          title={selectedProfile ? `${dict.dashboard.catchmentOverviewTitle}: ${selectedProfile.MWS}` : dict.dashboard.basinOverviewTitle}
          eyebrow={dict.dashboard.shiggaonGeographyEyebrow}
        >
          <BasinMap
            variant="overview"
            selectedMws={selectedProfile?.MWS}
            selectedId={selectedProfile?.id}
            hoveredId={hoveredMwsId}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            onSelectMws={onSelectMws}
          />
        </Panel>
      </div>

      <div className="dashboard-grid">
        <Panel
          title={dict.dashboard.healthIndexChartTitle}
          eyebrow={mode === 'live' ? dict.dashboard.healthIndexLiveEyebrow : dict.dashboard.healthIndexSimEyebrow}
          action={dict.dashboard.viewQualityAction}
        >
          <div className={`health-chart ${isOffline || telemetryUnavailable ? 'empty' : ''}`}>
            <div className="chart-y">
              <span>100</span>
              <span>75</span>
              <span>50</span>
              <span>25</span>
              <span>0</span>
            </div>
            {isOffline ? (
              <div className="empty-state">
                {dict.dashboard.healthChartEmptyOffline}
                <span>{dict.dashboard.healthChartEmptyOfflineSub}</span>
              </div>
            ) : telemetryUnavailable ? (
              <div className="empty-state">
                {dict.dashboard.healthChartEmptyWaiting}
                <span>{dict.dashboard.healthChartEmptyWaitingSub}</span>
              </div>
            ) : currentTrend.length > 0 ? (
              <>
                <div className="bars">
                  {formatChronological12Months(currentTrend).map((pt, i) => (
                    <div
                      className="bar-wrap"
                      key={`${pt.displayYear}-${pt.displayMonth}-${i}`}
                      title={`${pt.displayMonth} ${pt.displayYear}: Health ${pt.health_index}/100, Risk ${pt.risk_score}`}
                    >
                      <div
                        className="bar"
                        style={{
                          height: `${Math.max(6, Math.min(100, pt.health_index))}%`,
                          background:
                            pt.health_index < 45
                              ? '#ba1a1a'
                              : pt.health_index < 55
                              ? '#ed6c02'
                              : '#1b5e20',
                        }}
                      />
                      <span>{pt.displayMonth}</span>
                    </div>
                  ))}
                </div>
                <div className="chart-line" />
              </>
            ) : (
              <div className="empty-state">
                {isLoading ? dict.dashboard.healthChartEmptyLoading : dict.dashboard.healthChartEmptyNoTrend}
                <span>{isLoading ? dict.dashboard.healthChartEmptyLoadingSub : dict.dashboard.healthChartEmptyWaitingSub}</span>
              </div>
            )}
          </div>
          <div className="legend">
            <span>
              <i className="dot green-dot" />
              {dict.dashboard.healthLegendLabel}
            </span>
            <span className="muted">
              {selectedProfile
                ? `MWS ${selectedProfile.MWS} (${selectedProfile.id}) · ${dict.dashboard.healthLegendMwsSubtitle}`
                : dict.dashboard.healthLegendBasinSubtitle}
            </span>
          </div>
        </Panel>

        <Panel
          title={dict.dashboard.triageTitle}
          eyebrow={dict.dashboard.triageEyebrow}
          action={showAllPriority ? dict.dashboard.triageTop3 : dict.dashboard.triageDecisionMatrix}
          onAction={() => {
            if (showAllPriority) {
              setShowAllPriority(false)
            } else {
              setScreen('Reports & Exports')
            }
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {isLiveMode && hasLiveTelemetry && liveTelemetry && (
              <div
                style={{
                  background:
                    liveTelemetry.compound_alert_level === 'HIGH ALERT' ||
                    liveTelemetry.compound_alert_level === 'EMERGENCY'
                      ? '#fff1f2'
                      : '#f0fdf4',
                  border: `1.5px solid ${
                    liveTelemetry.compound_alert_level === 'HIGH ALERT' ||
                    liveTelemetry.compound_alert_level === 'EMERGENCY'
                      ? '#e11d48'
                      : '#16a34a'
                  }`,
                  borderLeft: `4px solid ${
                    liveTelemetry.compound_alert_level === 'HIGH ALERT' ||
                    liveTelemetry.compound_alert_level === 'EMERGENCY'
                      ? '#be123c'
                      : '#15803d'
                  }`,
                  borderRadius: 6,
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span
                    style={{
                      fontSize: '9px',
                      fontWeight: 800,
                      padding: '2px 7px',
                      borderRadius: 4,
                      background:
                        liveTelemetry.compound_alert_level === 'HIGH ALERT' ||
                        liveTelemetry.compound_alert_level === 'EMERGENCY'
                          ? '#be123c'
                          : '#15803d',
                      color: '#ffffff',
                      textTransform: 'uppercase',
                    }}
                  >
                    LIVE IoT {liveTelemetry.compound_alert_level}
                  </span>
                  <span style={{ fontSize: '12px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                    {liveTelemetry.MWS || liveTelemetry.id} ({liveTelemetry.id})
                  </span>
                </div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a' }}>
                  {liveTelemetry.compound_event_type}
                </div>
                <div style={{ fontSize: '10.5px', color: '#475569' }}>
                  {dict.dashboard.liveAlertAction}: {liveTelemetry.recommended_action}
                </div>
              </div>
            )}

            {isOffline ? (
              <div className="empty-state" style={{ padding: '24px 0' }}>
                {dict.dashboard.healthChartEmptyOffline}
                <span>{dict.dashboard.healthChartEmptyOfflineSub}</span>
              </div>
            ) : isLoading ? (
              <div className="empty-state" style={{ padding: '24px 0' }}>
                {dict.common.loading}...
                <span>{dict.dashboard.healthChartEmptyLoadingSub}</span>
              </div>
            ) : priorityWatersheds.length > 0 ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    maxHeight: showAllPriority ? '520px' : 'none',
                    overflowY: showAllPriority ? 'auto' : 'visible',
                    paddingRight: showAllPriority ? '4px' : '0',
                  }}
                >
                  {(showAllPriority ? priorityWatersheds : priorityWatersheds.slice(0, 3)).map((w, idx) => {
                    const isSelected = selectedProfile?.id === w.id
                    const displayCategory = w.display_category || getDisplayRiskCategory(w.risk_category, w.final_risk_score)
                    const isCritical = displayCategory === 'CRITICAL'
                    const driverInfo = getDriverDisplay(w.primary_driver, w.driver_score, dict.risk)
                    const rank = idx + 1

                    return (
                      <div
                        key={w.id}
                        className="triage-card"
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          onSelectMws(w.id)
                          setScreen('Micro-Watershed Profile')
                        }}
                        onMouseEnter={() => setHoveredMwsId(w.id)}
                        onMouseLeave={() => setHoveredMwsId(null)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onSelectMws(w.id)
                            setScreen('Micro-Watershed Profile')
                          }
                        }}
                        title={`Click to inspect diagnostic dossier for ${w.MWS} (${w.id})`}
                        style={{
                          background: isSelected ? 'linear-gradient(to right, #f0fdf4, #ffffff)' : '#ffffff',
                          border: isSelected
                            ? '1.5px solid #15803d'
                            : isCritical
                            ? '1px solid rgba(186, 26, 26, 0.28)'
                            : '1px solid rgba(217, 119, 6, 0.28)',
                          borderLeft: `4px solid ${isCritical ? '#ba1a1a' : '#d97706'}`,
                          borderRadius: '6px',
                          padding: '11px 13px',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '8px',
                          transition: 'all 0.16s ease',
                          boxShadow: isSelected
                            ? '0 0 0 2px rgba(21, 128, 61, 0.2), 0 3px 10px rgba(0,0,0,0.06)'
                            : '0 1px 3px rgba(0,0,0,0.04)',
                        }}
                      >
                        {/* Header: Rank, Risk Category, MWS Code & GIS ID */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                            <span
                              style={{
                                fontFamily: 'var(--font-mono, monospace)',
                                fontSize: '11px',
                                fontWeight: 800,
                                color: isCritical ? '#ba1a1a' : '#b45309',
                                background: isCritical ? '#fee2e2' : '#fef3c7',
                                padding: '2px 7px',
                                borderRadius: '4px',
                                letterSpacing: '0.02em',
                              }}
                            >
                              #{rank}
                            </span>
                            <span
                              style={{
                                fontSize: '9.5px',
                                fontWeight: 800,
                                letterSpacing: '0.05em',
                                padding: '2px 7px',
                                borderRadius: '4px',
                                textTransform: 'uppercase',
                                background: isCritical ? '#ba1a1a' : '#d97706',
                                color: '#ffffff',
                              }}
                            >
                              {getLocalizedRiskCategory(displayCategory, dict.risk)}
                            </span>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '14px', fontWeight: 800, letterSpacing: '-0.02em', color: '#0f172a' }}>
                              {w.MWS}
                            </div>
                            <div style={{ fontSize: '9.5px', fontFamily: 'var(--font-mono, monospace)', color: 'var(--muted, #64748b)' }}>
                              {w.id}
                            </div>
                          </div>
                        </div>

                        {/* Dual Metric Box: Risk Score + Primary Driver */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.35fr', gap: '8px', alignItems: 'stretch' }}>
                          {/* Risk Score */}
                          <div
                            style={{
                              background: '#f8fafc',
                              border: '1px solid #e2e8f0',
                              borderRadius: '5px',
                              padding: '6px 8px',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'center',
                            }}
                          >
                            <span style={{ fontSize: '8px', fontWeight: 800, color: 'var(--muted, #64748b)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                              {dict.mwsProfile.finalRiskScoreLabel}
                            </span>
                            <div style={{ marginTop: '2px' }}>
                              <strong style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a', fontFamily: 'var(--font-mono, monospace)' }}>
                                {w.final_risk_score !== null ? w.final_risk_score.toFixed(1) : '—'}
                              </strong>
                              <span style={{ fontSize: '10px', color: 'var(--muted, #64748b)', marginLeft: '2px' }}>/ 100</span>
                            </div>
                          </div>

                          {/* Primary Driver */}
                          <div
                            style={{
                              background: '#f8fafc',
                              border: '1px solid #e2e8f0',
                              borderRadius: '5px',
                              padding: '6px 8px',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'center',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '8px', fontWeight: 800, color: 'var(--muted, #64748b)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                {dict.mwsProfile.primaryDriverHeroLabel}
                              </span>
                              <span style={{ fontSize: '11px', fontWeight: 700, fontFamily: 'var(--font-mono, monospace)', color: '#0f172a' }}>
                                {driverInfo.scoreStr}
                              </span>
                            </div>
                            <div style={{ marginTop: '2px', fontSize: '11px', fontWeight: 700, color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {driverInfo.icon} {driverInfo.label}
                            </div>
                          </div>
                        </div>

                        {/* Recommended Action */}
                        <div style={{ marginTop: '1px' }}>
                          <span style={{ fontSize: '8px', fontWeight: 800, color: 'var(--muted, #64748b)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                            {dict.mwsProfile.step3Title}
                          </span>
                          <div style={{ fontSize: '11px', fontWeight: 600, color: '#1e293b', lineHeight: 1.35, marginTop: '2px' }}>
                            {w.primary_intervention || 'Spring recharge and groundwater recharge structures'}
                          </div>
                        </div>

                        {/* Action Affordance */}
                        <div
                          style={{
                            marginTop: '2px',
                            paddingTop: '6px',
                            borderTop: '1px dashed #e2e8f0',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'flex-end',
                            fontSize: '10.5px',
                            fontWeight: 700,
                            color: '#15803d',
                            gap: '4px',
                          }}
                        >
                          <span>{dict.dashboard.triageInspectDossier}</span>
                          <span style={{ fontSize: '12px' }}>→</span>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Footer Controls: Toggle all / Navigate to matrix */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px', paddingTop: '6px' }}>
                  <button
                    type="button"
                    onClick={() => setShowAllPriority((prev) => !prev)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--primary, #1b5e20)',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      padding: '4px 0',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {showAllPriority
                      ? dict.dashboard.triageCollapse
                      : dict.dashboard.triageViewAll.replace('{count}', String(priorityWatersheds.length))}
                  </button>
                  <button
                    type="button"
                    onClick={() => setScreen('Reports & Exports')}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--muted, #64748b)',
                      fontSize: '10.5px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: '4px 0',
                    }}
                  >
                    {dict.dashboard.triageDecisionMatrix} ↗
                  </button>
                </div>
              </>
            ) : (
              <div className="empty-state" style={{ padding: '24px 0' }}>
                {dict.dashboard.triageNoPriority}
                <span>{dict.dashboard.triageNoPrioritySub}</span>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <div className="bottom-grid">
        <Panel
          title={dict.dashboard.statusTableTitle}
          eyebrow={dict.dashboard.statusTableEyebrow.replace('{count}', String(watersheds.length > 0 ? watersheds.length : 66))}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 11 }}>
            <span style={{ color: 'var(--muted)', fontSize: 10 }}>
              {statusTableFilter === 'priority' ? dict.dashboard.statusShowingPriority.replace('{count}', String(priorityWatersheds.length)) : dict.dashboard.statusShowingAll.replace('{count}', String(watersheds.length))}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                onClick={() => setStatusTableFilter('priority')}
                style={{
                  background: statusTableFilter === 'priority' ? '#1b5e20' : '#f1f5f9',
                  color: statusTableFilter === 'priority' ? '#ffffff' : '#334155',
                  border: 'none',
                  borderRadius: 4,
                  padding: '2px 8px',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {dict.dashboard.statusBtnPriority.replace('{count}', String(priorityWatersheds.length))}
              </button>
              <button
                type="button"
                onClick={() => setStatusTableFilter('all')}
                style={{
                  background: statusTableFilter === 'all' ? '#1b5e20' : '#f1f5f9',
                  color: statusTableFilter === 'all' ? '#ffffff' : '#334155',
                  border: 'none',
                  borderRadius: 4,
                  padding: '2px 8px',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {dict.dashboard.statusBtnAll.replace('{count}', String(watersheds.length))}
              </button>
            </div>
          </div>
          <div className="status-table" style={{ maxHeight: '340px', overflowY: 'auto' }}>
            <div className="table-row table-label" style={{ position: 'sticky', top: 0, background: '#fff', zIndex: 1 }}>
              <span>{dict.dashboard.colUnitMws}</span>
              <span>{dict.dashboard.colGisId}</span>
              <span>{dict.dashboard.colHealth}</span>
              <span>{dict.dashboard.colStatus}</span>
            </div>
            {isOffline ? (
              <div className="table-row">
                <span style={{ gridColumn: '1 / -1', textAlign: 'center', opacity: 0.7 }}>
                  {dict.dashboard.tableDataUnavailable}
                </span>
              </div>
            ) : (statusTableFilter === 'priority' ? priorityWatersheds : [...watersheds].sort((a, b) => (b.final_risk_score || 0) - (a.final_risk_score || 0))).length > 0 ? (
              (statusTableFilter === 'priority' ? priorityWatersheds : [...watersheds].sort((a, b) => (b.final_risk_score || 0) - (a.final_risk_score || 0))).map((row) => (
                <div
                  className="table-row"
                  key={row.id}
                  style={{
                    cursor: 'pointer',
                    background: hoveredMwsId === row.id || selectedProfile?.id === row.id ? '#f0fdf4' : 'transparent',
                    transition: 'background 0.15s ease',
                  }}
                  onClick={() => {
                    onSelectMws(row.id)
                    setScreen('Micro-Watershed Profile')
                  }}
                  onMouseEnter={() => setHoveredMwsId(row.id)}
                  onMouseLeave={() => setHoveredMwsId(null)}
                  title={`Click to inspect profile for ${row.MWS} (${row.id})`}
                >
                  <strong>{row.MWS}</strong>
                  <span style={{ fontSize: '0.85em', opacity: 0.8 }}>{row.id}</span>
                  <span>{row.health_index !== null ? `${row.health_index} / 100` : '—'}</span>
                  <span className={`status ${(getDisplayRiskCategory(row.risk_category, row.final_risk_score) || 'stable').toLowerCase()}`}>
                    {getLocalizedRiskCategory(getDisplayRiskCategory(row.risk_category, row.final_risk_score), dict.risk)}
                  </span>
                </div>
              ))
            ) : (
              <div className="table-row">
                <span>{dict.dashboard.tableConnecting}</span>
                <span>—</span>
                <span>—</span>
                <span>—</span>
              </div>
            )}
          </div>
        </Panel>

        <Panel title={dict.dashboard.riskDistTitle} eyebrow={dict.dashboard.riskDistEyebrow}>
          <div className="provenance">
            <div>
              <span>{dict.dashboard.riskDistUnitCount.replace('{count}', String(basin?.watershed_count ?? 66))}</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px 12px', marginTop: 5 }}>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#ba1a1a', display: 'inline-block' }} />
                  {dict.risk.critical}: <strong>{basin?.critical_count ?? 5}</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#ed6c02', display: 'inline-block' }} />
                  {dict.risk.high}: <strong>{basin?.high_count ?? 15}</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#c8961e', display: 'inline-block' }} />
                  {dict.risk.moderate}: <strong>{basin?.moderate_count ?? 17}</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#1b5e20', display: 'inline-block' }} />
                  {dict.risk.low}: <strong>{basin?.low_count ?? 29}</strong>
                </span>
              </div>
            </div>
            <div>
              <span>{dict.dashboard.primaryDriversTitle}</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4 }}>
                <span style={{ fontSize: 11 }}>{dict.risk.waterStress}: <strong>{basin?.primary_risk_drivers?.['Water Stress'] ?? 38} {dict.dashboard.unitsWord}</strong></span>
                <span style={{ fontSize: 11 }}>{dict.risk.mlAnomaly}: <strong>{basin?.primary_risk_drivers?.['ML Anomaly'] ?? 20} {dict.dashboard.unitsWord}</strong></span>
                <span style={{ fontSize: 11 }}>{dict.risk.ecosystemPressure}: <strong>{basin?.primary_risk_drivers?.['Ecosystem Risk'] ?? 8} {dict.dashboard.unitsWord}</strong></span>
              </div>
            </div>
            <div>
              <span>{dict.dashboard.inputSourceLabel}</span>
              <strong>{modeCopy[mode].source}</strong>
            </div>
            <div>
              <span>{dict.dashboard.analyticsEngineLabel}</span>
              <strong>{modeCopy[mode].detail}</strong>
            </div>
            <div>
              <span>{dict.dashboard.canonicalGisLabel}</span>
              <strong>EPSG:32643 · 66 Micro-Watersheds</strong>
            </div>
          </div>
          <button className="outline-button full" onClick={() => setScreen('GIS Explorer')}>
            {dict.dashboard.inspectGisExplorer} →
          </button>
        </Panel>
      </div>
    </>
  )
}


function BasinMap({
  variant,
  selectedMws,
  selectedId,
  hoveredId,
  gisBoundaries,
  gisStatus,
  gisError,
  onSelectMws,
  observationMarker,
  onClearObservationMarker,
}: {
  variant: Screen | 'overview'
  selectedMws?: string
  selectedId?: string
  hoveredId?: string | null
  gisBoundaries?: MwsGeoJsonCollection | null
  gisStatus?: DataStatus
  gisError?: string | null
  onSelectMws?: (mwsId: string) => void
  observationMarker?: ObservationMarkerData | null
  onClearObservationMarker?: () => void
}) {
  return (
    <GisMap
      variant={variant}
      selectedMws={selectedMws}
      selectedId={selectedId}
      hoveredId={hoveredId}
      gisBoundaries={gisBoundaries}
      gisStatus={gisStatus}
      gisError={gisError}
      onSelectMws={onSelectMws}
      observationMarker={observationMarker}
      onClearObservationMarker={onClearObservationMarker}
      height={variant === 'GIS Explorer' ? 560 : variant === 'overview' ? 420 : 440}
    />
  )
}

function DetailScreen({
  screen,
  mode,
  setScreen,
  apiStatus,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  onSelectMws,
  liveTelemetry,
  observationMarker,
  onClearObservationMarker,
  cropAdvisory,
  cropStatus,
}: {
  screen: Screen
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  onSelectMws: (mwsId: string) => void
  liveTelemetry?: LiveRiskResult | null
  observationMarker?: ObservationMarkerData | null
  onClearObservationMarker?: () => void
  cropAdvisory?: WatershedCropAdvisory | null
  cropStatus?: DataStatus
}) {
  const { dict } = useLanguage()
  const isLive = mode === 'live'
  const isOffline = apiStatus === 'unavailable'
  const hasLiveTelemetry = isLive && Boolean(liveTelemetry) && liveTelemetry?.source === 'live'
  const isGisScreen = screen === 'GIS Explorer'
  const [gisMode, setGisMode] = useState<'2D' | '3D'>('2D')

  const titles: Record<Screen, [string, string]> = {
    'Water Quality': [
      dict.subscreens.wqTitle,
      dict.subscreens.wqSubtitle,
    ],
    'IoT Network': [
      dict.subscreens.iotTitle,
      dict.subscreens.iotSubtitle,
    ],
    'Micro-Watershed Profile': [
      dict.mwsProfile.profileTitle,
      dict.mwsProfile.profileSubtitle,
    ],
    'GIS Explorer': [
      'GIS Explorer',
      dict.dashboard.decisionSupportSubtitle,
    ],
    'LULC Analysis': [
      dict.subscreens.lulcTitle,
      dict.subscreens.lulcSubtitle,
    ],
    'Field Observations': [
      dict.subscreens.fieldObsTitle,
      dict.subscreens.fieldObsSubtitle,
    ],
    'Reports & Exports': [
      dict.subscreens.reportsTitle,
      dict.subscreens.reportsSubtitle,
    ],
    'Crop Intelligence': [
      'Water-optimized crop intelligence',
      'Agro-hydrological crop recommendations, drought resilience, and irrigation strategies by catchment.',
    ],
    Dashboard: ['', ''],
  }
  const [title, subtitle] = titles[screen]

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{screen.toUpperCase()} / SHIGGAON BASIN</span>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          <button className="outline-button">{dict.subscreens.exportPrintableDossier}</button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc} ({screen}).
        </div>
      )}

      {!isOffline && isLive && (
        <div className="notice warning">
          <strong>{dict.sidebar.liveTelemetry}.</strong> {dict.sidebar.liveTelemetryDesc}
        </div>
      )}

      {isGisScreen && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px',
          }}
        >
          <div className="mode-control" role="group" aria-label="GIS view mode" style={{ border: '1px solid var(--border)' }}>
            <button
              aria-pressed={gisMode === '2D'}
              className={gisMode === '2D' ? 'selected' : ''}
              onClick={() => setGisMode('2D')}
            >
              2D Map
            </button>
            <button
              aria-pressed={gisMode === '3D'}
              className={gisMode === '3D' ? 'selected' : ''}
              onClick={() => setGisMode('3D')}
            >
              3D Terrain
            </button>
          </div>

          <div
            style={{
              fontSize: '11px',
              color: 'var(--muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {gisMode === '3D' ? (
              <span>
                Copernicus GLO-30 DEM · 30m Grid Surface
                {selectedProfile && (
                  <span style={{ marginLeft: '10px', color: 'var(--primary)', fontWeight: 600 }}>
                    Selected MWS: {selectedProfile.MWS} · GIS ID: {selectedProfile.id}
                  </span>
                )}
              </span>
            ) : (
              <span>
                ESRI Satellite & Vector Overlay
                {observationMarker && (
                  <span style={{ marginLeft: '10px', color: '#0284c7', fontWeight: 600 }}>
                    📍 Field Photo Marker: {observationMarker.filename || 'Active Observation'} ({observationMarker.latitude.toFixed(4)}°N, {observationMarker.longitude.toFixed(4)}°E)
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="detail-hero">
        {isGisScreen && gisMode === '3D' ? (
          <Gis3DTerrain
            selectedMws={selectedProfile?.MWS}
            selectedId={selectedProfile?.id}
            gisBoundaries={gisBoundaries}
            onSelectMws={onSelectMws}
            selectedProfile={selectedProfile}
            onSwitchTo2D={() => setGisMode('2D')}
          />
        ) : (
          <BasinMap
            variant={screen}
            selectedMws={selectedProfile?.MWS}
            selectedId={selectedProfile?.id}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            onSelectMws={onSelectMws}
            observationMarker={observationMarker}
            onClearObservationMarker={onClearObservationMarker}
          />
        )}
        <div className="detail-summary">
          <div>
            <span className="eyebrow">
              {isOffline
                ? 'API OFFLINE'
                : isLive
                ? (hasLiveTelemetry ? 'ONLINE TELEMETRY' : 'AWAITING TELEMETRY')
                : isGisScreen
                ? selectedProfile
                  ? `SELECTED MWS: ${selectedProfile.MWS} · GIS ID: ${selectedProfile.id}`
                  : gisMode === '3D'
                  ? '3D ELEVATION · COPERNICUS DEM'
                  : 'CANONICAL GIS · 66 UNITS'
                : 'MODEL-GENERATED ANALYTICS'}
            </span>
            <h2>
              {isOffline
                ? 'Backend service is unavailable'
                : isLive
                ? (hasLiveTelemetry ? 'Live IoT stream connected' : 'Waiting for gateway telemetry stream')
                : isGisScreen
                ? selectedProfile
                  ? `${selectedProfile.MWS} Catchment Health & Priority`
                  : gisMode === '3D'
                  ? 'Shiggaon Taluk 3D Elevation & Drainage Model'
                  : 'Shiggaon Taluk Micro-Watershed Risk Map'
                : screen === 'Water Quality'
                ? 'Model indicates improving conditions'
                : 'Scenario insight: targeted action can protect the basin'}
            </h2>
            <p>
              {isOffline
                ? 'Please run the backend server at localhost:8000 to stream live model intelligence.'
                : isLive
                ? (hasLiveTelemetry
                  ? `Live sensor stream active for ${liveTelemetry?.MWS || liveTelemetry?.id}. Compound event: ${liveTelemetry?.compound_event_type}. Action: ${liveTelemetry?.recommended_action}`
                  : 'Connect a sensor gateway to resume live pipeline analytics. The interface will not substitute simulated readings.')
                : isGisScreen
                ? selectedProfile
                  ? `SLUSI Code: ${selectedProfile.MWS} | GIS ID: ${selectedProfile.id} | Dominant LULC: ${selectedProfile.lulc?.dominant_class || 'Agriculture'}`
                  : gisMode === '3D'
                  ? 'Interactive 3D elevation surface derived from Copernicus GLO-30 DEM. Visualizes topographic relief, stream drainage networks, and watershed boundaries across Shiggaon Taluk.'
                  : 'Spatial integration of 66 official micro-catchments with Model 1 LULC and Model 2 Risk Engine V4 calibration. Click any polygon to inspect.'
                : 'Use current watershed intelligence to direct field teams toward the highest-impact interventions.'}
            </p>
          </div>
          <div>
            <div className="summary-stats">
              <Metric
                label="HEALTH INDEX"
                sublabel="100 − Risk Score"
                value={
                  isOffline
                    ? '—'
                    : isGisScreen && selectedProfile
                    ? `${selectedProfile.risk?.final_risk_score !== undefined ? Math.round(100 - selectedProfile.risk.final_risk_score) : '—'}`
                    : '62.1'
                }
                unit="/100"
              />
              <Metric
                label={isGisScreen ? (selectedProfile ? 'AREA' : 'WATERSHEDS') : 'SITES REVIEWED'}
                value={
                  isOffline
                    ? '—'
                    : isGisScreen
                    ? selectedProfile
                      ? `${selectedProfile.area_km2 ?? '—'}`
                      : `${gisBoundaries?.total_features ?? 66}`
                    : '—'
                }
                unit={isGisScreen && selectedProfile ? 'km²' : undefined}
              />
              <Metric
                label="DATA STATUS"
                value={isOffline ? 'Offline' : isLive ? (hasLiveTelemetry ? 'Live' : 'Awaiting Telemetry') : 'Scenario'}
              />
            </div>
            {isGisScreen && selectedProfile ? (
              <button
                className="outline-button full"
                style={{ marginTop: 16, background: '#fff', color: 'var(--primary)' }}
                onClick={() => setScreen('Micro-Watershed Profile')}
              >
                Inspect Full Profile ({selectedProfile.MWS}) →
              </button>
            ) : isGisScreen ? (
              <button
                className="outline-button full"
                style={{ marginTop: 16, background: '#fff', color: 'var(--primary)' }}
                onClick={() => onSelectMws('g_mws.240575')}
              >
                Inspect Golden Catchment (4D4F2m3) →
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* CROP SUGGESTIONS BASED ON WATER CONDITIONS */}
      {isGisScreen && (
        <Panel
          title={
            selectedProfile
              ? `Water-Optimized Crop Intelligence: ${selectedProfile.MWS} (${selectedProfile.id})`
              : 'Water-Optimized Crop Intelligence · Select a Catchment'
          }
          eyebrow="AGRO-HYDROLOGICAL DECISION SUPPORT"
          action={selectedProfile ? 'Full Crop Screen' : undefined}
          onAction={() => setScreen('Crop Intelligence')}
        >
          <CropSuggestions
            advisory={cropAdvisory ?? null}
            status={cropStatus ?? 'available'}
            mwsCode={selectedProfile?.MWS}
            mwsId={selectedProfile?.id}
          />
        </Panel>
      )}

      <div className="detail-columns">
        <Panel title="Key indicators" eyebrow="ANALYTICS">
          <div className="indicator-list">
            <div>
              <span>Runoff risk</span>
              <strong className="amber">
                {isOffline
                  ? '—'
                  : isGisScreen && selectedProfile
                  ? selectedProfile.risk?.flood_risk_score !== undefined
                    ? selectedProfile.risk.flood_risk_score > 55
                      ? 'High'
                      : selectedProfile.risk.flood_risk_score > 40
                      ? 'Moderate'
                      : 'Low'
                    : '—'
                  : 'Moderate'}
              </strong>
            </div>
            <div>
              <span>{isGisScreen ? 'Primary Driver' : 'Groundwater recharge'}</span>
              <strong className="green">
                {isOffline
                  ? '—'
                  : isGisScreen && selectedProfile
                  ? selectedProfile.risk?.primary_risk_driver ?? '—'
                  : 'Favorable'}
              </strong>
            </div>
            <div>
              <span>Intervention priority</span>
              <strong className="red">
                {isOffline
                  ? '—'
                  : isGisScreen && selectedProfile
                  ? selectedProfile.interventions?.risk_category ||
                    selectedProfile.risk?.risk_category ||
                    'Assessed'
                  : 'Scenario active'}
              </strong>
            </div>
            <div>
              <span>Data confidence</span>
              <strong>{isOffline ? 'Pending API' : 'High · 91%'}</strong>
            </div>
          </div>
        </Panel>

        <Panel title="Pipeline audit" eyebrow="AUDIT TRAIL">
          <div className="activity-list">
            <div>
              <span>Data timestamp unavailable</span>
              <strong>Field observation ground-truth sync</strong>
            </div>
            <div>
              <span>Pipeline verified</span>
              <strong>Model 1 LULC Sentinel-2 10m classification</strong>
            </div>
            <div>
              <span>Pipeline verified</span>
              <strong>Model 2 Risk Engine V4 calibration (66 Units)</strong>
            </div>
          </div>
          <button className="outline-button full" onClick={() => setScreen('Field Observations')}>
            View field observations
          </button>
        </Panel>
      </div>
    </>
  )
}

function generateRootCauseSummary(
  mwsCode: string,
  risk?: WatershedRisk | null,
  lulc?: WatershedLULC | null,
  profile?: WatershedDetail | null,
  t?: (key: string, params?: Record<string, string | number>) => string,
  dict?: Translations
): string {
  const riskCategory = getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score)
  const localizedCategory = dict ? getLocalizedRiskCategory(riskCategory, dict.risk) : riskCategory
  const finalRisk = risk?.final_risk_score ?? 50.0
  const primaryDriver = risk?.primary_risk_driver || 'Environmental Stress'
  const localizedDriver = dict ? getDriverDisplay(primaryDriver, null, dict.risk).label : primaryDriver
  const rainfallAnomaly = profile?.rainfall_anomaly
  const ndvi = profile?.ndvi
  const slopeMean = profile?.slope_mean
  const agriPct = lulc?.agriculture_pct
  const roundedRisk = finalRisk.toFixed(1)

  const rainText =
    rainfallAnomaly != null
      ? rainfallAnomaly <= -1.0
        ? t ? t('rootCause.rainDeficit', { val: rainfallAnomaly.toFixed(2) }) : `a ${rainfallAnomaly.toFixed(2)}σ precipitation deficit vs historical monthly baseline (2017–2025)`
        : rainfallAnomaly >= 1.0
        ? t ? t('rootCause.rainElevated', { val: rainfallAnomaly.toFixed(2) }) : `elevated monthly precipitation (+${rainfallAnomaly.toFixed(2)}σ vs historical monthly baseline)`
        : t ? t('rootCause.rainAverage', { sign: rainfallAnomaly > 0 ? '+' : '', val: rainfallAnomaly.toFixed(2) }) : `near-average monthly rainfall conditions (${rainfallAnomaly > 0 ? '+' : ''}${rainfallAnomaly.toFixed(2)}σ vs historical baseline)`
      : dict ? dict.rootCause.rainAvailable : 'available precipitation records'

  const vegText =
    ndvi != null
      ? ndvi < 0.35
        ? t ? t('rootCause.vegSuppressed', { val: ndvi.toFixed(3) }) : `suppressed monthly vegetative greenness (Sentinel-2 NDVI ${ndvi.toFixed(3)})`
        : t ? t('rootCause.vegModerate', { val: ndvi.toFixed(3) }) : `moderate monthly vegetative greenness (Sentinel-2 NDVI ${ndvi.toFixed(3)})`
      : dict ? dict.rootCause.vegLevels : 'vegetation index levels'

  const landText =
    agriPct != null && agriPct > 60
      ? t ? t('rootCause.landAgriHigh', { pct: agriPct.toFixed(1) }) : `${agriPct.toFixed(1)}% agricultural land-use corresponds with elevated crop-water requirement`
      : dict ? dict.rootCause.landAgriBaseline : 'catchment land-cover composition contributes steady baseline demand'

  const terrainText =
    slopeMean != null
      ? slopeMean > 8.0
        ? t ? t('rootCause.terrainSteep', { val: slopeMean.toFixed(1) }) : `steeper headwater topography (${slopeMean.toFixed(1)}° mean slope) promotes accelerated surface runoff`
        : t ? t('rootCause.terrainGentle', { val: slopeMean.toFixed(1) }) : `gentle topography (${slopeMean.toFixed(1)}° mean slope) facilitates moderate surface flow`
      : dict ? dict.rootCause.terrainBaseline : 'local terrain characteristics influence runoff patterns'

  if (riskCategory === 'HIGH' || riskCategory === 'CRITICAL') {
    if (primaryDriver === 'Water Stress') {
      return t
        ? t('rootCause.summaryWaterStress', {
            mws: mwsCode,
            category: localizedCategory,
            score: roundedRisk,
            rain: rainText,
            veg: vegText,
            land: landText,
          })
        : `${mwsCode} is currently classified as ${riskCategory} risk (${roundedRisk}/100), with Water Stress as the dominant component. The elevated water-stress signal is associated with ${rainText} and ${vegText}, while ${landText}.`
    } else if (primaryDriver.toLowerCase().includes('flood')) {
      return t
        ? t('rootCause.summaryFlood', {
            mws: mwsCode,
            category: localizedCategory,
            score: roundedRisk,
            terrain: terrainText,
            rain: rainText,
          })
        : `${mwsCode} is currently classified as ${riskCategory} risk (${roundedRisk}/100), with Flood / Runoff susceptibility as the dominant component. The heightened runoff potential is associated with ${terrainText} alongside ${rainText}.`
    } else if (primaryDriver.toLowerCase().includes('ecosystem')) {
      return t
        ? t('rootCause.summaryEcosystem', {
            mws: mwsCode,
            category: localizedCategory,
            score: roundedRisk,
            veg: vegText,
          })
        : `${mwsCode} is currently classified as ${riskCategory} risk (${roundedRisk}/100), with Ecosystem Pressure as the primary component. Environmental stress corresponds with ${vegText} and high anthropogenic land utilization.`
    } else {
      return t
        ? t('rootCause.summaryAnomaly', {
            mws: mwsCode,
            category: localizedCategory,
            score: roundedRisk,
          })
        : `${mwsCode} is currently classified as ${riskCategory} risk (${roundedRisk}/100). The elevated risk profile corresponds with multivariate environmental indicators and seasonal stress patterns across the catchment.`
    }
  } else {
    return t
      ? t('rootCause.summaryStable', {
          mws: mwsCode,
          category: localizedCategory,
          score: roundedRisk,
          driver: localizedDriver,
          rain: rainText,
          slope: slopeMean != null ? `${slopeMean.toFixed(1)}° mean slope` : 'moderate slope',
        })
      : `${mwsCode} is currently classified as ${riskCategory} risk (${roundedRisk}/100), with ${primaryDriver} as the primary component. Environmental indicators indicate stable conditions, with ${rainText} and gentle topography (${slopeMean != null ? slopeMean.toFixed(1) + '° mean slope' : 'moderate slope'}), corresponding with baseline catchment conditions.`
  }
}

function MicroWatershedProfile({
  mode,
  setScreen,
  apiStatus,
  profileStatus,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
  basin,
  cropAdvisory,
  cropStatus,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  profileStatus: DataStatus
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
  basin?: BasinSummary | null
  cropAdvisory?: WatershedCropAdvisory | null
  cropStatus?: DataStatus
}) {
  const { dict, t } = useLanguage()
  const isOffline = apiStatus === 'unavailable' || profileStatus === 'unavailable'
  const isLoading = profileStatus === 'loading'
  const risk = selectedProfile?.risk
  const lulc = selectedProfile?.lulc
  const interventions = selectedProfile?.interventions
  const healthIndex = risk?.final_risk_score !== undefined ? Math.round(100 - risk.final_risk_score) : null

  // Authoritative Model 2 Formulation:
  // Base Risk = 0.35 * Water Stress + 0.35 * Flood Risk + 0.30 * Ecosystem
  // Final Risk = 0.80 * Base Risk + 0.20 * ML Anomaly
  // Effective Weights: Water 28%, Flood 28%, Ecosystem 24%, ML 20%
  const wScore = risk?.water_stress_score ?? 0
  const fScore = risk?.flood_risk_score ?? 0
  const eScore = risk?.ecosystem_risk_score ?? 0
  const mlScore = risk?.ml_anomaly_score ?? 0
  const baseScore = risk?.base_risk_score ?? 0
  const finalScore = risk?.final_risk_score ?? 0

  const wContrib = +(0.28 * wScore).toFixed(2)
  const fContrib = +(0.28 * fScore).toFixed(2)
  const eContrib = +(0.24 * eScore).toFixed(2)
  const mlContrib = +(0.20 * mlScore).toFixed(2)
  const sumContrib = +(wContrib + fContrib + eContrib + mlContrib).toFixed(2)

  const totalShare = sumContrib > 0 ? sumContrib : 1
  const wPctOfFinal = Math.max(0, Math.min(100, (wContrib / totalShare) * 100))
  const fPctOfFinal = Math.max(0, Math.min(100, (fContrib / totalShare) * 100))
  const ePctOfFinal = Math.max(0, Math.min(100, (eContrib / totalShare) * 100))
  const mlPctOfFinal = Math.max(0, Math.min(100, (mlContrib / totalShare) * 100))

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{dict.mwsProfile.eyebrow}</span>
          <h1>
            {selectedProfile ? `${dict.mwsProfile.profileTitle} ${selectedProfile.MWS}` : dict.mwsProfile.profileSelectionTitle}
          </h1>
          <p>
            {selectedProfile
              ? t('mwsProfile.profileSubtitle', { mws: selectedProfile.MWS, id: selectedProfile.id })
              : dict.mwsProfile.selectCatchmentDesc}
          </p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          <button className="outline-button" onClick={() => setScreen('GIS Explorer')}>
            {dict.mwsProfile.viewInGis}
          </button>
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            {dict.mwsProfile.backToDashboard}
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {isLoading && (
        <div className="notice">
          <strong>{dict.mwsProfile.loadingProfile}</strong> {dict.mwsProfile.loadingProfileDesc}
        </div>
      )}

      {/* Top 4 Metric Cards */}
      <div className="metric-grid">
        <Metric
          label={dict.dashboard.healthIndexLabel}
          sublabel={dict.dashboard.healthIndexSublabel}
          value={isOffline || healthIndex === null ? '—' : `${healthIndex}`}
          unit={isOffline || healthIndex === null ? undefined : '/100'}
          trend={
            isOffline || !risk
              ? undefined
              : `${getLocalizedRiskCategory(getDisplayRiskCategory(risk.risk_category, risk.final_risk_score), dict.risk)} ${dict.risk.alert.toUpperCase()}`
          }
          tone={
            getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score) === 'CRITICAL'
              ? 'red'
              : getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score) === 'HIGH'
              ? 'amber'
              : 'green'
          }
        />
        <Metric
          label={dict.mwsProfile.finalRiskScoreLabel}
          value={isOffline || risk?.final_risk_score === undefined ? '—' : `${risk.final_risk_score}`}
          unit={isOffline || risk?.final_risk_score === undefined ? undefined : '/100'}
          trend={
            isOffline || !risk
              ? undefined
              : `${dict.dashboard.primaryDriversTitle}: ${getDriverDisplay(risk.primary_risk_driver, null, dict.risk).label}`
          }
          tone="amber"
        />
        <Metric
          label={dict.mwsProfile.catchmentAreaLabel}
          value={isOffline || selectedProfile?.area_km2 === undefined ? '—' : `${selectedProfile.area_km2}`}
          unit={isOffline || selectedProfile?.area_km2 === undefined ? undefined : 'km²'}
          trend={
            isOffline || typeof selectedProfile?.area_km2 !== 'number'
              ? undefined
              : `${(selectedProfile.area_km2 * 100).toFixed(0)} Ha`
          }
          tone="green"
        />
        <Metric
          label={dict.mwsProfile.dominantLulcMetricLabel}
          value={isOffline || !lulc ? '—' : lulc.dominant_class}
          unit={isOffline || !lulc ? undefined : 'class'}
          trend={
            isOffline || !lulc ? undefined : `${lulc.coverage_category} ${dict.mwsProfile.coverageLabel}`
          }
          tone="green"
        />
      </div>

      {/* Catchment Hero: Map + Summary */}
      <div className="detail-hero">
        <BasinMap
          variant="Micro-Watershed Profile"
          selectedMws={selectedProfile?.MWS}
          selectedId={selectedProfile?.id}
          gisBoundaries={gisBoundaries}
          gisStatus={gisStatus}
          gisError={gisError}
          onSelectMws={onSelectMws}
        />
        <div className="detail-summary">
          <span className="eyebrow">
            {isOffline
              ? dict.mwsProfile.identityCardOfflineEyebrow
              : selectedProfile
              ? t('mwsProfile.identityCardSelectedEyebrow', { id: selectedProfile.id })
              : dict.mwsProfile.identityCardPromptEyebrow}
          </span>
          <h2>
            {isOffline
              ? dict.mwsProfile.identityOfflineTitle
              : selectedProfile
              ? `${dict.mwsProfile.profileTitle} ${selectedProfile.MWS}`
              : dict.mwsProfile.identityPromptTitle}
          </h2>
          <p>
            {isOffline
              ? dict.mwsProfile.identityOfflineDesc
              : selectedProfile
              ? `SLUSI: ${selectedProfile.MWS} | GIS: ${selectedProfile.id} | ${dict.mwsProfile.meanElevationLabel}: ${selectedProfile.elevation_mean ?? '—'}m | ${dict.mwsProfile.meanSlopeLabel}: ${selectedProfile.slope_mean ?? '—'}°`
              : dict.mwsProfile.identityPromptDesc}
          </p>
          <div className="summary-stats">
            <Metric
              label={dict.mwsProfile.healthIndexStat}
              sublabel={dict.dashboard.healthIndexSublabel}
              value={isOffline || healthIndex === null ? '—' : `${healthIndex}`}
              unit="/100"
            />
            <Metric
              label={dict.mwsProfile.riskCategoryStat}
              value={isOffline || !risk ? '—' : getLocalizedRiskCategory(getDisplayRiskCategory(risk.risk_category, risk.final_risk_score), dict.risk)}
            />
            <Metric
              label={dict.mwsProfile.primaryDriverStat}
              value={isOffline || !risk ? '—' : getDriverDisplay(risk.primary_risk_driver, null, dict.risk).label}
            />
          </div>
        </div>
      </div>

      {/* SECTION 1: RISK DECOMPOSITION & COMPONENT ATTRIBUTION */}
      <Panel
        title={dict.mwsProfile.riskDecompositionTitle}
        eyebrow={dict.mwsProfile.riskDecompositionEyebrow}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>
              {dict.mwsProfile.riskDecompSubtitle}
            </span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--surface-low)', padding: '3px 8px', borderRadius: 4, border: '1px solid var(--border)' }}>
              {dict.mwsProfile.riskFormulaLabel}
            </span>
          </div>

          {/* Proportional Stacked Attribution Bar */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.04em' }}>
              <span>{dict.risk.proportionalShare}</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{dict.mwsProfile.finalRiskScoreLabel}: {isOffline || !risk ? '—' : `${risk.final_risk_score} / 100`}</span>
            </div>
            <div style={{ height: 22, display: 'flex', borderRadius: 5, overflow: 'hidden', border: '1px solid var(--border)', background: 'var(--surface-low)' }}>
              <div
                style={{ width: `${wPctOfFinal}%`, background: '#0284c7', transition: 'width 0.3s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 700, overflow: 'hidden', whiteSpace: 'nowrap' }}
                title={`${dict.risk.waterStress}: ${wContrib} pts (${wPctOfFinal.toFixed(1)}% ${dict.risk.ofTotalRisk})`}
              >
                {wPctOfFinal > 12 ? `${dict.risk.waterStress} ${wContrib} pts` : ''}
              </div>
              <div
                style={{ width: `${fPctOfFinal}%`, background: '#0d9488', transition: 'width 0.3s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 700, overflow: 'hidden', whiteSpace: 'nowrap' }}
                title={`${dict.risk.floodRunoff}: ${fContrib} pts (${fPctOfFinal.toFixed(1)}% ${dict.risk.ofTotalRisk})`}
              >
                {fPctOfFinal > 12 ? `${dict.risk.floodRunoff} ${fContrib} pts` : ''}
              </div>
              <div
                style={{ width: `${ePctOfFinal}%`, background: '#16a34a', transition: 'width 0.3s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 700, overflow: 'hidden', whiteSpace: 'nowrap' }}
                title={`${dict.risk.ecosystemPressure}: ${eContrib} pts (${ePctOfFinal.toFixed(1)}% ${dict.risk.ofTotalRisk})`}
              >
                {ePctOfFinal > 12 ? `${dict.risk.ecosystemPressure} ${eContrib} pts` : ''}
              </div>
              <div
                style={{ width: `${mlPctOfFinal}%`, background: '#d97706', transition: 'width 0.3s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 700, overflow: 'hidden', whiteSpace: 'nowrap' }}
                title={`${dict.risk.mlAnomaly}: ${mlContrib} pts (${mlPctOfFinal.toFixed(1)}% ${dict.risk.ofTotalRisk})`}
              >
                {mlPctOfFinal > 8 ? `ML ${mlContrib}` : ''}
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6, marginTop: 6, fontSize: 10 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#0284c7', display: 'inline-block' }} />
                {dict.risk.waterStress}: <strong>{wContrib} pts</strong> (28% wt)
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#0d9488', display: 'inline-block' }} />
                {dict.risk.floodRunoff}: <strong>{fContrib} pts</strong> (28% wt)
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#16a34a', display: 'inline-block' }} />
                {dict.risk.ecosystemPressure}: <strong>{eContrib} pts</strong> (24% wt)
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#d97706', display: 'inline-block' }} />
                {dict.risk.mlAnomaly}: <strong>{mlContrib} pts</strong> (20% wt)
              </span>
            </div>
          </div>

          {/* 4 Component Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10 }}>
            {/* Card 1: Water Stress */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: '#0284c7' }}>{dict.risk.environmentalComponent.toUpperCase()}</span>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>💧 {dict.risk.waterStress}</div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: wScore > 55 ? '#ffe2df' : wScore > 40 ? '#fff0d6' : '#dff1dc', color: wScore > 55 ? 'var(--red)' : wScore > 40 ? '#9d5400' : 'var(--primary)' }}>
                  {getLocalizedRiskCategory(wScore > 70 ? 'CRITICAL' : wScore > 55 ? 'HIGH' : wScore > 40 ? 'MODERATE' : 'LOW', dict.risk)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', margin: '4px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--foreground)' }}>
                  {isOffline || !risk ? '—' : wScore}
                  <small style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>/100</small>
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0284c7' }}>
                  +{wContrib} {dict.risk.ptsFinal}
                </span>
              </div>
              <div style={{ height: 4, background: '#cbd5e1', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
                <div style={{ height: '100%', width: `${Math.min(100, wScore)}%`, background: '#0284c7' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>{dict.risk.weightLabel}: 0.80 × 0.35 = 28%</span>
                <span>{wPctOfFinal.toFixed(1)}% {dict.risk.ofTotalRisk}</span>
              </div>
            </div>

            {/* Card 2: Flood / Runoff */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: '#0d9488' }}>{dict.risk.environmentalComponent.toUpperCase()}</span>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>🌊 {dict.risk.floodRunoff}</div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: fScore > 55 ? '#ffe2df' : fScore > 40 ? '#fff0d6' : '#dff1dc', color: fScore > 55 ? 'var(--red)' : fScore > 40 ? '#9d5400' : 'var(--primary)' }}>
                  {getLocalizedRiskCategory(fScore > 70 ? 'CRITICAL' : fScore > 55 ? 'HIGH' : fScore > 40 ? 'MODERATE' : 'LOW', dict.risk)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', margin: '4px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--foreground)' }}>
                  {isOffline || !risk ? '—' : fScore}
                  <small style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>/100</small>
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0d9488' }}>
                  +{fContrib} {dict.risk.ptsFinal}
                </span>
              </div>
              <div style={{ height: 4, background: '#cbd5e1', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
                <div style={{ height: '100%', width: `${Math.min(100, fScore)}%`, background: '#0d9488' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>{dict.risk.weightLabel}: 0.80 × 0.35 = 28%</span>
                <span>{fPctOfFinal.toFixed(1)}% {dict.risk.ofTotalRisk}</span>
              </div>
            </div>

            {/* Card 3: Ecosystem Pressure */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: '#16a34a' }}>{dict.risk.environmentalComponent.toUpperCase()}</span>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>🌿 {dict.risk.ecosystemPressure}</div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: eScore > 55 ? '#ffe2df' : eScore > 40 ? '#fff0d6' : '#dff1dc', color: eScore > 55 ? 'var(--red)' : eScore > 40 ? '#9d5400' : 'var(--primary)' }}>
                  {getLocalizedRiskCategory(eScore > 70 ? 'CRITICAL' : eScore > 55 ? 'HIGH' : eScore > 40 ? 'MODERATE' : 'LOW', dict.risk)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', margin: '4px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--foreground)' }}>
                  {isOffline || !risk ? '—' : eScore}
                  <small style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>/100</small>
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#16a34a' }}>
                  +{eContrib} {dict.risk.ptsFinal}
                </span>
              </div>
              <div style={{ height: 4, background: '#cbd5e1', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
                <div style={{ height: '100%', width: `${Math.min(100, eScore)}%`, background: '#16a34a' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>{dict.risk.weightLabel}: 0.80 × 0.30 = 24%</span>
                <span>{ePctOfFinal.toFixed(1)}% {dict.risk.ofTotalRisk}</span>
              </div>
            </div>

            {/* Card 4: ML Anomaly */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: '#d97706' }}>{dict.risk.unsupervisedMlModel.toUpperCase()}</span>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>🤖 {dict.risk.mlAnomaly}</div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: mlScore > 50 ? '#ffe2df' : '#dff1dc', color: mlScore > 50 ? 'var(--red)' : 'var(--primary)' }}>
                  {mlScore > 50 ? dict.risk.anomalous : dict.risk.normal}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', margin: '4px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: 'var(--foreground)' }}>
                  {isOffline || !risk ? '—' : mlScore}
                  <small style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>/100</small>
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#d97706' }}>
                  +{mlContrib} {dict.risk.ptsFinal}
                </span>
              </div>
              <div style={{ height: 4, background: '#cbd5e1', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
                <div style={{ height: '100%', width: `${Math.min(100, mlScore)}%`, background: '#d97706' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>{dict.risk.weightLabel}: 0.20 = 20%</span>
                <span>{mlPctOfFinal.toFixed(1)}% {dict.risk.ofTotalRisk}</span>
              </div>
            </div>
          </div>

          {/* Model Combination Summary Footer */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, padding: '10px 14px', background: '#f8fafc', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}>
            <div>
              <span style={{ color: 'var(--muted)' }}>{dict.risk.baseEnvironmentalRisk}: </span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{isOffline || !risk ? '—' : `${baseScore} / 100`}</strong>
              <span style={{ color: 'var(--muted)', fontSize: 10 }}> (80% wt → +{(0.80 * baseScore).toFixed(2)} pts)</span>
            </div>
            <div>
              <span style={{ color: 'var(--muted)' }}>{dict.risk.mlAdjustment}: </span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{isOffline || !risk ? '—' : `+${mlContrib} pts`}</strong>
              <span style={{ color: 'var(--muted)', fontSize: 10 }}> (20% wt)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{dict.risk.calibratedFinalRisk}:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: risk && risk.final_risk_score >= 70 ? 'var(--red)' : risk && risk.final_risk_score >= 55 ? 'var(--amber)' : 'var(--primary)' }}>
                {isOffline || !risk ? '—' : `${finalScore} / 100`}
              </span>
              <span className={`priority ${getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score) === 'CRITICAL' ? 'high' : getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score) === 'HIGH' ? 'medium' : 'low'}`} style={{ padding: '2px 6px', fontSize: 9 }}>
                {getLocalizedRiskCategory(getDisplayRiskCategory(risk?.risk_category, risk?.final_risk_score), dict.risk) || '—'}
              </span>
            </div>
          </div>
        </div>
      </Panel>

      {/* SECTION 2 & 3: "WHY IS THIS MWS AT RISK?" & ROOT CAUSE SYNTHESIS */}
      <Panel
        title={dict.mwsProfile.whyAtRiskTitle}
        eyebrow={dict.mwsProfile.whyAtRiskEyebrow}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Primary Driver Hero Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, padding: '10px 14px', background: 'var(--surface-low)', borderRadius: 6, border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.08em', color: 'var(--muted)' }}>
                {dict.mwsProfile.primaryDriverHeroLabel}
              </span>
              <span style={{ fontSize: 13, fontWeight: 800, color: risk?.primary_risk_driver === 'Water Stress' ? '#0284c7' : risk?.primary_risk_driver?.toLowerCase().includes('flood') ? '#0d9488' : '#16a34a', background: '#fff', padding: '3px 10px', borderRadius: 4, border: '1px solid var(--border)' }}>
                {isOffline || !risk ? '—' : getDriverDisplay(risk.primary_risk_driver, null, dict.risk).label.toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>
              {t('mwsProfile.dominantAccountsFor', {
                pct: (risk?.primary_risk_driver === 'Water Stress' ? wPctOfFinal : risk?.primary_risk_driver?.toLowerCase().includes('flood') ? fPctOfFinal : ePctOfFinal).toFixed(1),
              })}
            </div>
          </div>

          {/* FEATURE 3: Plain-English Deterministic Root Cause Summary */}
          <div style={{ padding: '12px 16px', background: '#f8fafc', borderLeft: '4px solid var(--primary)', borderRadius: '0 6px 6px 0', borderTop: '1px solid var(--border)', borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--primary)' }}>
                {dict.mwsProfile.rootCauseHeading}
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: 'var(--foreground)' }}>
              {isOffline || !selectedProfile
                ? dict.rootCause.offlineFallback
                : generateRootCauseSummary(selectedProfile.MWS, risk, lulc, selectedProfile, t, dict)}
            </p>
          </div>

          {/* 5 Physical Risk Signals Grid */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 8 }}>
              {dict.mwsProfile.physicalSignalsHeading}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {/* Signal 1: Rainfall */}
              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 5, padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>🌧</span>
                  <strong style={{ fontSize: 11 }}>{dict.mwsProfile.signalRainfall}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalRainfallMonthly}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.rainfall_mm == null ? dict.common.noData : `${selectedProfile.rainfall_mm} mm/month`}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalRainfallAnomaly}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)', color: selectedProfile?.rainfall_anomaly != null && selectedProfile.rainfall_anomaly < -1 ? 'var(--red)' : 'inherit' }}>
                      {isOffline || selectedProfile?.rainfall_anomaly == null ? dict.common.noData : `${selectedProfile.rainfall_anomaly > 0 ? '+' : ''}${selectedProfile.rainfall_anomaly}σ vs historical baseline`}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #f1f5f9', fontSize: 9, color: 'var(--muted)' }}>
                  {dict.mwsProfile.signalRainfallSource}
                </div>
              </div>

              {/* Signal 2: Vegetation */}
              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 5, padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>🌿</span>
                  <strong style={{ fontSize: 11 }}>{dict.mwsProfile.signalVeg}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalVegNdvi}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.ndvi == null ? dict.common.noData : `${selectedProfile.ndvi}`}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalVegAnomaly}</span>
                    <strong style={{ fontSize: 10, color: selectedProfile?.ndvi_anomaly != null && selectedProfile.ndvi_anomaly < -0.5 ? 'var(--amber)' : 'var(--primary)' }}>
                      {isOffline || selectedProfile?.ndvi_anomaly == null
                        ? (selectedProfile?.ndvi != null ? (selectedProfile.ndvi < 0.4 ? dict.mwsProfile.signalVegSuppressed : dict.mwsProfile.signalVegModerate) : dict.common.noData)
                        : `${selectedProfile.ndvi_anomaly > 0 ? '+' : ''}${selectedProfile.ndvi_anomaly}σ vs historical baseline`}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #f1f5f9', fontSize: 9, color: 'var(--muted)' }}>
                  {dict.mwsProfile.signalVegSource}
                </div>
              </div>

              {/* Signal 3: Terrain */}
              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 5, padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>⛰</span>
                  <strong style={{ fontSize: 11 }}>{dict.mwsProfile.signalTerrain}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalTerrainSlope}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.slope_mean == null ? dict.common.noData : `${selectedProfile.slope_mean}°`}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalTerrainElevation}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.elevation_mean == null ? dict.common.noData : `${selectedProfile.elevation_mean} m`}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #f1f5f9', fontSize: 9, color: 'var(--muted)' }}>
                  {dict.mwsProfile.signalTerrainSource}
                </div>
              </div>

              {/* Signal 4: Drainage */}
              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 5, padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>🌊</span>
                  <strong style={{ fontSize: 11 }}>{dict.mwsProfile.signalDrainage}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalDrainageDensity}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.drainage_density == null ? dict.common.noData : `${selectedProfile.drainage_density} km/km²`}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalDrainageStreamLen}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                      {isOffline || selectedProfile?.stream_length_km == null ? dict.common.noData : `${selectedProfile.stream_length_km} km`}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #f1f5f9', fontSize: 9, color: 'var(--muted)' }}>
                  {dict.mwsProfile.signalDrainageSource}
                </div>
              </div>

              {/* Signal 5: Land Use */}
              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 5, padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>🏘</span>
                  <strong style={{ fontSize: 11 }}>{dict.mwsProfile.signalLandUse}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalLandUseDominant}</span>
                    <strong style={{ fontSize: 10 }}>
                      {isOffline || !lulc ? dict.common.noData : lulc.dominant_class}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)' }}>{dict.mwsProfile.signalLandUseAgriForest}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                      {isOffline || !lulc || typeof lulc.agriculture_pct !== 'number' ? '—' : `${lulc.agriculture_pct.toFixed(0)}%`} / {isOffline || !lulc || typeof lulc.forest_pct !== 'number' ? '—' : `${lulc.forest_pct.toFixed(0)}%`}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #f1f5f9', fontSize: 9, color: 'var(--muted)' }}>
                  {dict.mwsProfile.signalLandUseSource}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Panel>

      {/* SECTION 4: ACTION LINKAGE (Driver -> Signals -> Targeted Response) */}
      <Panel
        title={dict.mwsProfile.actionLinkageTitle}
        eyebrow={dict.mwsProfile.actionLinkageEyebrow}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* 3-Step Visual Decision Flow */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, alignItems: 'stretch' }}>
            {/* Step 1: Primary Driver */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--muted)', marginBottom: 4 }}>
                {dict.mwsProfile.step1Title}
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--foreground)' }}>
                {isOffline || !risk ? '—' : getDriverDisplay(risk.primary_risk_driver, null, dict.risk).label}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                {dict.mwsProfile.step1DominantScore} <strong>{isOffline || !risk ? '—' : risk.primary_risk_driver === 'Water Stress' ? risk.water_stress_score : risk.primary_risk_driver?.toLowerCase().includes('flood') ? risk.flood_risk_score : risk.ecosystem_risk_score} / 100</strong>
              </div>
              <div style={{ marginTop: 8, fontSize: 10, color: 'var(--primary)', fontWeight: 600 }}>
                {dict.risk.effectiveWeight}: {risk?.primary_risk_driver === 'Water Stress' || risk?.primary_risk_driver?.toLowerCase().includes('flood') ? '28%' : '24%'} {dict.risk.ofTotalRisk}
              </div>
            </div>

            {/* Step 2: Observed Risk Signals */}
            <div style={{ background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--muted)', marginBottom: 4 }}>
                {dict.mwsProfile.step2Title}
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--foreground)' }}>
                {dict.mwsProfile.step2Subtitle}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span>• {dict.mwsProfile.step2RainAnomaly} {selectedProfile?.rainfall_anomaly != null ? `${selectedProfile.rainfall_anomaly > 0 ? '+' : ''}${selectedProfile.rainfall_anomaly}σ vs historical baseline` : dict.common.unavailable}</span>
                <span>• {dict.mwsProfile.step2Ndvi} {selectedProfile?.ndvi != null ? `${selectedProfile.ndvi}` : dict.common.unavailable}</span>
                <span>• {dict.mwsProfile.step2Cropland} {lulc?.agriculture_pct != null ? `${lulc.agriculture_pct.toFixed(1)}%` : dict.common.unavailable}</span>
              </div>
            </div>

            {/* Step 3: Recommended Response */}
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.1em', color: '#16a34a' }}>
                  {dict.mwsProfile.step3Title}
                </span>
                <span className={`priority ${interventions?.risk_category?.toLowerCase() === 'critical' ? 'high' : 'medium'}`} style={{ padding: '2px 6px', fontSize: 8 }}>
                  {getLocalizedRiskCategory(interventions?.risk_category, dict.risk) || dict.mwsProfile.targetedBadge}
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#14532d' }}>
                {interventions?.primary_intervention || (isOffline ? dict.mwsProfile.interventionsOffline : dict.mwsProfile.routineConservation)}
              </div>
              <div style={{ fontSize: 11, color: '#166534', marginTop: 4 }}>
                {dict.mwsProfile.step3Subtitle}
              </div>
            </div>
          </div>

          {/* Action Details Table / List */}
          <div className="action-list">
            <div>
              <span className={`priority ${interventions?.risk_category?.toLowerCase() === 'critical' ? 'high' : 'medium'}`}>
                {dict.mwsProfile.actionPrimaryBadge}
              </span>
              <strong>{interventions?.primary_intervention || (isOffline ? dict.mwsProfile.interventionsOffline : dict.mwsProfile.routineConservation)}</strong>
              <span>{dict.mwsProfile.actionPrimarySubtitle}</span>
              <b>{dict.mwsProfile.actionPrimaryTargeted}</b>
            </div>
            <div>
              <span className="priority medium">{dict.mwsProfile.actionSecondaryBadge}</span>
              <strong>{interventions?.secondary_intervention || (isOffline ? dict.mwsProfile.interventionsOffline : dict.mwsProfile.catchmentStabilization)}</strong>
              <span>{dict.mwsProfile.actionSecondarySubtitle}</span>
              <b>{dict.mwsProfile.actionSecondaryTargeted}</b>
            </div>
            <div>
              <span className="priority low">{dict.mwsProfile.actionLongTermBadge}</span>
              <strong>{interventions?.long_term_intervention || (isOffline ? dict.mwsProfile.interventionsOffline : dict.mwsProfile.rechargeProtection)}</strong>
              <span>{dict.mwsProfile.actionLongTermSubtitle}</span>
              <b>{dict.mwsProfile.actionLongTermScheduled}</b>
            </div>
            <div>
              <span className="priority low">{dict.mwsProfile.actionMonitoringBadge}</span>
              <strong>{dict.mwsProfile.actionMonitoringFocus} {interventions?.monitoring_focus || dict.mwsProfile.groundwaterFocus}</strong>
              <span>{dict.mwsProfile.actionMonitoringSensors} {interventions?.iot_sensors || dict.mwsProfile.sensorsPrescription}</span>
              <b>{dict.mwsProfile.actionMonitoringContinuous}</b>
            </div>
          </div>
        </div>
      </Panel>

      {/* Row 2: Model 1 LULC Composition + Morphometry & Hydrology */}
      <div className="dashboard-grid">
        <Panel
          title={dict.mwsProfile.lulcCompositionTitle}
          eyebrow={dict.mwsProfile.lulcCompositionEyebrow}
        >
          {lulc && lulc.coverage_category === 'LOW' && (
            <div
              style={{
                padding: '6px 10px',
                borderRadius: 4,
                background: '#fff8ec',
                border: '1px solid #edc58e',
                color: '#774a0e',
                fontSize: 11,
                marginBottom: 10,
              }}
            >
              {dict.mwsProfile.lulcLowRasterWarning}
            </div>
          )}
          <div className="indicator-list">
            <div>
              <span>{dict.mwsProfile.lulcAgri}</span>
              <strong>{isOffline || !lulc || typeof lulc.agriculture_pct !== 'number' ? '—' : `${lulc.agriculture_pct.toFixed(1)}%`}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcForest}</span>
              <strong>{isOffline || !lulc || typeof lulc.forest_pct !== 'number' ? '—' : `${lulc.forest_pct.toFixed(1)}%`}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcWater}</span>
              <strong>{isOffline || !lulc || typeof lulc.water_pct !== 'number' ? '—' : `${lulc.water_pct.toFixed(1)}%`}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcBuiltup}</span>
              <strong>{isOffline || !lulc || typeof lulc.builtup_pct !== 'number' ? '—' : `${lulc.builtup_pct.toFixed(1)}%`}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcBarren}</span>
              <strong>{isOffline || !lulc || typeof lulc.barren_pct !== 'number' ? '—' : `${lulc.barren_pct.toFixed(1)}%`}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcValidPixels}</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {isOffline || !lulc || typeof lulc.valid_pixel_count !== 'number' ? '—' : `${lulc.valid_pixel_count.toLocaleString()} px`}
              </strong>
            </div>
            <div>
              <span>{dict.mwsProfile.lulcDominantClass}</span>
              <strong>
                {isOffline || !lulc ? '—' : `${lulc.dominant_class} (${lulc.coverage_category})`}
              </strong>
            </div>
          </div>
        </Panel>

        <Panel
          title={dict.mwsProfile.morphometryTitle}
          eyebrow={dict.mwsProfile.morphometryEyebrow}
        >
          <div className="indicator-list">
            <div>
              <span>{dict.mwsProfile.meanElevation}</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {isOffline || selectedProfile?.elevation_mean === null || selectedProfile?.elevation_mean === undefined
                  ? '—'
                  : `${selectedProfile.elevation_mean} m`}
              </strong>
            </div>
            <div>
              <span>{dict.mwsProfile.meanSlope}</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {isOffline || selectedProfile?.slope_mean === null || selectedProfile?.slope_mean === undefined
                  ? '—'
                  : `${selectedProfile.slope_mean}°`}
              </strong>
            </div>
            <div>
              <span>{dict.mwsProfile.streamLength}</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {isOffline || selectedProfile?.stream_length_km === null || selectedProfile?.stream_length_km === undefined
                  ? '—'
                  : `${selectedProfile.stream_length_km} km`}
              </strong>
            </div>
            <div>
              <span>{dict.mwsProfile.drainageDensity}</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {isOffline || selectedProfile?.drainage_density === null || selectedProfile?.drainage_density === undefined
                  ? '—'
                  : `${selectedProfile.drainage_density} km/km²`}
              </strong>
            </div>
            <div>
              <span>{dict.mwsProfile.soilIndicators}</span>
              <strong style={{ opacity: 0.75 }}>{dict.mwsProfile.soilDataUnavailable}</strong>
            </div>
            <div>
              <span>{dict.mwsProfile.streamNetwork}</span>
              <strong className="green">{dict.mwsProfile.streamCanonicalMapped}</strong>
            </div>
          </div>
        </Panel>
      </div>

      {/* Row 3: 12-Month Historical Trend */}
      <Panel
        title={dict.mwsProfile.trendTitle}
        eyebrow={dict.mwsProfile.trendEyebrow}
      >
        <div className="health-chart">
          <div className="chart-y">
            <span>100</span>
            <span>75</span>
            <span>50</span>
            <span>25</span>
            <span>0</span>
          </div>
          <div className="bars">
            {isOffline ? (
              <div className="empty-state">
                {dict.mwsProfile.trendOffline}
                <span>{dict.mwsProfile.trendOfflineDesc}</span>
              </div>
            ) : selectedProfile?.monthly_trend && selectedProfile.monthly_trend.length > 0 ? (
              formatChronological12Months(selectedProfile.monthly_trend).map((pt, idx) => (
                <div className="bar-wrap" key={`${pt.displayYear}-${pt.displayMonth}-${idx}`}>
                  <div
                    className="bar"
                    style={{
                      height: `${Math.max(4, Math.min(100, pt.health_index))}%`,
                      background:
                        pt.health_index < 45
                          ? 'var(--red)'
                          : pt.health_index < 60
                          ? 'var(--amber)'
                          : '#68ad68',
                    }}
                    title={`${pt.displayMonth} ${pt.displayYear}: Health ${pt.health_index}/100, Risk ${pt.risk_score}/100`}
                  />
                  <span>{pt.displayMonth}</span>
                </div>
              ))
            ) : (
              <div className="empty-state">
                {dict.mwsProfile.trendNoPoints}
              </div>
            )}
          </div>
        </div>
        <div className="legend">
          <span>
            <i className="green-dot" style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block' }} />
            {dict.mwsProfile.trendLegend}
          </span>
          <span className="muted">{dict.mwsProfile.trendSubtitle}</span>
        </div>
      </Panel>

      {/* SECTION 5: AGRO-HYDROLOGICAL CROP SUGGESTIONS */}
      <Panel
        title={`Water-Conditioned Crop Intelligence · ${selectedProfile?.MWS ?? 'Catchment'}`}
        eyebrow="AGRO-HYDROLOGICAL DECISION SUPPORT"
        action="Full Crop Screen"
        onAction={() => setScreen('Crop Intelligence')}
      >
        <CropSuggestions
          advisory={cropAdvisory ?? null}
          status={cropStatus ?? 'available'}
          mwsCode={selectedProfile?.MWS}
          mwsId={selectedProfile?.id}
        />
      </Panel>

      {/* SECTION 6: BASIN BENCHMARK (This MWS vs Shiggaon Basin) */}
      <Panel
        title={dict.mwsProfile.benchmarkTitle}
        eyebrow={dict.mwsProfile.benchmarkEyebrow}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            {t('mwsProfile.benchmarkIntro', { mws: selectedProfile?.MWS || 'this catchment' })}
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left', color: 'var(--muted)', fontSize: 10, letterSpacing: '0.06em' }}>
                  <th style={{ padding: '8px 10px' }}>{dict.mwsProfile.colMetric}</th>
                  <th style={{ padding: '8px 10px' }}>{t('mwsProfile.colMws', { mws: selectedProfile?.MWS || 'Catchment' })}</th>
                  <th style={{ padding: '8px 10px' }}>{dict.mwsProfile.colBasinAvg}</th>
                  <th style={{ padding: '8px 10px' }}>{dict.mwsProfile.colComparison}</th>
                </tr>
              </thead>
              <tbody>
                {/* Row 1: Overall Risk Score */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmRiskRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: risk && risk.final_risk_score >= 55 ? 'var(--red)' : 'var(--primary)' }}>
                    {isOffline || !risk ? '—' : `${risk.final_risk_score} / 100`}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.average_risk_score != null ? `${basin.average_risk_score} / 100` : '50.0 / 100'}
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    {risk && basin?.average_risk_score != null ? (
                      risk.final_risk_score > basin.average_risk_score ? (
                        <span style={{ color: 'var(--red)', fontWeight: 600 }}>
                          {t('mwsProfile.ptsAboveAvg', { diff: (risk.final_risk_score - basin.average_risk_score).toFixed(1) })}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--primary)', fontWeight: 600 }}>
                          {t('mwsProfile.ptsBelowAvg', { diff: (basin.average_risk_score - risk.final_risk_score).toFixed(1) })}
                        </span>
                      )
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 2: Mean Slope */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmSlopeRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.slope_mean != null ? `${selectedProfile.slope_mean}°` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_slope_mean != null ? `${basin.avg_slope_mean}°` : '8.1°'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.slope_mean != null && basin?.avg_slope_mean != null ? (
                      selectedProfile.slope_mean > basin.avg_slope_mean
                        ? t('mwsProfile.steeperThanAvg', { diff: (selectedProfile.slope_mean - basin.avg_slope_mean).toFixed(1) })
                        : t('mwsProfile.gentlerThanAvg', { diff: (basin.avg_slope_mean - selectedProfile.slope_mean).toFixed(1) })
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 3: Mean Elevation */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmElevationRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.elevation_mean != null ? `${selectedProfile.elevation_mean} m` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_elevation_mean != null ? `${basin.avg_elevation_mean} m` : '631.1 m'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.elevation_mean != null && basin?.avg_elevation_mean != null ? (
                      selectedProfile.elevation_mean > basin.avg_elevation_mean
                        ? t('mwsProfile.aboveAvgHeadwater', { diff: (selectedProfile.elevation_mean - basin.avg_elevation_mean).toFixed(1) })
                        : t('mwsProfile.belowAvg', { diff: (basin.avg_elevation_mean - selectedProfile.elevation_mean).toFixed(1) })
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 4: Drainage Density */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmDrainageRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.drainage_density != null ? `${selectedProfile.drainage_density} km/km²` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_drainage_density != null ? `${basin.avg_drainage_density} km/km²` : '0.207 km/km²'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.drainage_density != null && basin?.avg_drainage_density != null ? (
                      selectedProfile.drainage_density >= basin.avg_drainage_density ? dict.mwsProfile.higherThanAvg : dict.mwsProfile.moderateDensityAvg
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 5: Stream Length */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmStreamRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.stream_length_km != null ? `${selectedProfile.stream_length_km} km` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_stream_length_km != null ? `${basin.avg_stream_length_km} km` : '3.03 km'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.stream_length_km != null && basin?.avg_stream_length_km != null ? (
                      t('mwsProfile.timesAvgNetwork', { ratio: (selectedProfile.stream_length_km / (basin.avg_stream_length_km || 1)).toFixed(1) })
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 6: Vegetation Index */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmNdviRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.ndvi != null ? `${selectedProfile.ndvi} (Current)` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_ndvi != null ? `${basin.avg_ndvi}` : '0.443'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.ndvi != null && basin?.avg_ndvi != null ? (
                      selectedProfile.ndvi < basin.avg_ndvi ? dict.mwsProfile.suppressedVegAvg : dict.mwsProfile.equalOrAboveVegAvg
                    ) : '—'}
                  </td>
                </tr>

                {/* Row 7: Monthly Rainfall */}
                <tr>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{dict.mwsProfile.bmRainRow}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {selectedProfile?.rainfall_mm != null ? `${selectedProfile.rainfall_mm} mm/month` : dict.common.noData}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                    {basin?.avg_rainfall_mm != null ? `${basin.avg_rainfall_mm} mm/month` : '0.8 mm/month'}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--muted)' }}>
                    {selectedProfile?.rainfall_anomaly != null ? (
                      `${dict.mwsProfile.rainfallAnomalyLabel} ${selectedProfile.rainfall_anomaly > 0 ? '+' : ''}${selectedProfile.rainfall_anomaly}σ vs historical baseline (2017–2025)`
                    ) : '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </Panel>

      {/* SECTION 6: DATA PROVENANCE BANNER */}
      <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
        <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.12em', color: 'var(--muted)' }}>
          {dict.mwsProfile.dataProvenanceTitle}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, fontSize: 10, color: 'var(--muted)' }}>
          <span>🛰 <strong>{dict.mwsProfile.provSatellite}</strong></span>
          <span>🌧 <strong>{dict.mwsProfile.provRainfall}</strong></span>
          <span>⛰ <strong>{dict.mwsProfile.provDem}</strong></span>
          <span>🗺 <strong>{dict.mwsProfile.provBoundaries}</strong></span>
          <span>🤖 <strong>{dict.mwsProfile.provMlModel}</strong></span>
          <span>⚖ <strong>{dict.mwsProfile.provRiskModel}</strong></span>
        </div>
      </div>
    </>
  )
}

function LulcAnalysisScreen({
  mode,
  setScreen,
  apiStatus,
  lulcSummary,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  lulcSummary: LulcBasinSummary | null
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
}) {
  const { dict } = useLanguage()
  const isOffline = apiStatus === 'unavailable'
  const lulc = selectedProfile?.lulc
  const meta = lulcSummary?.model_metadata
  const conf = lulcSummary?.confidence_stats

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">LULC ANALYSIS / SHIGGAON BASIN</span>
          <h1>{dict.subscreens.lulcTitle}</h1>
          <p>{dict.subscreens.lulcSubtitle}</p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          {selectedProfile && (
            <button className="outline-button" onClick={() => setScreen('Micro-Watershed Profile')}>
              Inspect Profile ({selectedProfile.MWS}) ↗
            </button>
          )}
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            {dict.mwsProfile.backToDashboard}
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {/* Top 4 Metrics Grid */}
      <div className="metric-grid">
        <Metric
          label={dict.subscreens.lulcMacroF1}
          value={isOffline || !meta ? '—' : `${meta.macro_f1}`}
          unit={isOffline || !meta ? undefined : 'score'}
          trend={isOffline || !meta || typeof meta.accuracy !== 'number' ? undefined : `${dict.subscreens.lulcAccuracy}: ${(meta.accuracy * 100).toFixed(1)}%`}
          tone="green"
        />
        <Metric
          label={dict.subscreens.lulcWeightedF1}
          value={isOffline || !conf ? '—' : `${conf.mean_confidence}%`}
          unit={isOffline || !conf ? undefined : 'model'}
          trend={isOffline || !conf ? undefined : `High Conf: ${conf.high_confidence_pct}%`}
          tone="green"
        />
        <Metric
          label={dict.mwsProfile.dominantLulcMetricLabel}
          value={
            isOffline
              ? '—'
              : selectedProfile?.lulc?.dominant_class || 'Agriculture'
          }
          unit={isOffline ? undefined : selectedProfile ? 'local' : 'basin'}
          trend={
            isOffline
              ? undefined
              : selectedProfile
              ? `${dict.mwsProfile.coverageLabel}: ${selectedProfile.lulc?.coverage_category || 'LOW'}`
              : '53 / 66 Micro-Watersheds'
          }
          tone="green"
        />
        <Metric
          label={dict.dashboard.monitoredAreaLabel}
          value={isOffline ? '—' : `${lulcSummary?.total_watersheds ?? (watersheds.length > 0 ? watersheds.length : 66)}`}
          unit={isOffline ? undefined : dict.dashboard.unitsWord}
          trend={dict.dashboard.talukBasinExtent}
          tone="green"
        />
      </div>

      {/* Hero Section: Map + Catchment Zonal Focus */}
      <div className="detail-hero">
        <BasinMap
          variant="LULC Analysis"
          selectedMws={selectedProfile?.MWS}
          selectedId={selectedProfile?.id}
          gisBoundaries={gisBoundaries}
          gisStatus={gisStatus}
          gisError={gisError}
          onSelectMws={onSelectMws}
        />
        <div className="detail-summary">
          <span className="eyebrow">
            {isOffline
              ? dict.mwsProfile.identityCardOfflineEyebrow
              : selectedProfile
              ? `SELECTED CATCHMENT · ${selectedProfile.id}`
              : 'SHIGGAON BASIN LULC'}
          </span>
          <h2>
            {isOffline
              ? dict.mwsProfile.identityOfflineTitle
              : selectedProfile
              ? `Catchment ${selectedProfile.MWS} LULC Breakdown`
              : 'Sentinel-2 10m Classification Overview'}
          </h2>
          <p>
            {isOffline
              ? dict.mwsProfile.identityOfflineDesc
              : selectedProfile
              ? `SLUSI Code: ${selectedProfile.MWS} | Master GIS Key: ${selectedProfile.id} | Valid Pixels: ${selectedProfile.lulc?.valid_pixel_count?.toLocaleString() ?? '—'} px | Dominant Class: ${selectedProfile.lulc?.dominant_class || 'Agriculture'}`
              : 'Zonal multi-spectral analysis calibrated from Sentinel-2 bands (B2, B3, B4, B8, B11) and vegetation indices. Click any polygon on the map to inspect catchment-level land use.'}
          </p>
          <div className="summary-stats">
            <Metric
              label={dict.mwsProfile.signalLandUseDominant}
              value={isOffline || !lulc ? (isOffline ? '—' : 'Agri') : lulc.dominant_class}
            />
            <Metric
              label={dict.mwsProfile.coverageLabel.toUpperCase()}
              value={isOffline || !lulc ? (isOffline ? '—' : '66 MWS') : lulc.coverage_category}
            />
            <Metric
              label={dict.mwsProfile.lulcValidPixels}
              value={isOffline || !lulc ? (isOffline ? '—' : '1.2M') : (typeof lulc.valid_pixel_count === 'number' ? lulc.valid_pixel_count.toLocaleString() : '—')}
              unit={lulc ? 'px' : undefined}
            />
          </div>
          {selectedProfile && (
            <button
              className="outline-button full"
              style={{ marginTop: 16, background: '#fff', color: 'var(--primary)' }}
              onClick={() => setScreen('Micro-Watershed Profile')}
            >
              Inspect Full Profile ({selectedProfile.MWS}) →
            </button>
          )}
        </div>
      </div>

      {/* Row 2: Selected Catchment Composition + Basin-Wide Model 1 Confidence */}
      <div className="dashboard-grid">
        <Panel
          title={selectedProfile ? `${dict.mwsProfile.lulcCompositionTitle}: ${selectedProfile.MWS}` : dict.mwsProfile.selectCatchmentDesc}
          eyebrow="MODEL 1 ZONAL METRICS"
        >
          {isOffline ? (
            <div className="empty-state">
              {dict.common.dataUnavailable}
            </div>
          ) : lulc ? (
            <>
              {lulc.coverage_category === 'LOW' && (
                <div
                  style={{
                    padding: '6px 10px',
                    borderRadius: 4,
                    background: '#fff8ec',
                    border: '1px solid #edc58e',
                    color: '#774a0e',
                    fontSize: 11,
                    marginBottom: 10,
                  }}
                >
                  {dict.mwsProfile.lulcLowRasterWarning}
                </div>
              )}
              <div className="indicator-list">
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#ed6c02', display: 'inline-block' }} />
                  {dict.mwsProfile.lulcAgri}
                </span>
                <strong>{typeof lulc.agriculture_pct === 'number' ? `${lulc.agriculture_pct.toFixed(1)}%` : '—'}</strong>
              </div>
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#2e7d32', display: 'inline-block' }} />
                  {dict.mwsProfile.lulcForest}
                </span>
                <strong>{typeof lulc.forest_pct === 'number' ? `${lulc.forest_pct.toFixed(1)}%` : '—'}</strong>
              </div>
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#0288d1', display: 'inline-block' }} />
                  {dict.mwsProfile.lulcWater}
                </span>
                <strong>{typeof lulc.water_pct === 'number' ? `${lulc.water_pct.toFixed(1)}%` : '—'}</strong>
              </div>
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#ba1a1a', display: 'inline-block' }} />
                  {dict.mwsProfile.lulcBuiltup}
                </span>
                <strong>{typeof lulc.builtup_pct === 'number' ? `${lulc.builtup_pct.toFixed(1)}%` : '—'}</strong>
              </div>
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#757575', display: 'inline-block' }} />
                  {dict.mwsProfile.lulcBarren}
                </span>
                <strong>{typeof lulc.barren_pct === 'number' ? `${lulc.barren_pct.toFixed(1)}%` : '—'}</strong>
              </div>
              <div>
                <span>{dict.mwsProfile.lulcValidPixels}</span>
                <strong style={{ fontFamily: 'var(--font-mono)' }}>{typeof lulc.valid_pixel_count === 'number' ? `${lulc.valid_pixel_count.toLocaleString()} px` : '—'}</strong>
              </div>
              <div>
                <span>{dict.mwsProfile.lulcDominantClass}</span>
                <strong>{lulc.coverage_category} ({lulc.coverage_pct ? `${lulc.coverage_pct}% raster overlap` : 'Zonal'})</strong>
              </div>
            </div>
            </>
          ) : (
            <div className="empty-state">
              {dict.mwsProfile.selectCatchmentDesc}
            </div>
          )}
        </Panel>

        <Panel
          title={dict.subscreens.lulcDistribution}
          eyebrow="MODEL 1 EVALUATION"
        >
          <div className="provenance">
            <div>
              <span>{dict.subscreens.lulcFullScene}</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 6 }}>
                {isOffline || !lulcSummary?.full_scene_distribution ? (
                  <span style={{ fontSize: 11, opacity: 0.7 }}>{dict.common.noData}</span>
                ) : (
                  Object.entries(lulcSummary.full_scene_distribution).map(([cls, pct]) => {
                    const colorMap: Record<string, string> = {
                      Agriculture: '#ed6c02',
                      Forest: '#2e7d32',
                      Water: '#0288d1',
                      'Built-up': '#ba1a1a',
                      Barren: '#757575',
                    }
                    return (
                      <div key={cls} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <i style={{ width: 8, height: 8, borderRadius: 2, background: colorMap[cls] || '#687263', display: 'inline-block' }} />
                          {cls}
                        </span>
                        <strong style={{ fontFamily: 'var(--font-mono)' }}>{typeof pct === 'number' ? `${pct.toFixed(1)}%` : '—'}</strong>
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            <div>
              <span>MODEL CONFIDENCE STRATIFICATION</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span>High Confidence (≥ 0.75)</span>
                  <strong className="green">{isOffline || !conf ? '—' : `${conf.high_confidence_pct}%`}</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span>Medium Confidence (0.50 – 0.75)</span>
                  <strong className="amber">{isOffline || !conf ? '—' : `${conf.medium_confidence_pct}%`}</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span>Low Confidence (&lt; 0.50)</span>
                  <strong className="red">{isOffline || !conf ? '—' : `${conf.low_confidence_pct}%`}</strong>
                </div>
              </div>
            </div>

            <div>
              <span>RASTER TILING PIPELINE</span>
              <strong style={{ fontSize: 10, fontWeight: 500, color: 'var(--muted)', lineHeight: 1.4, display: 'block', marginTop: 2 }}>
                Authoritative Sentinel-2 10m LULC raster (lulc_prediction.tif) processed into zonal catchment statistics across all 66 micro-watersheds. Direct raster GeoTIFF web tiling unavailable in current release.
              </strong>
            </div>
          </div>
        </Panel>
      </div>

      {/* Row 3: 66-MWS Comparative Zonal Table + Architecture & Coverage Breakdown */}
      <div className="bottom-grid">
        <Panel
          title={dict.mwsProfile.lulcCompositionTitle}
          eyebrow={dict.dashboard.slusiOfficialUnits}
        >
          <div className="status-table">
            <div className="table-row table-label">
              <span>{dict.dashboard.colUnitMws}</span>
              <span>{dict.mwsProfile.dominantLulcMetricLabel}</span>
              <span>{dict.dashboard.colGisId}</span>
              <span>{dict.dashboard.colStatus}</span>
            </div>
            {isOffline ? (
              <div className="table-row">
                <span style={{ gridColumn: '1 / -1', textAlign: 'center', opacity: 0.7 }}>
                  {dict.dashboard.tableDataUnavailable}
                </span>
              </div>
            ) : watersheds.length > 0 ? (
              watersheds.map((row) => {
                const isSelected = row.id === selectedProfile?.id
                return (
                  <div
                    className="table-row"
                    key={row.id}
                    style={{
                      cursor: 'pointer',
                      background: isSelected ? 'var(--surface-low)' : 'transparent',
                    }}
                    onClick={() => onSelectMws(row.id)}
                    title={`Click to inspect LULC for ${row.MWS} (${row.id})`}
                  >
                    <strong>{row.MWS}</strong>
                    <span>{row.dominant_class || 'Agriculture'}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em' }}>
                      {row.id}
                    </span>
                    <span className="status stable">
                      {row.dominant_class === 'Forest' ? 'Forest' : 'Assessed'}
                    </span>
                  </div>
                )
              })
            ) : (
              <div className="table-row">
                <span>{dict.dashboard.tableConnecting}</span>
                <span>—</span>
                <span>—</span>
                <span>—</span>
              </div>
            )}
          </div>
        </Panel>

        <Panel
          title={dict.subscreens.lulcModelMetadata}
          eyebrow="RANDOM FOREST PIPELINE"
        >
          <div className="provenance">
            <div>
              <span>66-MWS COVERAGE CATEGORY DISTRIBUTION</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px 12px', marginTop: 5 }}>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#1b5e20', display: 'inline-block' }} />
                  GOOD: <strong>{lulcSummary?.coverage_distribution?.GOOD ?? 27} units</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#c8961e', display: 'inline-block' }} />
                  LOW: <strong>{lulcSummary?.coverage_distribution?.LOW ?? 35} units</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#ed6c02', display: 'inline-block' }} />
                  ACCEPTABLE: <strong>{lulcSummary?.coverage_distribution?.ACCEPTABLE ?? 3} units</strong>
                </span>
                <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i style={{ width: 7, height: 7, borderRadius: '50%', background: '#ba1a1a', display: 'inline-block' }} />
                  INSUFFICIENT: <strong>{lulcSummary?.coverage_distribution?.INSUFFICIENT_DATA ?? 1} unit</strong>
                </span>
              </div>
            </div>

            <div>
              <span>{dict.subscreens.lulcBands} & {dict.subscreens.lulcIndices}</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                {['B02 (Blue)', 'B03 (Green)', 'B04 (Red)', 'B08 (NIR)', 'B11 (SWIR)', 'NDVI', 'NDWI', 'NDBI', 'BSI'].map((b) => (
                  <span key={b} style={{ fontSize: 9, padding: '2px 6px', background: 'var(--surface-low)', border: '1px solid var(--border)', borderRadius: 3, fontFamily: 'var(--font-mono)' }}>
                    {b}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <span>{dict.subscreens.lulcClassifier}</span>
              <strong>{meta?.classifier || 'RandomForestClassifier (200 trees)'}</strong>
            </div>

            <div>
              <span>{dict.subscreens.lulcResolution} & {dict.subscreens.lulcCrs}</span>
              <strong>{meta?.resolution_m || 10.0}m Ground Sampling · {meta?.crs || 'EPSG:32643'}</strong>
            </div>

            <div>
              <span>TRAINING SAMPLE SPLIT</span>
              <strong style={{ fontSize: 10, fontWeight: 500 }}>Equal count, 3,000 samples/class (Spatial block split, 25% test)</strong>
            </div>
          </div>
        </Panel>
      </div>
    </>
  )
}

function WaterQualityScreen({
  mode,
  setScreen,
  apiStatus,
  wqSummary,
  wqRecord,
  wqStatus,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  wqSummary: WaterQualitySummary | null
  wqRecord: WaterQualityRecord | null
  wqStatus: DataStatus
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
}) {
  const { dict } = useLanguage()
  const isOffline = apiStatus === 'unavailable' || wqStatus === 'unavailable'
  const isLoading = wqStatus === 'loading'
  const [searchTerm, setSearchTerm] = useState('')

  const activeMws = wqRecord?.MWS || selectedProfile?.MWS || 'Select MWS'
  const activeId = wqRecord?.id || selectedProfile?.id || ''
  const wqi = wqRecord?.wqi ?? null
  const category = wqRecord?.quality_category ?? null
  const isLive = mode === 'live' && wqRecord?.source === 'live'

  const getCategoryTone = (cat: string | null) => {
    if (!cat) return 'green'
    if (cat === 'Excellent' || cat === 'Good') return 'green'
    if (cat === 'Poor') return 'amber'
    return 'red'
  }

  const filteredWatersheds = (wqSummary?.watersheds || []).filter((w) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      w.MWS.toLowerCase().includes(term) ||
      w.id.toLowerCase().includes(term) ||
      w.quality_category.toLowerCase().includes(term)
    )
  })

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WATER QUALITY / SHIGGAON BASIN</span>
          <h1>{dict.subscreens.wqTitle}</h1>
          <p>
            {isLive
              ? 'Real-time ESP32 gateway telemetry stream, in-situ acidity & siltation monitoring, and live WQI evaluation.'
              : dict.subscreens.wqSubtitle}
          </p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          {isLive ? (
            <span
              className="source-badge live"
              style={{
                background: '#d4edda',
                color: '#155724',
                borderColor: '#c3e6cb',
                fontWeight: 700,
              }}
            >
              <span className="source-dot" style={{ background: '#28a745' }} />
              WQ: LIVE (ESP32 HARDWARE)
            </span>
          ) : (
            <span
              className="source-badge simulation"
              style={{
                background: '#fff3cd',
                color: '#856404',
                borderColor: '#ffeeba',
                fontWeight: 700,
              }}
            >
              <span className="source-dot" style={{ background: '#856404' }} />
              WQ: SIMULATION
            </span>
          )}
          {selectedProfile && (
            <button className="outline-button" onClick={() => setScreen('Micro-Watershed Profile')}>
              Inspect Profile ({selectedProfile.MWS}) ↗
            </button>
          )}
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            {dict.mwsProfile.backToDashboard}
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {isLoading && (
        <div className="notice">
          <strong>{dict.common.loading}</strong>
        </div>
      )}

      {!isOffline && (
        isLive ? (
          <div
            className="notice"
            style={{
              borderLeft: '4px solid var(--green)',
              background: 'rgba(46, 125, 50, 0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: '20px' }}>🟢</span>
            <div>
              <strong>Live ESP32 Telemetry Active:</strong> Water Quality Index (WQI) and parameters (Runoff Stream Acidity, Siltation Turbidity, Temperature) are streaming in real-time from the connected ESP32 sensor node on <code>/dev/cu.usbserial-0001</code>.
            </div>
          </div>
        ) : (
          <div
            className="notice"
            style={{
              borderLeft: '4px solid var(--amber)',
              background: 'rgba(237, 108, 2, 0.05)',
            }}
          >
            {dict.subscreens.wqSimulationNotice}
          </div>
        )
      )}

      {/* Top 4 Metrics Grid */}
      <div className="metric-grid">
        <Metric
          label={dict.subscreens.wqIndexLabel}
          value={isOffline || wqi === null ? '—' : `${wqi}`}
          unit={isOffline || wqi === null ? undefined : 'WQI'}
          trend={isOffline || !category ? undefined : `${category}`}
          tone={getCategoryTone(category)}
        />
        <Metric
          label="WQ DATA"
          value={isOffline ? dict.common.offline.toUpperCase() : (isLive ? 'LIVE (ESP32)' : 'SIMULATED')}
          trend={isLive ? 'Real Hardware Stream' : 'Deterministic Seed'}
          tone={isLive ? 'green' : 'amber'}
        />
        <Metric
          label={dict.dashboard.selectedMwsCodeLabel}
          value={isOffline ? '—' : activeMws}
          unit={isOffline ? undefined : 'MWS'}
          trend={isOffline ? undefined : `GIS ID: ${activeId || 'g_mws.240575'}`}
          tone="green"
        />
        <Metric
          label={dict.subscreens.meanBasinWqi}
          value={isOffline || !wqSummary ? '—' : `${wqSummary.mean_wqi}`}
          unit={isOffline || !wqSummary ? undefined : 'WQI'}
          trend={isLive ? 'Incorporating Live Nodes' : dict.subscreens.monitoredCatchments}
          tone="green"
        />
      </div>

      {/* Hero Section: Map + Catchment Assessment */}
      <div className="detail-hero">
        <BasinMap
          variant="Water Quality"
          selectedMws={activeMws}
          selectedId={activeId}
          gisBoundaries={gisBoundaries}
          gisStatus={gisStatus}
          gisError={gisError}
          onSelectMws={onSelectMws}
        />
        <div className="detail-summary">
          <div>
            <span className="eyebrow">
              {isOffline
                ? dict.mwsProfile.identityCardOfflineEyebrow
                : (isLive ? 'LIVE ESP32 STREAM · WEIGHTED ARITHMETIC WQI' : 'SIMULATION · WEIGHTED ARITHMETIC WQI')}
            </span>
            <h2>
              {isOffline
                ? dict.subscreens.wqSubtitle
                : (isLive ? `Catchment ${activeMws} (Live IoT Monitoring)` : `Catchment ${activeMws} Assessment`)}
            </h2>
            <p>
              {isOffline
                ? dict.mwsProfile.identityOfflineDesc
                : (isLive
                    ? `Live Water Quality Index (WQI) derived in real time from physical sensors on ESP32 node. Runoff acidity (pH), siltation turbidity (NTU), and ambient/stream temperature are evaluated against reference standards.`
                    : `Water Quality Index (WQI) computed using the weighted arithmetic method over 4 core parameters: pH, TDS, Turbidity, and Temperature. Values are evaluated against project reference limits derived from drinking-water standards and water-quality literature.`)}
            </p>
          </div>
          <div>
            <div className="summary-stats">
              <Metric
                label={dict.subscreens.wqIndexLabel}
                value={isOffline || wqi === null ? '—' : `${wqi}`}
                unit={wqi !== null ? 'WQI' : undefined}
              />
              <Metric
                label={dict.mwsProfile.riskCategoryStat}
                value={isOffline || !category ? '—' : category}
              />
              <Metric
                label="SOURCE"
                value={isOffline ? dict.common.offline : (isLive ? 'ESP32 Hardware' : 'Simulation')}
              />
            </div>
            {selectedProfile && (
              <button
                className="outline-button full"
                style={{ marginTop: 16, background: '#fff', color: 'var(--primary)' }}
                onClick={() => setScreen('Micro-Watershed Profile')}
              >
                Inspect Full Catchment Profile ({selectedProfile.MWS}) →
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: Core Parameter Cards + WQI Methodology */}
      <div className="dashboard-grid">
        <Panel
          title={wqRecord ? (isLive ? `Live Catchment Parameters (${wqRecord.MWS} - ESP32)` : `Simulated Catchment Parameters (${wqRecord.MWS})`) : 'Select a Micro-Watershed'}
          eyebrow={isLive ? '4 CORE REAL-TIME SENSOR PARAMETERS' : '4 CORE SIMULATED PARAMETERS'}
        >
          {isOffline ? (
            <div className="empty-state">
              Parameters unavailable while backend is disconnected.
            </div>
          ) : wqRecord ? (
            <div className="indicator-list">
              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#01629e', display: 'inline-block' }} />
                  pH Level
                </span>
                <strong>
                  {typeof wqRecord.ph === 'number' ? wqRecord.ph.toFixed(2) : '—'}{' '}
                  <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>
                    (Std: 8.5 · Ideal: 7.0 · Weight: 33.3%)
                  </span>
                </strong>
              </div>
              <div style={{ padding: '0 0 6px 0' }}>
                <div style={{ background: 'var(--surface-low)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      background: typeof wqRecord.ph === 'number' && wqRecord.ph >= 6.5 && wqRecord.ph <= 8.5 ? '#2e7d32' : '#ba1a1a',
                      height: '100%',
                      width: `${typeof wqRecord.ph === 'number' ? Math.min(100, Math.max(0, (wqRecord.ph / 14) * 100)) : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#ed6c02', display: 'inline-block' }} />
                  Total Dissolved Solids (TDS)
                </span>
                <strong>
                  {typeof wqRecord.tds === 'number' ? `${wqRecord.tds.toFixed(1)} mg/L` : '—'}{' '}
                  <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>
                    (Desirable: &lt; 500 mg/L · Weight: 0.6%)
                  </span>
                </strong>
              </div>
              <div style={{ padding: '0 0 6px 0' }}>
                <div style={{ background: 'var(--surface-low)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      background: typeof wqRecord.tds === 'number' ? (wqRecord.tds <= 500 ? '#2e7d32' : wqRecord.tds <= 1000 ? '#ed6c02' : '#ba1a1a') : '#757575',
                      height: '100%',
                      width: `${typeof wqRecord.tds === 'number' ? Math.min(100, Math.max(0, (wqRecord.tds / 1000) * 100)) : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#883454', display: 'inline-block' }} />
                  Turbidity
                </span>
                <strong>
                  {typeof wqRecord.turbidity === 'number' ? `${wqRecord.turbidity.toFixed(2)} NTU` : '—'}{' '}
                  <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>
                    (Permissible: &lt; 5 NTU · Weight: 56.7%)
                  </span>
                </strong>
              </div>
              <div style={{ padding: '0 0 6px 0' }}>
                <div style={{ background: 'var(--surface-low)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      background: typeof wqRecord.turbidity === 'number' ? (wqRecord.turbidity <= 5.0 ? '#2e7d32' : '#ba1a1a') : '#757575',
                      height: '100%',
                      width: `${typeof wqRecord.turbidity === 'number' ? Math.min(100, Math.max(0, (wqRecord.turbidity / 15) * 100)) : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: '#00450d', display: 'inline-block' }} />
                  Water Temperature
                </span>
                <strong>
                  {typeof wqRecord.temperature === 'number' ? `${wqRecord.temperature.toFixed(1)} °C` : '—'}{' '}
                  <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>
                    (Baseline: 25.0 °C · Std: 30.0 °C · Weight: 9.4%)
                  </span>
                </strong>
              </div>
              <div style={{ padding: '0 0 6px 0' }}>
                <div style={{ background: 'var(--surface-low)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      background: typeof wqRecord.temperature === 'number' ? (wqRecord.temperature <= 30.0 ? '#2e7d32' : '#ed6c02') : '#757575',
                      height: '100%',
                      width: `${typeof wqRecord.temperature === 'number' ? Math.min(100, Math.max(0, (wqRecord.temperature / 40) * 100)) : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 4 }}>
                <span>Sampling Timestamp</span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em' }}>
                  {wqRecord.timestamp}
                </strong>
              </div>
              <div>
                <span>Source Provenance</span>
                <span className="source-badge simulation small">
                  <span className="source-dot" />
                  {wqRecord.source}
                </span>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              Select any micro-watershed to view its water quality metrics.
            </div>
          )}
        </Panel>

        <Panel
          title={dict.subscreens.wqMatrixTitle}
          eyebrow="WEIGHTED ARITHMETIC FORMULA"
        >
          <div className="provenance">
            <div>
              <span>FORMULA SPECIFICATION</span>
              <div style={{ fontSize: 11, lineHeight: 1.5, marginTop: 4, fontFamily: 'var(--font-mono)', background: 'var(--surface-low)', padding: '6px 10px', borderRadius: 4 }}>
                <div>Qi = |Vi - Voi| / (Si - Voi) × 100</div>
                <div>K = 1 / Σ(1/Si) ≈ 2.833</div>
                <div>WQI = Σ(Wi × Qi) / ΣWi</div>
              </div>
            </div>

            <div>
              <span>{dict.subscreens.wqCategoryDist}</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: '#2e7d32', display: 'inline-block' }} />
                    Excellent (0 – 25)
                  </span>
                  <strong className="green">{wqSummary?.category_distribution.Excellent ?? '—'} units</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: '#1b5e20', display: 'inline-block' }} />
                    Good (25 – 50)
                  </span>
                  <strong className="green">{wqSummary?.category_distribution.Good ?? '—'} units</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: '#c8961e', display: 'inline-block' }} />
                    Poor (50 – 75)
                  </span>
                  <strong className="amber">{wqSummary?.category_distribution.Poor ?? '—'} units</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: '#ed6c02', display: 'inline-block' }} />
                    Very Poor (75 – 100)
                  </span>
                  <strong className="amber">{wqSummary?.category_distribution['Very Poor'] ?? '—'} units</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: '#ba1a1a', display: 'inline-block' }} />
                    Unsuitable for Drinking (&gt; 100)
                  </span>
                  <strong className="red">{wqSummary?.category_distribution['Unsuitable for Drinking'] ?? '—'} units</strong>
                </div>
              </div>
            </div>

            <div>
              <span>{dict.subscreens.wqParamStandards}</span>
              <strong style={{ fontSize: 10, fontWeight: 500, color: 'var(--muted)', lineHeight: 1.4, display: 'block', marginTop: 2 }}>
                Formula represents the Weighted Arithmetic WQI method commonly used in surface water studies. Reference limits for pH, TDS, and turbidity are drawn from Indian drinking water literature. Water temperature (25°C baseline / 30°C standard) is an assumed regional ambient deviation, not an official BIS regulatory standard.
              </strong>
            </div>
          </div>
        </Panel>
      </div>

      {/* Row 3: Honest Unavailable Notices for Historical Trends & Forecasting */}
      <div className="bottom-grid">
        <Panel
          title="Historical Parameter Trends"
          eyebrow="HISTORICAL TIMESERIES"
        >
          <div className="empty-state" style={{ padding: '24px 16px', textAlign: 'center' }}>
            <div style={{ fontWeight: 600, color: 'var(--foreground)', marginBottom: 4 }}>
              Timeseries Data Unavailable in Simulation Mode
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', maxWidth: 420, margin: '0 auto', lineHeight: 1.5 }}>
              A continuous field sensor logger or scheduled laboratory monitoring campaign is required to establish real historical trend lines. No synthetic timeseries has been fabricated.
            </p>
          </div>
        </Panel>

        <Panel
          title="Predictive Forecasting"
          eyebrow="ML FORECASTING PIPELINE"
        >
          <div className="empty-state" style={{ padding: '24px 16px', textAlign: 'center' }}>
            <div style={{ fontWeight: 600, color: 'var(--foreground)', marginBottom: 4 }}>
              Historical forecasting unavailable
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', maxWidth: 420, margin: '0 auto', lineHeight: 1.5 }}>
              Continuous field observations are required to establish a reliable time-series forecast. No synthetic forecasting series are presented in this release.
            </p>
          </div>
        </Panel>
      </div>

      {/* Row 4: 66-MWS Comparative Water Quality Table */}
      <div style={{ marginTop: 20 }}>
        <Panel
          title="Micro-Watershed Water Quality Comparison"
          eyebrow="66 OFFICIAL UNITS · SIMULATED READINGS"
        >
          <div style={{ marginBottom: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              type="text"
              placeholder={dict.common.searchPlaceholder}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                padding: '6px 12px',
                fontSize: 12,
                borderRadius: 4,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--foreground)',
                minWidth: 260,
              }}
            />
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
              Showing {filteredWatersheds.length} of {wqSummary?.total_monitored_mws ?? 66} units
            </span>
          </div>
          <div className="status-table" style={{ maxHeight: 380, overflowY: 'auto' }}>
            <div className="table-row table-label" style={{ gridTemplateColumns: '1fr 1.2fr 0.8fr 1fr 1fr 1fr 1fr 1.2fr 1fr' }}>
              <span>{dict.dashboard.colUnitMws}</span>
              <span>{dict.dashboard.colGisId}</span>
              <span>pH</span>
              <span>TDS</span>
              <span>TURBIDITY</span>
              <span>TEMP</span>
              <span>WQI</span>
              <span>{dict.dashboard.colStatus}</span>
              <span>SOURCE</span>
            </div>
            {isOffline ? (
              <div className="table-row">
                <span style={{ gridColumn: '1 / -1', textAlign: 'center', opacity: 0.7 }}>
                  Data unavailable while backend is disconnected.
                </span>
              </div>
            ) : filteredWatersheds.length > 0 ? (
              filteredWatersheds.map((row) => {
                const isSelected = row.id === activeId || row.MWS === activeMws
                return (
                  <div
                    className="table-row"
                    key={row.id}
                    style={{
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(46, 125, 50, 0.08)' : 'transparent',
                      gridTemplateColumns: '1fr 1.2fr 0.8fr 1fr 1fr 1fr 1fr 1.2fr 1fr',
                      borderLeft: isSelected ? '3px solid var(--primary)' : 'none',
                    }}
                    onClick={() => onSelectMws(row.id)}
                    title={`Click to inspect Water Quality for ${row.MWS} (${row.id})`}
                  >
                    <strong>{row.MWS}</strong>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em' }}>{row.id}</span>
                    <span>{typeof row.ph === 'number' ? row.ph.toFixed(2) : '—'}</span>
                    <span>{typeof row.tds === 'number' ? `${row.tds.toFixed(0)} mg/L` : '—'}</span>
                    <span>{typeof row.turbidity === 'number' ? `${row.turbidity.toFixed(1)} NTU` : '—'}</span>
                    <span>{typeof row.temperature === 'number' ? `${row.temperature.toFixed(1)} °C` : '—'}</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>{typeof row.wqi === 'number' ? `${row.wqi.toFixed(1)} WQI` : '—'}</strong>
                    <span>
                      <span
                        style={{
                          fontSize: 10,
                          padding: '2px 6px',
                          borderRadius: 3,
                          fontWeight: 600,
                          background:
                            row.quality_category === 'Excellent' || row.quality_category === 'Good'
                              ? '#e8f5e9'
                              : row.quality_category === 'Poor'
                              ? '#fff8e1'
                              : '#ffebee',
                          color:
                            row.quality_category === 'Excellent' || row.quality_category === 'Good'
                              ? '#2e7d32'
                              : row.quality_category === 'Poor'
                              ? '#f57f17'
                              : '#c62828',
                        }}
                      >
                        {row.quality_category}
                      </span>
                    </span>
                    <span className="source-badge simulation small" style={{ fontSize: 9, padding: '1px 5px' }}>
                      simulation
                    </span>
                  </div>
                )
              })
            ) : (
              <div className="table-row">
                <span style={{ gridColumn: '1 / -1', textAlign: 'center', opacity: 0.7 }}>
                  No matching micro-watersheds found.
                </span>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </>
  )
}

function IotNetworkScreen({
  mode,
  setScreen,
  apiStatus,
  liveTelemetry,
  setLiveTelemetry,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  liveTelemetry: LiveRiskResult | null
  setLiveTelemetry: (val: LiveRiskResult | null) => void
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
}) {
  const { dict } = useLanguage()
  const isLive = mode === 'live'
  const isOffline = apiStatus === 'unavailable'
  const hasLive = isLive && liveTelemetry !== null && liveTelemetry.source === 'live' && !liveTelemetry.is_stale
  const isStale = isLive && liveTelemetry !== null && Boolean(liveTelemetry.is_stale)
  const hasSim = !isLive && liveTelemetry !== null && liveTelemetry.source === 'simulation'
  const activeTelemetry = isLive ? (hasLive ? liveTelemetry : null) : (hasSim ? liveTelemetry : null)
  const connectionStatus: 'CONNECTING' | 'CONNECTED' | 'OFFLINE / NO DATA' = isOffline
    ? 'OFFLINE / NO DATA'
    : !liveTelemetry
    ? 'CONNECTING'
    : isStale
    ? 'OFFLINE / NO DATA'
    : 'CONNECTED'

  const activeId = 'g_mws.240575'
  const activeMws = '4D4F2m3'

  // Form State for "Telemetry Test / Demo Input" - consistently pinned to golden demo catchment
  const [inputMwsId, setInputMwsId] = useState('g_mws.240575')
  const [rainfall, setRainfall] = useState('250.0')
  const [soilMoisture, setSoilMoisture] = useState('92.0')
  const [waterLevel, setWaterLevel] = useState('85.0')
  const [turbidity, setTurbidity] = useState('800.0')
  const [submitting, setSubmitting] = useState(false)
  const [submitFeedback, setSubmitFeedback] = useState<{ status: 'success' | 'error'; message: string } | null>(null)

  async function handleTransmitTelemetry(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitFeedback(null)

    const payload: IoTReading = {
      id: inputMwsId,
      mws_code: inputMwsId.startsWith('g_mws') ? '4D4F2m3' : inputMwsId,
      device_id: 'ESP32_SHIGGAON_NODE_01',
      rainfall_mm_hr: parseFloat(rainfall) || 0,
      rainfall_mm: parseFloat(rainfall) || 0,
      soil_moisture_pct: parseFloat(soilMoisture) || 0,
      water_level_cm: parseFloat(waterLevel) || 0,
      turbidity_ntu: parseFloat(turbidity) || 0,
      air_temperature_c: 27.0,
      humidity_pct: 80.0,
      water_temperature_c: 25.0,
      ph: 7.0,
      timestamp: new Date().toISOString(),
    }

    try {
      const res = isLive ? await postLiveTelemetry(payload) : await simulateTelemetryInference(payload)
      if (res.status === 'available' && res.data) {
        setLiveTelemetry(res.data)
        setSubmitFeedback({
          status: 'success',
          message: `Inference success: ML Anomaly ${typeof res.data.live_ml_anomaly_score === 'number' ? res.data.live_ml_anomaly_score.toFixed(1) : '—'}, Risk ${typeof res.data.live_risk_score === 'number' ? res.data.live_risk_score.toFixed(1) : '—'} (${res.data.live_risk_category || '—'}), Alert: ${res.data.compound_alert_level || '—'} [source: ${res.data.source || (isLive ? 'live' : 'simulation')}]`,
        })
      } else {
        setSubmitFeedback({
          status: 'error',
          message: res.error || 'Failed to ingest telemetry payload.',
        })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error'
      setSubmitFeedback({ status: 'error', message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  function loadKnownTestCase() {
    setInputMwsId('g_mws.240575')
    setRainfall('250.0')
    setSoilMoisture('92.0')
    setWaterLevel('85.0')
    setTurbidity('800.0')
  }

  return (
    <div className="iot-page-container">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{dict.sidebar.workspaceLabel} · {dict.subscreens.iotTitle}</span>
          <h1>{dict.subscreens.iotTitle}</h1>
          <p>
            {dict.subscreens.iotSubtitle}
          </p>
        </div>
        <div className="heading-actions">
          <SourceBadge mode={mode} />
          {isLive && (
            <ConnectionStatusBadge
              status={connectionStatus}
              timestamp={liveTelemetry?.timestamp}
            />
          )}
          <button className="outline-button" onClick={() => setScreen('Reports & Exports')}>
            {dict.dashboard.exportBriefing} ↗
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {!isOffline && isLive && (!hasLive || isStale) && (
        <div className="notice warning">
          <strong>Waiting for live telemetry:</strong> Connect physical ESP32 node or transmit sensor packet to <code>/api/v1/telemetry</code>.
        </div>
      )}

      {!isOffline && isLive && hasLive && liveTelemetry && !isStale && (
        <div
          className="notice"
          style={{
            background:
              liveTelemetry.compound_alert_level === 'HIGH ALERT' || liveTelemetry.compound_alert_level === 'EMERGENCY'
                ? '#ffebee'
                : '#e8f5e9',
            border: `1px solid ${
              liveTelemetry.compound_alert_level === 'HIGH ALERT' || liveTelemetry.compound_alert_level === 'EMERGENCY'
                ? '#ba1a1a'
                : '#2e7d32'
            }`,
          }}
        >
          <strong>
            {dict.subscreens.liveTelemetryStream} · {liveTelemetry.compound_alert_level}
          </strong>{' '}
          {dict.mwsProfile.eyebrow} <code>{liveTelemetry.MWS || liveTelemetry.id}</code> ({liveTelemetry.id}) · {dict.subscreens.anomalyScore}: {typeof liveTelemetry.live_ml_anomaly_score === 'number' ? liveTelemetry.live_ml_anomaly_score.toFixed(1) : '—'} · {dict.dashboard.liveTelemetryRiskText}: {typeof liveTelemetry.live_risk_score === 'number' ? liveTelemetry.live_risk_score.toFixed(1) : '—'} ({getLocalizedRiskCategory(liveTelemetry.live_risk_category, dict)}) · {dict.dashboard.liveAlertEvent}: {liveTelemetry.compound_event_type}.
        </div>
      )}

      {!isOffline && !isLive && (
        <div className="notice">
          <strong>{dict.header.simulation.toUpperCase()}:</strong> {dict.sidebar.simScenarioDesc}
        </div>
      )}

      <div className="metric-grid">
        <Metric
          label={dict.subscreens.monitoredCatchments}
          value={
            isOffline
              ? '—'
              : isLive
              ? hasLive && activeTelemetry
                ? activeTelemetry.MWS || activeTelemetry.id
                : 'Waiting for live telemetry'
              : activeTelemetry?.MWS || '4D4F2m3'
          }
          trend={
            isOffline
              ? dict.common.offline
              : isLive
              ? hasLive && activeTelemetry
                ? `Node: ${activeTelemetry.device_id || 'ESP32_SHIGGAON_NODE_01'}`
                : `Status: ${connectionStatus}`
              : `${dict.dashboard.colGisId}: ${activeTelemetry?.id || 'g_mws.240575'}`
          }
        />
        <Metric
          label={dict.subscreens.anomalyScore}
          value={
            isOffline
              ? '—'
              : isLive
              ? hasLive && activeTelemetry && typeof activeTelemetry.live_ml_anomaly_score === 'number'
                ? activeTelemetry.live_ml_anomaly_score.toFixed(1)
                : '—'
              : activeTelemetry && typeof activeTelemetry.live_ml_anomaly_score === 'number'
              ? activeTelemetry.live_ml_anomaly_score.toFixed(1)
              : '43.3'
          }
          unit="/100"
          trend={isLive ? dict.risk.unsupervisedMlModel : `${dict.header.simulation} ${dict.risk.unsupervisedMlModel}`}
          tone={
            isLive
              ? (activeTelemetry?.live_ml_anomaly_score ?? 0) >= 70
                ? 'red'
                : (activeTelemetry?.live_ml_anomaly_score ?? 0) >= 50
                ? 'amber'
                : 'green'
              : 'green'
          }
        />
        <Metric
          label={dict.subscreens.compoundAlertLevel}
          value={
            isOffline
              ? '—'
              : isLive
              ? hasLive && activeTelemetry
                ? activeTelemetry.compound_alert_level || dict.risk.normal
                : '—'
              : activeTelemetry?.compound_alert_level || 'HIGH ALERT'
          }
          trend={
            isLive
              ? (hasLive && activeTelemetry ? (activeTelemetry.compound_event_type ?? undefined) : dict.common.noData)
              : (activeTelemetry?.compound_event_type || 'Compound runoff and flood event')
          }
          tone={
            isLive && hasLive && activeTelemetry
              ? activeTelemetry.compound_alert_level === 'HIGH ALERT' ||
                activeTelemetry.compound_alert_level === 'EMERGENCY'
                ? 'red'
                : activeTelemetry.compound_alert_level === 'WARNING'
                ? 'amber'
                : 'green'
              : 'red'
          }
        />
        <Metric
          label={dict.mwsProfile.finalRiskScoreLabel}
          value={
            isOffline
              ? '—'
              : isLive
              ? hasLive && activeTelemetry && typeof activeTelemetry.live_risk_score === 'number'
                ? activeTelemetry.live_risk_score.toFixed(1)
                : '—'
              : activeTelemetry && typeof activeTelemetry.live_risk_score === 'number'
              ? activeTelemetry.live_risk_score.toFixed(1)
              : '58.9'
          }
          unit="/100"
          trend={
            isLive
              ? (hasLive && activeTelemetry
                ? `${dict.mwsProfile.riskCategoryStat}: ${getLocalizedRiskCategory(activeTelemetry.live_risk_category, dict)}`
                : dict.dashboard.waitingForTelemetryText)
              : `${dict.header.simulation}: ${getLocalizedRiskCategory(activeTelemetry?.live_risk_category || 'HIGH', dict)}`
          }
          tone={
            isLive && hasLive && activeTelemetry
              ? activeTelemetry.live_risk_category === 'CRITICAL' ||
                activeTelemetry.live_risk_category === 'HIGH'
                ? 'red'
                : 'green'
              : 'amber'
          }
        />
      </div>

      <div className="iot-hero-grid">
        <BasinMap
          variant="IoT Network"
          selectedMws={activeTelemetry?.MWS || '4D4F2m3'}
          selectedId={activeTelemetry?.id || 'g_mws.240575'}
          gisBoundaries={gisBoundaries}
          gisStatus={gisStatus}
          gisError={gisError}
          onSelectMws={(id) => {
            setInputMwsId(id)
            onSelectMws(id)
          }}
        />
        <div className="iot-disturbance-panel">
          <div>
            <span className="iot-panel-eyebrow">
              {isOffline
                ? dict.sidebar.statusOffline.toUpperCase()
                : isLive
                ? hasLive
                  ? `${dict.subscreens.liveTelemetryStream} · ${activeTelemetry?.MWS || activeTelemetry?.id}`
                  : dict.dashboard.waitingForTelemetryText.toUpperCase()
                : `${dict.sidebar.simScenario.toUpperCase()} · ${activeTelemetry?.MWS || '4D4F2m3'}`}
            </span>
            <h2 className="iot-panel-title">
              {isOffline
                ? dict.dashboard.apiDisconnectedWarning
                : isLive
                ? hasLive
                  ? `${activeTelemetry?.MWS || activeTelemetry?.id} ${dict.subscreens.liveTelemetryStream}`
                  : dict.dashboard.waitingForTelemetryText
                : `${activeTelemetry?.MWS || '4D4F2m3'} ${dict.sidebar.simScenario}`}
            </h2>
            <p className="iot-panel-desc">
              {isOffline
                ? dict.dashboard.apiDisconnectedWarningDesc
                : isLive
                ? hasLive
                  ? `Online telemetry for ${activeTelemetry?.MWS} (${activeTelemetry?.id}) received at ${activeTelemetry?.timestamp}. ML anomaly score: ${typeof activeTelemetry?.live_ml_anomaly_score === 'number' ? activeTelemetry.live_ml_anomaly_score.toFixed(1) : '—'}/100.`
                  : dict.dashboard.waitingForLiveTelemetryDesc
                : `Simulation mode exercises the full Model 2 calibrated disturbance engine for golden catchment ${activeTelemetry?.MWS || '4D4F2m3'} (${activeTelemetry?.id || 'g_mws.240575'}).`}
            </p>
          </div>

          <div className="iot-panel-divider" />

          <div>
            <span className="iot-sensor-heading">{dict.subscreens.activeSensorNodes.toUpperCase()}</span>
            <div className="iot-sensor-card">
              <div className="iot-sensor-cell">
                <span className="iot-sensor-label">{dict.subscreens.rainfallIntensity.toUpperCase()}</span>
                <strong className="iot-sensor-value">
                  {isLive
                    ? hasLive && activeTelemetry && typeof (activeTelemetry.rainfall_mm_hr ?? activeTelemetry.rainfall_mm) === 'number'
                      ? `${(activeTelemetry.rainfall_mm_hr ?? activeTelemetry.rainfall_mm ?? 0).toFixed(1)} mm/hr`
                      : '—'
                    : `${(activeTelemetry?.rainfall_mm ?? activeTelemetry?.rainfall ?? 250.0).toFixed(1)} mm/hr`}
                </strong>
                <span className="iot-sensor-desc">
                  z-score: {isLive ? (hasLive && typeof activeTelemetry?.rainfall_z_score === 'number' ? activeTelemetry.rainfall_z_score.toFixed(2) : '—') : (typeof activeTelemetry?.rainfall_z_score === 'number' ? activeTelemetry.rainfall_z_score.toFixed(2) : '1.88')}
                </span>
              </div>

              <div className="iot-sensor-cell">
                <span className="iot-sensor-label">{dict.subscreens.soilMoisture.toUpperCase()}</span>
                <strong className="iot-sensor-value">
                  {isLive
                    ? hasLive && activeTelemetry && typeof (activeTelemetry.soil_moisture_pct ?? activeTelemetry.soil_moisture) === 'number'
                      ? `${(activeTelemetry.soil_moisture_pct ?? activeTelemetry.soil_moisture ?? 0).toFixed(1)} %`
                      : '—'
                    : `${(activeTelemetry?.soil_moisture_pct ?? activeTelemetry?.soil_moisture ?? 92.0).toFixed(1)} %`}
                </strong>
                <span className="iot-sensor-desc">
                  {dict.mwsProfile.actionMonitoringFocus}
                </span>
              </div>

              <div className="iot-sensor-cell">
                <span className="iot-sensor-label">{dict.subscreens.surfaceWaterLevel.toUpperCase()}</span>
                <strong className="iot-sensor-value">
                  {isLive
                    ? hasLive && activeTelemetry && typeof (activeTelemetry.water_level_cm ?? activeTelemetry.water_level) === 'number'
                      ? `${(activeTelemetry.water_level_cm ?? activeTelemetry.water_level ?? 0).toFixed(1)} cm`
                      : '—'
                    : `${(activeTelemetry?.water_level_cm ?? activeTelemetry?.water_level ?? 85.0).toFixed(1)} cm`}
                </strong>
                <span className="iot-sensor-desc">
                  {dict.gis3d.waterElevation}
                </span>
              </div>

              <div className="iot-sensor-cell">
                <span className="iot-sensor-label">{dict.subscreens.turbidity.toUpperCase()}</span>
                <strong className="iot-sensor-value">
                  {isLive
                    ? hasLive && activeTelemetry && typeof (activeTelemetry.turbidity_ntu ?? activeTelemetry.turbidity) === 'number'
                      ? `${(activeTelemetry.turbidity_ntu ?? activeTelemetry.turbidity ?? 0).toFixed(1)} NTU`
                      : '—'
                    : `${(activeTelemetry?.turbidity_ntu ?? activeTelemetry?.turbidity ?? 800.0).toFixed(1)} NTU`}
                </strong>
                <span className="iot-sensor-desc">
                  sediment load
                </span>
              </div>
            </div>
          </div>

          <div className="iot-panel-divider" />

          <div className="iot-panel-stats">
            <div>
              <span className="iot-stat-label">{dict.dashboard.inputSourceLabel}</span>
              <strong className="iot-stat-value">
                {activeTelemetry?.source ? (activeTelemetry.source === 'live' ? dict.header.liveIot : dict.header.simulation) : (isLive ? (hasLive ? dict.header.liveIot : dict.common.loading) : dict.header.simulation)}
              </strong>
            </div>
            <div>
              <span className="iot-stat-label">{dict.dashboard.liveAlertEvent}</span>
              <strong
                className="iot-stat-value"
                style={{
                  color: (activeTelemetry?.compound_event_detected ?? !isLive) ? '#fca5a5' : '#86efac',
                }}
              >
                {(activeTelemetry?.compound_event_detected ?? !isLive) ? 'YES' : 'NO'}
              </strong>
            </div>
            <div>
              <span className="iot-stat-label">{dict.dashboard.colStatus}</span>
              <strong className="iot-stat-value">
                {isOffline ? dict.common.offline : isLive ? (hasLive ? dict.common.active : dict.sidebar.statusConnecting) : dict.header.simulation}
              </strong>
            </div>
          </div>
        </div>
      </div>

      <div className="detail-columns">
        {/* Left Column: Compound Event Intelligence & Recommended Actions */}
        <Panel title={dict.subscreens.compoundAlertEngine} eyebrow="DECISION SUPPORT">
          <div className="indicator-list">
            <div>
              <span>{dict.mwsProfile.eyebrow}</span>
              <strong style={{ maxWidth: 260, textAlign: 'right' }}>
                {activeTelemetry?.MWS || '4D4F2m3'} ({activeTelemetry?.id || 'g_mws.240575'})
              </strong>
            </div>
            <div>
              <span>{dict.dashboard.liveAlertEvent}</span>
              <strong style={{ maxWidth: 260, textAlign: 'right' }}>
                {activeTelemetry?.compound_event_type || (isLive ? dict.dashboard.waitingForTelemetryText : 'Compound runoff and flood event')}
              </strong>
            </div>
            <div>
              <span>{dict.subscreens.compoundAlertLevel}</span>
              <strong
                className={
                  (activeTelemetry?.compound_alert_level || (!isLive ? 'HIGH ALERT' : '')) === 'HIGH ALERT' ||
                  activeTelemetry?.compound_alert_level === 'EMERGENCY'
                    ? 'red'
                    : activeTelemetry?.compound_alert_level === 'WARNING'
                    ? 'amber'
                    : 'green'
                }
              >
                {activeTelemetry?.compound_alert_level || (isLive ? dict.sidebar.statusConnecting : 'HIGH ALERT')}
              </strong>
            </div>
            <div>
              <span>{dict.dashboard.primaryDriversTitle}</span>
              <strong style={{ maxWidth: 260, textAlign: 'right', fontSize: 11 }}>
                {activeTelemetry?.live_risk_drivers || (isLive ? dict.dashboard.waitingForTelemetryText : 'Extreme rainfall anomaly; High soil saturation; Elevated water level; High sediment/turbidity')}
              </strong>
            </div>
            <div>
              <span>{dict.dashboard.liveAlertAction}</span>
              <strong style={{ maxWidth: 260, textAlign: 'right', fontSize: 11 }}>
                {activeTelemetry?.recommended_action || (isLive ? dict.dashboard.waitingForTelemetryText : 'Conduct field inspection and monitor downstream areas for possible flooding or erosion')}
              </strong>
            </div>
            <div>
              <span>{dict.subscreens.liveTelemetryStream}</span>
              <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {activeTelemetry?.timestamp || (isLive ? '—' : dict.header.simulation)}
              </strong>
            </div>
          </div>
        </Panel>

        {/* Right Column: Telemetry Test / Demo Input (Strict Section 14 Compliance) */}
        <Panel title={dict.subscreens.simulateReadingBtn} eyebrow="DEVELOPER / DEMO CONSOLE">
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.4 }}>
            <strong>Hardware Notice:</strong> Software verification environment. Physical ESP32 hardware is not required or connected. Use this testing console to simulate an ESP32 sensor node HTTP POST to <code>/api/v1/telemetry</code>.
          </div>

          <form onSubmit={handleTransmitTelemetry} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                {dict.mwsProfile.eyebrow}
              </label>
              <select
                value={inputMwsId}
                onChange={(e) => setInputMwsId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  fontSize: 12,
                  borderRadius: 4,
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  color: 'var(--foreground)',
                }}
              >
                {watersheds.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.MWS} ({w.id})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  {dict.subscreens.rainfallIntensity} (mm)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={rainfall}
                  onChange={(e) => setRainfall(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    fontSize: 12,
                    borderRadius: 4,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                    color: 'var(--foreground)',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  {dict.subscreens.soilMoisture} (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={soilMoisture}
                  onChange={(e) => setSoilMoisture(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    fontSize: 12,
                    borderRadius: 4,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                    color: 'var(--foreground)',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  {dict.subscreens.surfaceWaterLevel} (cm)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={waterLevel}
                  onChange={(e) => setWaterLevel(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    fontSize: 12,
                    borderRadius: 4,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                    color: 'var(--foreground)',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  {dict.subscreens.turbidity} (NTU)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={turbidity}
                  onChange={(e) => setTurbidity(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    fontSize: 12,
                    borderRadius: 4,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                    color: 'var(--foreground)',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
              <button
                type="button"
                onClick={loadKnownTestCase}
                className="outline-button"
                style={{ fontSize: 11, padding: '6px 10px' }}
                title="Load known regression test: g_mws.240575, 250mm, 92%, 85cm, 800NTU"
              >
                Load Known Case (4D4F2m3)
              </button>
              <button
                type="submit"
                disabled={submitting || isOffline}
                className="outline-button"
                style={{
                  fontSize: 11,
                  padding: '6px 12px',
                  background: 'var(--primary)',
                  color: '#fff',
                  border: 'none',
                  flex: 1,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                }}
              >
                {submitting ? dict.common.loading : isLive ? 'POST Live Telemetry' : 'POST Simulation Telemetry'}
              </button>
            </div>

            {submitFeedback && (
              <div
                style={{
                  fontSize: 11,
                  marginTop: 6,
                  padding: '6px 8px',
                  borderRadius: 4,
                  background: submitFeedback.status === 'success' ? '#e8f5e9' : '#ffebee',
                  color: submitFeedback.status === 'success' ? '#1b5e20' : '#ba1a1a',
                }}
              >
                {submitFeedback.message}
              </div>
            )}
          </form>
        </Panel>
      </div>
    </div>
  )
}

function FieldObservationsScreen({
  mode,
  setScreen,
  apiStatus,
  observations,
  obsStatus,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
  onObservationsUpdated,
  onNavigateToGis,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  observations: EvidenceItem[]
  obsStatus: DataStatus
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
  onObservationsUpdated?: (newObs: EvidenceItem[]) => void
  onNavigateToGis?: (obs: EvidenceItem) => void
}) {
  const { dict } = useLanguage()
  const isOffline = apiStatus === 'unavailable' || obsStatus === 'unavailable'
  const isLoading = obsStatus === 'loading'
  const [selectedObs, setSelectedObs] = useState<EvidenceItem | null>(null)
  const [photoUrls, setPhotoUrls] = useState<Record<string, string>>({})

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStage, setUploadStage] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle')
  const [uploadProgress, setUploadProgress] = useState<string>('')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [lastBatchSummary, setLastBatchSummary] = useState<BatchUploadResponse | null>(null)

  const validGeotagged = observations.filter(
    (o) => o.latitude !== null && o.longitude !== null && o.coordinate_status !== 'MISSING' && o.observation_status !== 'NO_GPS'
  )
  const insideBoundary = observations.filter((o) => o.boundary_status === 'INSIDE')
  const mwsResolved = observations.filter((o) => o.id !== null || o.MWS !== null)

  // Synchronize observation and active MWS strictly to selectedProfile
  const activeObs = selectedObs && (selectedObs.id === selectedProfile?.id || selectedObs.MWS === selectedProfile?.MWS)
    ? selectedObs
    : observations.find((o) => o.id === selectedProfile?.id || o.MWS === selectedProfile?.MWS) || (observations.length > 0 ? observations[0] : null)
  const activeMws = selectedProfile?.MWS || activeObs?.MWS || '4D4F2m3'
  const activeId = selectedProfile?.id || activeObs?.id || 'g_mws.240575'

  // Authoritative watershed risk and LULC resolution for the active observation
  const activeMwsSummary = watersheds.find(
    (w) => (activeObs?.id && w.id === activeObs.id) || (activeObs?.MWS && w.MWS === activeObs.MWS)
  )
  const lulcClass = activeObs?.lulc_class || activeMwsSummary?.dominant_class || selectedProfile?.lulc?.dominant_class || 'Agriculture'
  const riskCategory = activeMwsSummary?.risk_category || selectedProfile?.risk?.risk_category || 'HIGH'
  const riskScore = activeMwsSummary?.final_risk_score ?? activeMwsSummary?.risk_score ?? selectedProfile?.risk?.final_risk_score ?? null
  const primaryDriver = activeMwsSummary?.primary_driver || selectedProfile?.risk?.primary_driver || 'Water Stress'

  const spatialInterpretation = activeObs
    ? `This geo-coded observation is located within ${activeObs.MWS || activeMws}. The location is associated with ${lulcClass} land cover and a ${riskCategory} watershed-risk classification, primarily influenced by ${primaryDriver}.`
    : null

  const [activeInterventions, setActiveInterventions] = useState<WatershedInterventions | null>(null)

  useEffect(() => {
    if (!activeObs) {
      setActiveInterventions(null)
      return
    }
    const matchId = activeObs.id || activeObs.MWS
    if (!matchId) {
      setActiveInterventions(null)
      return
    }
    if (selectedProfile && (selectedProfile.id === activeObs.id || selectedProfile.MWS === activeObs.MWS)) {
      setActiveInterventions(selectedProfile.interventions || null)
      return
    }
    let isMounted = true
    fetchWatershedProfile(matchId).then((res) => {
      if (isMounted && res.status === 'available' && res.data) {
        setActiveInterventions(res.data.interventions || null)
      } else if (isMounted) {
        setActiveInterventions(null)
      }
    })
    return () => {
      isMounted = false
    }
  }, [activeObs, selectedProfile])

  const recommendedAction =
    activeInterventions?.primary_intervention ||
    selectedProfile?.interventions?.primary_intervention ||
    null

  const fieldEvidenceText = activeObs?.filename
    ? `${activeObs.filename}${activeObs.observation_status && activeObs.observation_status !== 'OK' && activeObs.observation_status !== 'available' ? ` (${activeObs.observation_status})` : ''}`
    : 'Field evidence recorded without observation classification.'

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    const fileList = Array.from(files)
    // Create local object URLs for immediate high-resolution preview
    const newUrls: Record<string, string> = {}
    fileList.forEach((f) => {
      newUrls[f.name] = URL.createObjectURL(f)
    })
    setPhotoUrls((prev) => ({ ...prev, ...newUrls }))
    // Client-side validation: formats
    const validExtensions = ['.jpg', '.jpeg', '.png']
    const invalidFormatFiles = fileList.filter((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase()
      return !validExtensions.includes(ext)
    })
    if (invalidFormatFiles.length > 0) {
      setUploadError(
        `Unsupported file type(s): ${invalidFormatFiles.map((f) => f.name).join(', ')}. Only JPG, JPEG, and PNG are supported.`
      )
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    // Client-side validation: max size (25MB)
    const oversizedFiles = fileList.filter((f) => f.size > 25 * 1024 * 1024)
    if (oversizedFiles.length > 0) {
      setUploadError(
        `File(s) exceed 25MB limit: ${oversizedFiles.map((f) => f.name).join(', ')}.`
      )
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setUploadError(null)
    setIsUploading(true)
    setUploadStage('uploading')
    setUploadProgress(`Uploading ${fileList.length} photo${fileList.length > 1 ? 's' : ''}...`)

    const timer = setTimeout(() => {
      setUploadStage('processing')
      setUploadProgress('Extracting EXIF GPS, validating boundaries & resolving 66-MWS...')
    }, 400)

    try {
      const res = await uploadFieldPhotos(fileList)
      clearTimeout(timer)
      if (res.status === 'available' && res.data) {
        setUploadStage('done')
        setLastBatchSummary(res.data)
        if (onObservationsUpdated && res.data.ledger) {
          onObservationsUpdated(res.data.ledger)
        }
        const firstWithMws = res.data.ledger.find((o) => o.id)
        if (firstWithMws && firstWithMws.id) {
          onSelectMws(firstWithMws.id)
          setSelectedObs(firstWithMws)
        }
      } else {
        setUploadStage('error')
        setUploadError(res.error || 'Failed to process photos through pipeline.')
      }
    } catch (err: unknown) {
      clearTimeout(timer)
      setUploadStage('error')
      setUploadError(err instanceof Error ? err.message : 'Network error during photo upload.')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span className="eyebrow">{dict.sidebar.workspaceLabel} · {dict.subscreens.fieldObsTitle}</span>
            <span className="source-badge live small">
              <span className="source-dot" />
              {dict.subscreens.fieldObsTitle}
            </span>
          </div>
          <h1>{dict.subscreens.fieldObsTitle}</h1>
          <p>
            {dict.subscreens.fieldObsSubtitle}
          </p>
        </div>
        <div className="heading-actions">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          <button
            className="outline-button"
            disabled={isUploading || isOffline}
            onClick={() => fileInputRef.current?.click()}
            style={{
              background: '#15803d',
              color: '#ffffff',
              borderColor: '#15803d',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontWeight: 600,
              cursor: isUploading || isOffline ? 'not-allowed' : 'pointer',
              opacity: isOffline ? 0.6 : 1,
            }}
          >
            {isUploading ? (
              <>
                <span
                  style={{
                    display: 'inline-block',
                    width: 12,
                    height: 12,
                    border: '2px solid #fff',
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                  }}
                />
                <span>{uploadStage === 'processing' ? dict.common.loading : dict.common.loading}</span>
              </>
            ) : (
              <>
                <span style={{ fontSize: 13 }}>📷</span>
                <span>{dict.subscreens.selectPhotosBtn}</span>
              </>
            )}
          </button>
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            ← {dict.mwsProfile.backToDashboard}
          </button>
          <button className="outline-button" onClick={() => setScreen('GIS Explorer')}>
            {dict.mwsProfile.viewInGis} ↗
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {isUploading && (
        <div
          className="notice"
          style={{
            background: 'rgba(21, 128, 61, 0.08)',
            borderColor: 'rgba(21, 128, 61, 0.3)',
            color: '#15803d',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <strong>Geo-Coded Pipeline Active:</strong> {uploadProgress}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            Pipeline Steps: EXIF GPS → Validate → Taluk Boundary → 66-MWS → LULC
          </div>
        </div>
      )}

      {uploadError && (
        <div className="notice warning" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <strong>Upload Error:</strong> {uploadError}
          </div>
          <button
            className="outline-button"
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={() => setUploadError(null)}
          >
            {dict.common.dismiss} ✕
          </button>
        </div>
      )}

      {lastBatchSummary && (
        <div
          style={{
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: 8,
            padding: '14px 16px',
            marginBottom: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14 }}>✓</span>
              <strong style={{ fontSize: 13, color: '#166534' }}>
                Batch Ingestion Complete: {lastBatchSummary.summary_message}
              </strong>
            </div>
            <button
              className="outline-button"
              style={{ padding: '2px 8px', fontSize: 11, background: '#fff', borderColor: '#bbf7d0', color: '#166534' }}
              onClick={() => setLastBatchSummary(null)}
            >
              Dismiss Summary ✕
            </button>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, fontSize: 11, marginTop: 6 }}>
            <span style={{ padding: '3px 8px', borderRadius: 4, background: '#dcfce7', color: '#166534', fontWeight: 600 }}>
              ● Successfully processed: {lastBatchSummary.results.filter((r) => r.state_category === 'processed').length}
            </span>
            {lastBatchSummary.rejected_missing_gps > 0 && (
              <span style={{ padding: '3px 8px', borderRadius: 4, background: '#fee2e2', color: '#991b1b', fontWeight: 600 }}>
                ● Rejected / missing GPS: {lastBatchSummary.rejected_missing_gps}
              </span>
            )}
            {lastBatchSummary.outside_boundary > 0 && (
              <span style={{ padding: '3px 8px', borderRadius: 4, background: '#fef3c7', color: '#92400e', fontWeight: 600 }}>
                ● Outside boundary: {lastBatchSummary.outside_boundary}
              </span>
            )}
            {lastBatchSummary.mws_unresolved > 0 && (
              <span style={{ padding: '3px 8px', borderRadius: 4, background: '#fef3c7', color: '#92400e', fontWeight: 600 }}>
                ● MWS unresolved: {lastBatchSummary.mws_unresolved}
              </span>
            )}
            {lastBatchSummary.failed_or_invalid > 0 && (
              <span style={{ padding: '3px 8px', borderRadius: 4, background: '#f3f4f6', color: '#374151', fontWeight: 600 }}>
                ● Failed / Invalid format: {lastBatchSummary.failed_or_invalid}
              </span>
            )}
          </div>

          <div style={{ marginTop: 10, borderTop: '1px solid #dcfce7', paddingTop: 8, fontSize: 11 }}>
            <div style={{ color: '#166534', fontWeight: 600, marginBottom: 4 }}>Batch Results Detail:</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 6 }}>
              {lastBatchSummary.results.map((item, idx) => {
                const stateLabel =
                  item.state_category === 'processed'
                    ? 'Successfully processed'
                    : item.state_category === 'missing_gps'
                    ? 'Rejected / missing GPS'
                    : item.state_category === 'outside_boundary'
                    ? 'Outside boundary'
                    : item.state_category === 'mws_unresolved'
                    ? 'MWS unresolved'
                    : item.state_category === 'rejected'
                    ? 'Rejected'
                    : 'Pipeline error'

                const badgeBg =
                  item.state_category === 'processed'
                    ? '#dcfce7'
                    : item.state_category === 'missing_gps'
                    ? '#fee2e2'
                    : '#fef3c7'
                const badgeColor =
                  item.state_category === 'processed'
                    ? '#166534'
                    : item.state_category === 'missing_gps'
                    ? '#991b1b'
                    : '#92400e'

                return (
                  <div
                    key={idx}
                    style={{
                      background: '#fff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 6,
                      padding: '6px 10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 600, color: 'var(--foreground)' }}>{item.filename}</span>
                      <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600, background: badgeBg, color: badgeColor }}>
                        {stateLabel}
                      </span>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                      {item.image_id ? `ID: ${item.image_id} · ` : ''}
                      {item.mws_code ? `MWS: ${item.mws_code} (${item.micro_watershed_id}) · ` : ''}
                      {item.lulc_class ? `LULC: ${item.lulc_class}` : item.error_reason || 'EXIF inspection complete'}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="notice">
          <strong>Querying Geo-Coded Evidence...</strong> Ingesting validated photo points and micro-watershed spatial joins.
        </div>
      )}

      {!isOffline && !isLoading && observations.length === 0 && !lastBatchSummary && (
        <div
          className="notice"
          style={{
            background: 'rgba(56, 189, 248, 0.08)',
            borderColor: 'rgba(56, 189, 248, 0.3)',
            color: '#0369a1',
          }}
        >
          <strong>{dict.common.noData}.</strong> Process geotagged field photos through the Geo-Coded pipeline to populate ground-truth records. Zero mock observations or fabricated coordinates are displayed.
        </div>
      )}

      {/* Top 4 KPI Metric Cards */}
      <div className="metric-grid">
        <Metric
          label={dict.subscreens.totalObs}
          value={isOffline ? '—' : String(observations.length)}
          trend={observations.length > 0 ? `${observations.length} ${dict.common.available}` : dict.common.noData}
        />
        <Metric
          label={dict.subscreens.validGeotagged}
          value={isOffline ? '—' : String(validGeotagged.length)}
          trend={observations.length > 0 ? `${Math.round((validGeotagged.length / (observations.length || 1)) * 100)}% valid EXIF` : 'EXIF GPS check'}
        />
        <Metric
          label={dict.subscreens.insideBasin}
          value={isOffline ? '—' : String(insideBoundary.length)}
          trend={observations.length > 0 ? `${insideBoundary.length} in Shiggaon` : 'Boundary-first check'}
        />
        <Metric
          label={dict.subscreens.mwsResolved}
          value={isOffline ? '—' : String(mwsResolved.length)}
          trend={observations.length > 0 ? `${mwsResolved.length} joined to 66-MWS` : 'Canonical id join'}
        />
      </div>

      {/* Detail Hero: BasinMap + HUD */}
      <div className="detail-hero">
        <BasinMap
          variant="Field Observations"
          selectedMws={activeMws}
          selectedId={activeId}
          gisBoundaries={gisBoundaries}
          gisStatus={gisStatus}
          gisError={gisError}
          onSelectMws={(mwsId) => {
            onSelectMws(mwsId)
            const match = observations.find((o) => o.id === mwsId || o.MWS === mwsId)
            setSelectedObs(match || null)
          }}
        />
        <div className="detail-summary">
          <div>
            <span className="eyebrow">
              {isOffline
                ? dict.sidebar.statusOffline.toUpperCase()
                : observations.length > 0
                ? activeObs
                  ? `LEDGER ID: ${activeObs.image_id || 'PENDING'}`
                  : dict.subscreens.fieldObsTitle.toUpperCase()
                : dict.common.noData.toUpperCase()}
            </span>
            <h2>
              {isOffline
                ? dict.dashboard.apiDisconnectedWarning
                : observations.length > 0
                ? activeObs
                  ? `Site Photo: ${activeObs.filename}`
                  : dict.subscreens.fieldObsTitle
                : dict.common.noData}
            </h2>
            <p>
              {isOffline
                ? dict.dashboard.apiDisconnectedWarningDesc
                : observations.length > 0
                ? activeObs
                  ? `Catchment: ${activeObs.MWS || 'Unassigned'} (${activeObs.id || 'N/A'}) | Coordinates: ${
                      typeof activeObs.latitude === 'number' && typeof activeObs.longitude === 'number'
                        ? `${activeObs.latitude.toFixed(5)}°N, ${activeObs.longitude.toFixed(5)}°E`
                        : 'Missing GPS'
                    } | LULC: ${activeObs.lulc_class || 'Unclassified'}`
                  : dict.subscreens.fieldObsSubtitle
                : 'The system strictly rejects fabricated observations. Ingest geotagged field survey photos into the Geo-Coded pipeline to view ground-truth validations here.'}
            </p>
          </div>
          <div>
            <div className="summary-stats">
              <Metric
                label="OBSERVATION INTEGRITY"
                value={isOffline ? '—' : observations.length > 0 ? dict.common.available : dict.common.noData}
              />
              <Metric
                label={dict.dashboard.colGisId}
                value={isOffline ? '—' : activeId}
              />
              <Metric
                label={dict.dashboard.inputSourceLabel}
                value={isOffline ? dict.common.offline : dict.subscreens.fieldObsTitle}
              />
            </div>
            {activeId && (
              <button
                className="outline-button full"
                style={{ marginTop: 16, background: '#fff', color: 'var(--primary)' }}
                onClick={() => {
                  onSelectMws(activeId)
                  setScreen('Micro-Watershed Profile')
                }}
              >
                {dict.mwsProfile.profileTitle} ({activeMws}) →
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Observation Table and 10-Step Pipeline Audit Panel */}
      <div className="detail-columns">
        <Panel title={dict.subscreens.obsLedgerTitle} eyebrow="GROUND TRUTH RECORDS">
          {observations.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)', fontSize: 11 }}>
                    <th style={{ padding: '8px 6px' }}>Image ID</th>
                    <th style={{ padding: '8px 6px' }}>Filename</th>
                    <th style={{ padding: '8px 6px' }}>Coordinates</th>
                    <th style={{ padding: '8px 6px' }}>{dict.mwsProfile.eyebrow}</th>
                    <th style={{ padding: '8px 6px' }}>{dict.mwsProfile.dominantLulcMetricLabel}</th>
                    <th style={{ padding: '8px 6px' }}>{dict.subscreens.insideBasin}</th>
                    <th style={{ padding: '8px 6px' }}>{dict.dashboard.colStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {observations.map((obs, i) => {
                    const isSelected = activeObs?.image_id === obs.image_id
                    return (
                      <tr
                        key={obs.image_id || `obs-${i}`}
                        onClick={() => {
                          setSelectedObs(obs)
                          if (obs.id) onSelectMws(obs.id)
                        }}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '8px 6px', fontWeight: 600 }}>{obs.image_id || '—'}</td>
                        <td style={{ padding: '8px 6px' }}>{obs.filename}</td>
                        <td style={{ padding: '8px 6px', fontFamily: 'monospace' }}>
                          {typeof obs.latitude === 'number' && typeof obs.longitude === 'number'
                            ? `${obs.latitude.toFixed(4)}, ${obs.longitude.toFixed(4)}`
                            : '—'}
                        </td>
                        <td style={{ padding: '8px 6px', fontWeight: 600 }}>
                          {obs.MWS ? (
                            <span>
                              {obs.MWS} <span style={{ color: 'var(--muted)', fontSize: 10 }}>({obs.id})</span>
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td style={{ padding: '8px 6px' }}>{obs.lulc_class || '—'}</td>
                        <td style={{ padding: '8px 6px' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 6px',
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 600,
                              background: obs.boundary_status === 'INSIDE' ? '#e8f5e9' : '#fff3e0',
                              color: obs.boundary_status === 'INSIDE' ? '#1b5e20' : '#e65100',
                            }}
                          >
                            {obs.boundary_status || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '8px 6px' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 6px',
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 600,
                              background:
                                obs.observation_status === 'OK' || obs.coordinate_status === 'VALID'
                                  ? '#e8f5e9'
                                  : '#ffebee',
                              color:
                                obs.observation_status === 'OK' || obs.coordinate_status === 'VALID'
                                  ? '#1b5e20'
                                  : '#c62828',
                            }}
                          >
                            {obs.observation_status || obs.coordinate_status || '—'}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              style={{
                padding: '32px 20px',
                textAlign: 'center',
                background: 'rgba(255, 255, 255, 0.6)',
                borderRadius: 8,
                border: '1px dashed var(--border)',
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.7 }}>◉</div>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Zero Field Observations Ingested</h3>
              <p
                style={{
                  fontSize: 12,
                  color: 'var(--muted)',
                  maxWidth: 440,
                  margin: '0 auto 16px',
                  lineHeight: 1.5,
                }}
              >
                The Geo-Coded pipeline currently has no processed photo records. Upload geotagged field survey photos to the image pipeline to extract EXIF metadata, validate coordinates, verify Taluk boundaries, and link canonical micro-watersheds.
              </p>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 6,
                  background: '#f8fafc',
                  border: '1px solid var(--border)',
                  fontSize: 11,
                  color: 'var(--muted)',
                }}
              >
                <span>🔒 Data Honesty Contract: Zero mock coordinates or fake thumbnails are substituted.</span>
              </div>
            </div>
          )}
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {observations.length > 0 && activeObs && (
            <Panel title="Geo-coded image interpretation" eyebrow="SPATIAL REASONING ENGINE">
              {/* Visual Pipeline */}
              <div style={{ background: '#f8fafc', borderRadius: 8, padding: '12px 14px', border: '1px solid var(--border)', marginBottom: 16 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                  VISUAL REASONING PIPELINE
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {[
                    { label: 'Geo-coded Image', val: activeObs.filename, icon: '📷' },
                    { label: 'GPS Location', val: typeof activeObs.latitude === 'number' && typeof activeObs.longitude === 'number' ? `${activeObs.latitude.toFixed(4)}°N, ${activeObs.longitude.toFixed(4)}°E` : 'Valid EXIF GPS', icon: '📍' },
                    { label: 'Micro-Watershed', val: `${activeObs.MWS || activeMws} (${activeObs.id || activeId})`, icon: '🗺️' },
                    { label: 'Satellite LULC', val: `${lulcClass} (Satellite Layer)`, icon: '🛰️' },
                    { label: 'Watershed Risk', val: `${riskCategory}${riskScore !== null ? ` (${riskScore})` : ''} · ${primaryDriver}`, icon: '⚠️' },
                    { label: 'Spatial Interpretation', val: 'Synthesis Complete', icon: '🧠' },
                  ].map((step, idx, arr) => (
                    <div key={idx}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, background: '#fff', padding: '6px 10px', borderRadius: 5, border: '1px solid #e2e8f0' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#1e293b' }}>
                          <span>{step.icon}</span>
                          <span>{step.label}</span>
                        </span>
                        <span style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono, monospace)', fontSize: 10 }}>
                          {step.val}
                        </span>
                      </div>
                      {idx < arr.length - 1 && (
                        <div style={{ textAlign: 'center', color: '#15803d', fontSize: 11, lineHeight: '14px', fontWeight: 700 }}>
                          ↓
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* FIELD IMAGE */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                  FIELD IMAGE
                </div>
                {photoUrls[activeObs.filename] ? (
                  <div style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)', background: '#0f172a', maxHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <img
                      src={photoUrls[activeObs.filename]}
                      alt={activeObs.filename}
                      style={{ maxWidth: '100%', maxHeight: 220, objectFit: 'contain' }}
                    />
                  </div>
                ) : (
                  <div style={{
                    borderRadius: 8,
                    border: '1px dashed var(--border)',
                    background: '#f8fafc',
                    padding: '20px 14px',
                    textAlign: 'center',
                    color: 'var(--muted)',
                    fontSize: 12,
                  }}>
                    <div style={{ fontSize: 26, marginBottom: 4 }}>📷</div>
                    <strong style={{ color: 'var(--primary)', display: 'block', fontSize: 13 }}>{activeObs.filename}</strong>
                    <span style={{ fontSize: 11 }}>Field Photograph · {activeObs.image_id || 'ID Recorded'}</span>
                  </div>
                )}
              </div>

              {/* GEO-SPATIAL CONTEXT */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                  GEO-SPATIAL CONTEXT
                </div>
                <div style={{ background: '#f8fafc', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 11.5 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: 'var(--muted)' }}>GPS:</span>
                    <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#0f172a' }}>
                      {typeof activeObs.latitude === 'number' && typeof activeObs.longitude === 'number'
                        ? `${activeObs.latitude.toFixed(5)}°N, ${activeObs.longitude.toFixed(5)}°E`
                        : 'Missing GPS'}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: 'var(--muted)' }}>Micro-Watershed:</span>
                    <strong style={{ color: 'var(--primary)' }}>{activeObs.MWS || activeMws}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                    <span style={{ color: 'var(--muted)' }}>GIS ID:</span>
                    <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#475569' }}>{activeObs.id || activeId}</strong>
                  </div>
                </div>
              </div>

              {/* WATERSHED CONTEXT */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                  WATERSHED CONTEXT
                </div>
                <div style={{ background: '#f8fafc', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 11.5 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: 'var(--muted)' }}>LULC:</span>
                    <strong style={{ color: '#0f172a' }}>{lulcClass}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: 'var(--muted)' }}>Risk:</span>
                    <strong style={{
                      color: riskCategory === 'CRITICAL' ? '#dc2626' : riskCategory === 'HIGH' ? '#d97706' : '#16a34a',
                    }}>
                      {riskCategory} {riskScore !== null ? `(${riskScore})` : ''}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                    <span style={{ color: 'var(--muted)' }}>Primary Driver:</span>
                    <strong style={{ color: '#0f172a' }}>{primaryDriver}</strong>
                  </div>
                </div>
              </div>

              {/* SPATIAL INTERPRETATION */}
              <div style={{
                background: 'rgba(21, 128, 61, 0.06)',
                border: '1px solid rgba(21, 128, 61, 0.25)',
                borderRadius: 8,
                padding: '12px 14px',
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: '#166534', textTransform: 'uppercase', marginBottom: 4 }}>
                  SPATIAL INTERPRETATION
                </div>
                <p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: '#14532d', fontWeight: 500 }}>
                  "{spatialInterpretation}"
                </p>
              </div>

              {/* WATERSHED DECISION SUPPORT */}
              <div
                style={{
                  background: 'rgba(2, 132, 199, 0.04)',
                  border: '1px solid rgba(2, 132, 199, 0.25)',
                  borderRadius: 8,
                  padding: '12px 14px',
                  marginTop: 14,
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.07em',
                    color: '#0284c7',
                    textTransform: 'uppercase',
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>🌱</span>
                  <span>WATERSHED DECISION SUPPORT</span>
                </div>

                {/* Small Visual Flow */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 2,
                    fontSize: 10,
                    fontWeight: 600,
                    background: '#ffffff',
                    padding: '8px 10px',
                    borderRadius: 6,
                    border: '1px solid #e0f2fe',
                    marginBottom: 12,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#1e293b' }}>
                    <span>📷</span>
                    <span>Field Evidence</span>
                  </div>
                  <div style={{ color: '#0284c7', fontSize: 9, lineHeight: '10px' }}>↓</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#1e293b' }}>
                    <span>🗺️</span>
                    <span>Spatial Context</span>
                  </div>
                  <div style={{ color: '#0284c7', fontSize: 9, lineHeight: '10px' }}>↓</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#1e293b' }}>
                    <span>📊</span>
                    <span>Watershed Analytics</span>
                  </div>
                  <div style={{ color: '#0284c7', fontSize: 9, lineHeight: '10px' }}>↓</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#15803d' }}>
                    <span>🎯</span>
                    <span>Recommended Action</span>
                  </div>
                </div>

                {/* FIELD EVIDENCE */}
                <div style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: '0.06em',
                      color: 'var(--muted)',
                      textTransform: 'uppercase',
                      marginBottom: 4,
                    }}
                  >
                    FIELD EVIDENCE
                  </div>
                  <div
                    style={{
                      background: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '6px 10px',
                      fontSize: 11.5,
                      color: '#0f172a',
                      fontWeight: 500,
                    }}
                  >
                    {fieldEvidenceText}
                  </div>
                </div>

                {/* SPATIAL CONTEXT */}
                <div style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: '0.06em',
                      color: 'var(--muted)',
                      textTransform: 'uppercase',
                      marginBottom: 4,
                    }}
                  >
                    SPATIAL CONTEXT
                  </div>
                  <div
                    style={{
                      background: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '6px 10px',
                      fontSize: 11.5,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span style={{ color: 'var(--muted)' }}>Micro-Watershed:</span>
                      <strong style={{ color: 'var(--primary)' }}>{activeObs.MWS || activeMws || '—'}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span style={{ color: 'var(--muted)' }}>GIS ID:</span>
                      <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#475569' }}>
                        {activeObs.id || activeId || '—'}
                      </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <span style={{ color: 'var(--muted)' }}>LULC:</span>
                      <strong style={{ color: '#0f172a' }}>{lulcClass || '—'}</strong>
                    </div>
                  </div>
                </div>

                {/* WATERSHED ANALYTICS */}
                <div style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: '0.06em',
                      color: 'var(--muted)',
                      textTransform: 'uppercase',
                      marginBottom: 4,
                    }}
                  >
                    WATERSHED ANALYTICS
                  </div>
                  <div
                    style={{
                      background: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '6px 10px',
                      fontSize: 11.5,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span style={{ color: 'var(--muted)' }}>Risk:</span>
                      <strong
                        style={{
                          color:
                            riskCategory === 'CRITICAL'
                              ? '#dc2626'
                              : riskCategory === 'HIGH'
                              ? '#d97706'
                              : '#16a34a',
                        }}
                      >
                        {riskCategory} {riskScore !== null ? `(${riskScore})` : ''}
                      </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <span style={{ color: 'var(--muted)' }}>Primary Driver:</span>
                      <strong style={{ color: '#0f172a' }}>{primaryDriver}</strong>
                    </div>
                  </div>
                </div>

                {/* RECOMMENDED ACTION */}
                <div>
                  <div
                    style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: '0.06em',
                      color: '#15803d',
                      textTransform: 'uppercase',
                      marginBottom: 4,
                    }}
                  >
                    RECOMMENDED ACTION
                  </div>
                  <div
                    style={{
                      background: '#f0fdf4',
                      border: '1px solid #bbf7d0',
                      borderRadius: 6,
                      padding: '8px 10px',
                      fontSize: 11.5,
                      color: '#14532d',
                      lineHeight: 1.45,
                    }}
                  >
                    {recommendedAction ? (
                      <div style={{ fontWeight: 600 }}>{recommendedAction}</div>
                    ) : (
                      <span style={{ color: 'var(--muted)', fontStyle: 'italic', fontWeight: 400 }}>
                        No recommendation available for this observation.
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* View on GIS Action */}
              <div style={{ marginTop: 14 }}>
                {typeof activeObs.latitude === 'number' && typeof activeObs.longitude === 'number' ? (
                  <button
                    className="primary-button full"
                    onClick={() => onNavigateToGis && onNavigateToGis(activeObs)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      padding: '10px 16px',
                      fontWeight: 600,
                      width: '100%',
                    }}
                  >
                    <span>🗺️</span>
                    <span>{dict.mwsProfile.viewInGis}</span>
                  </button>
                ) : (
                  <div>
                    <button
                      className="outline-button full"
                      disabled
                      style={{
                        opacity: 0.6,
                        cursor: 'not-allowed',
                        padding: '10px 16px',
                        width: '100%',
                      }}
                    >
                      {dict.mwsProfile.viewInGis}
                    </button>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, textAlign: 'center' }}>
                      Spatial context unavailable — GPS coordinates not available.
                    </div>
                  </div>
                )}
              </div>
            </Panel>
          )}

          <Panel title="10-step pipeline audit" eyebrow="VERIFICATION WORKFLOW">
            <div className="activity-list">
              <div>
                <span>Step 1 · Ingest</span>
                <strong>Image Discovery & EXIF Reading (Metadata parsing)</strong>
              </div>
              <div>
                <span>Step 2 · Extract</span>
                <strong>GPS Coordinate Extraction (GPSLatitude & GPSLongitude tags)</strong>
              </div>
              <div>
                <span>Step 3 · Validate</span>
                <strong>DMS to Decimal Conversion & Range Verification (WGS84)</strong>
              </div>
              <div>
                <span>Step 4 · Boundary</span>
                <strong>Shiggaon Taluk Boundary-First Spatial Inclusion Check</strong>
              </div>
              <div>
                <span>Step 5 · Spatial Index</span>
                <strong>66-MWS STRtree Spatial Index Polygon Lookup</strong>
              </div>
              <div>
                <span>Step 6 · Identity</span>
                <strong>Canonical Watershed Join (`id` = key, `MWS` = display code)</strong>
              </div>
              <div>
                <span>Step 7 · LULC Sample</span>
                <strong>Sentinel-2 10m LULC Sampling & Neighborhood Class Purity</strong>
              </div>
              <div>
                <span>Step 8 · Translate</span>
                <strong>Teammate Status Translation (VALID, INSIDE, BOUNDARY_REVIEW)</strong>
              </div>
              <div>
                <span>Step 9 · Ledger</span>
                <strong>Deterministic SHA-256 Ledger ID Assignment (`IMG_0001`)</strong>
              </div>
              <div>
                <span>Step 10 · Flat-File</span>
                <strong>Flat-File Persistence (Photo_Master_Validated.csv, GPKG)</strong>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </>
  )
}

function ReportsExportsScreen({
  mode,
  setScreen,
  apiStatus,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  selectedProfile,
  onSelectMws,
}: {
  mode: Mode
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  selectedProfile: WatershedDetail | null
  onSelectMws: (mwsId: string) => void
}) {
  const { dict } = useLanguage()
  const [scope, setScope] = useState<'basin' | 'mws'>('basin')
  const [selectedMwsId, setSelectedMwsId] = useState<string>(
    selectedProfile?.id || (watersheds.length > 0 ? watersheds[0].id : 'g_mws.240575')
  )
  const [basinReport, setBasinReport] = useState<BasinReport | null>(null)
  const [basinReportStatus, setBasinReportStatus] = useState<DataStatus>('loading')
  const [mwsReport, setMwsReport] = useState<MwsReport | null>(null)
  const [mwsReportStatus, setMwsReportStatus] = useState<DataStatus>('loading')
  const [searchFilter, setSearchFilter] = useState('')

  // Sync with parent selectedProfile
  useEffect(() => {
    if (selectedProfile?.id) {
      setSelectedMwsId(selectedProfile.id)
    }
  }, [selectedProfile])

  // Load Basin Report
  useEffect(() => {
    let isMounted = true
    async function loadBasin() {
      setBasinReportStatus('loading')
      const res = await fetchBasinReport()
      if (isMounted) {
        if (res.status === 'available' && res.data) {
          setBasinReport(res.data)
          setBasinReportStatus('available')
        } else {
          setBasinReport(null)
          setBasinReportStatus('unavailable')
        }
      }
    }
    loadBasin()
    return () => {
      isMounted = false
    }
  }, [])

  // Load MWS Report
  useEffect(() => {
    if (!selectedMwsId) return
    let isMounted = true
    async function loadMws() {
      setMwsReportStatus('loading')
      const res = await fetchMwsReport(selectedMwsId)
      if (isMounted) {
        if (res.status === 'available' && res.data) {
          setMwsReport(res.data)
          setMwsReportStatus('available')
        } else {
          setMwsReport(null)
          setMwsReportStatus('unavailable')
        }
      }
    }
    loadMws()
    return () => {
      isMounted = false
    }
  }, [selectedMwsId])

  const isOffline = apiStatus === 'unavailable'
  const isLoading = (scope === 'basin' ? basinReportStatus : mwsReportStatus) === 'loading'

  const filteredWatersheds = watersheds.filter((w) => {
    const q = searchFilter.toLowerCase()
    return (
      (w.MWS ? w.MWS.toLowerCase().includes(q) : false) ||
      (w.id ? w.id.toLowerCase().includes(q) : false) ||
      (w.risk_category ? w.risk_category.toLowerCase().includes(q) : false)
    )
  })

  const downloadJson = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{dict.sidebar.workspaceLabel} · {dict.subscreens.reportsTitle}</span>
          <h1>{dict.subscreens.reportsTitle}</h1>
          <p>
            {dict.subscreens.reportsSubtitle}
          </p>
        </div>
        <div className="heading-actions">
          <div style={{ display: 'inline-flex', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
            <button
              onClick={() => setScope('basin')}
              style={{
                padding: '6px 14px',
                fontSize: 11,
                fontWeight: 700,
                background: scope === 'basin' ? 'var(--primary)' : '#fff',
                color: scope === 'basin' ? '#fff' : 'var(--primary)',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Basin Scope (66 MWS)
            </button>
            <button
              onClick={() => setScope('mws')}
              style={{
                padding: '6px 14px',
                fontSize: 11,
                fontWeight: 700,
                background: scope === 'mws' ? 'var(--primary)' : '#fff',
                color: scope === 'mws' ? '#fff' : 'var(--primary)',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              {dict.subscreens.individualMwsDossier}
            </button>
          </div>

          {scope === 'basin' ? (
            <>
              <a
                href={getBasinReportCsvUrl()}
                download="Shiggaon_Basin_Watershed_Report.csv"
                className="outline-button"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <span>⤓</span> {dict.subscreens.download66Csv}
              </a>
              {basinReport && (
                <button
                  className="outline-button"
                  onClick={() => downloadJson(basinReport, 'Shiggaon_Basin_Report.json')}
                >
                  {dict.subscreens.downloadBasinJson}
                </button>
              )}
            </>
          ) : (
            <>
              <a
                href={getMwsReportCsvUrl(selectedMwsId)}
                download={`MWS_${mwsReport?.MWS || selectedMwsId}_Report.csv`}
                className="outline-button"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <span>⤓</span> {dict.subscreens.downloadMwsTimeseries}
              </a>
              {mwsReport && (
                <button
                  className="outline-button"
                  onClick={() => downloadJson(mwsReport, `MWS_${mwsReport.MWS}_Report.json`)}
                >
                  {dict.subscreens.downloadMwsJson}
                </button>
              )}
            </>
          )}

          <button className="outline-button" onClick={() => window.print()}>
            {dict.subscreens.exportPrintableDossier}
          </button>
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            ← {dict.mwsProfile.backToDashboard}
          </button>
        </div>
      </div>

      {isOffline && (
        <div className="notice warning">
          <strong>{dict.dashboard.apiDisconnectedWarning}</strong> {dict.dashboard.apiDisconnectedWarningDesc}
        </div>
      )}

      {isLoading && (
        <div className="notice">
          <strong>{dict.common.loading}...</strong>
        </div>
      )}

      {/* Top 4 KPI Metric Cards */}
      <div className="metric-grid">
        {scope === 'basin' ? (
          <>
            <Metric
              label={dict.dashboard.monitoredAreaLabel}
              value={isOffline ? '—' : basinReport ? `${basinReport.total_mws} MWS` : '66 MWS'}
              unit={basinReport ? `${basinReport.total_area_km2} km²` : '627.5 km²'}
              trend={dict.dashboard.talukBasinExtent}
            />
            <Metric
              label={dict.dashboard.healthIndexLabel}
              sublabel={dict.dashboard.healthIndexSublabel}
              value={isOffline ? '—' : typeof basinReport?.basin_health_index === 'number' ? basinReport.basin_health_index.toFixed(1) : '50.0'}
              unit="/100"
              trend={typeof basinReport?.average_risk_score === 'number' ? `${dict.dashboard.basinAvgRiskText}: ${basinReport.average_risk_score.toFixed(1)}` : 'Authoritative Risk V4'}
              tone="amber"
            />
            <Metric
              label={`${dict.risk.high} / ${dict.risk.critical}`}
              value={
                isOffline
                  ? '—'
                  : basinReport
                  ? `${(basinReport.risk_distribution?.CRITICAL || 0) + (basinReport.risk_distribution?.HIGH || 0)} ${dict.dashboard.unitsWord}`
                  : `20 ${dict.dashboard.unitsWord}`
              }
              trend={dict.dashboard.priorityFieldActionsLabel}
              tone="red"
            />
            <Metric
              label={dict.dashboard.inputSourceLabel}
              value="6 Feeds"
              trend="GIS · M1 · M2 · WQ · IoT · Obs"
              tone="green"
            />
          </>
        ) : (
          <>
            <Metric
              label={dict.mwsProfile.eyebrow}
              value={mwsReport?.MWS || '—'}
              unit={typeof mwsReport?.area_km2 === 'number' ? `${mwsReport.area_km2} km²` : undefined}
              trend={`${dict.dashboard.colGisId}: ${mwsReport?.id || selectedMwsId}`}
            />
            <Metric
              label={dict.mwsProfile.finalRiskScoreLabel}
              value={typeof mwsReport?.risk?.risk_score === 'number' ? mwsReport.risk.risk_score.toFixed(1) : '—'}
              unit="/100"
              trend={`${dict.mwsProfile.riskCategoryStat}: ${getLocalizedRiskCategory(mwsReport?.risk?.risk_category || '—', dict)}`}
              tone={
                mwsReport?.risk?.risk_category === 'CRITICAL'
                  ? 'red'
                  : mwsReport?.risk?.risk_category === 'HIGH'
                  ? 'amber'
                  : 'green'
              }
            />
            <Metric
              label={dict.mwsProfile.healthIndexStat}
              value={
                typeof mwsReport?.risk?.health_index === 'number'
                  ? mwsReport.risk.health_index.toFixed(1)
                  : '—'
              }
              unit="/100"
              trend={`${dict.mwsProfile.primaryDriverStat}: ${getDriverDisplay(mwsReport?.risk?.primary_driver, dict).label}`}
              tone="amber"
            />
            <Metric
              label={dict.mwsProfile.dominantLulcMetricLabel}
              value={mwsReport?.lulc.dominant_class || '—'}
              trend={`${mwsReport?.lulc.agriculture_pct ?? 0}% ${dict.mwsProfile.lulcAgri} · ${mwsReport?.lulc.forest_pct ?? 0}% ${dict.mwsProfile.lulcForest}`}
              tone="green"
            />
          </>
        )}
      </div>

      {/* Honest Provenance Banner */}
      <div
        style={{
          background: '#fff',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '12px 18px',
          marginBottom: 18,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, fontWeight: 600 }}>
          <span style={{ color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Data Honesty & Provenance:
          </span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#e0f2fe', color: '#0369a1' }}>
            GIS: Authoritative GPKG (66 MWS)
          </span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#f3e8ff', color: '#6b21a8' }}>
            Model 2: Risk Engine V4
          </span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#fef3c7', color: '#92400e' }}>
            WQ: SIMULATION (Synthetic Simulator)
          </span>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              background: mode === 'live' ? '#dcfce7' : '#f1f5f9',
              color: mode === 'live' ? '#166534' : '#475569',
            }}
          >
            IoT: {mode === 'live' ? 'LIVE (Sensor Telemetry)' : 'Scenario / Offline'}
          </span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#f8fafc', border: '1px solid var(--border)', color: '#334155' }}>
            Field Obs: Geocoded Pipeline
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>
          Generated: {scope === 'basin' ? basinReport?.generated_at || '—' : mwsReport?.generated_at || '—'}
        </div>
      </div>

      {scope === 'basin' ? (
        <>
          {/* Basin Overview Layout */}
          <div className="detail-hero">
            <BasinMap
              variant="Reports & Exports"
              gisBoundaries={gisBoundaries}
              gisStatus={gisStatus}
              gisError={gisError}
              onSelectMws={(id) => {
                setSelectedMwsId(id)
                onSelectMws(id)
                setScope('mws')
              }}
            />
            <div className="detail-hud">
              <span className="hud-title">{dict.dashboard.basinOverviewTitle}</span>
              <div className="hud-metric">
                <span className="hud-label">{dict.dashboard.monitoredAreaLabel}</span>
                <span className="hud-value">{basinReport?.total_area_km2 ?? 627.5} km²</span>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.dashboard.riskDistTitle} (66 MWS)</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 4, marginTop: 4 }}>
                  <span style={{ fontSize: 11, color: '#ba1a1a', fontWeight: 600 }}>
                    {dict.risk.critical}: {basinReport?.risk_distribution?.CRITICAL ?? 5}
                  </span>
                  <span style={{ fontSize: 11, color: '#ed6c02', fontWeight: 600 }}>
                    {dict.risk.high}: {basinReport?.risk_distribution?.HIGH ?? 15}
                  </span>
                  <span style={{ fontSize: 11, color: '#c8961e', fontWeight: 600 }}>
                    {dict.risk.moderate}: {basinReport?.risk_distribution?.MODERATE ?? 17}
                  </span>
                  <span style={{ fontSize: 11, color: '#1b5e20', fontWeight: 600 }}>
                    {dict.risk.low}: {basinReport?.risk_distribution?.LOW ?? 29}
                  </span>
                </div>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.dashboard.primaryDriversTitle}</span>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                  {dict.risk.waterStress}: {basinReport?.primary_drivers?.['Water Stress'] ?? 38} · {dict.risk.mlAnomaly}: {basinReport?.primary_drivers?.['ML Anomaly'] ?? 20} · {dict.risk.ecosystemPressure}: {basinReport?.primary_drivers?.['Ecosystem Risk'] ?? 8}
                </div>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.sidebar.waterQuality} ({dict.header.simulation})</span>
                <span className="hud-value" style={{ fontSize: 16 }}>
                  Mean {basinReport?.water_quality_summary?.mean_wqi ?? 75.0} WQI · 66 {dict.dashboard.unitsWord}
                </span>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{mode === 'live' ? dict.subscreens.liveTelemetryStream : dict.sidebar.simScenario}</span>
                <span className="hud-value" style={{ fontSize: 14 }}>
                  {mode === 'live'
                    ? (basinReport?.live_iot_summary?.status === 'online' ? '1 Gateway Online' : dict.dashboard.waitingForTelemetryText)
                    : `${dict.header.simulation} / ${dict.common.offline}`}
                </span>
              </div>
              <button
                className="outline-button full"
                onClick={() => setScreen('GIS Explorer')}
              >
                {dict.dashboard.inspectGisExplorer} →
              </button>
            </div>
          </div>

          {/* 66-MWS Master Basin Table */}
          <div style={{ marginTop: 24 }}>
            <Panel
              title={dict.dashboard.triageDecisionMatrix}
              eyebrow={dict.dashboard.triageEyebrow}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <input
                  type="text"
                  placeholder={dict.common.searchPlaceholder}
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    fontSize: 12,
                    border: '1px solid var(--border)',
                    borderRadius: 4,
                    width: 320,
                  }}
                />
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {filteredWatersheds.length} / {watersheds.length} {dict.dashboard.unitsWord}
                </span>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)', fontSize: 11 }}>
                      <th style={{ padding: '8px 6px' }}>{dict.mwsProfile.eyebrow}</th>
                      <th style={{ padding: '8px 6px' }}>{dict.dashboard.colGisId}</th>
                      <th style={{ padding: '8px 6px' }}>Area (km²)</th>
                      <th style={{ padding: '8px 6px' }}>{dict.dashboard.colHealth}</th>
                      <th style={{ padding: '8px 6px' }}>{dict.dashboard.colStatus}</th>
                      <th style={{ padding: '8px 6px' }}>{dict.dashboard.primaryDriversTitle}</th>
                      <th style={{ padding: '8px 6px' }}>{dict.dashboard.healthIndexLabel}</th>
                      <th style={{ padding: '8px 6px' }}>Priority</th>
                      <th style={{ padding: '8px 6px' }}>Stream Len</th>
                      <th style={{ padding: '8px 6px' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredWatersheds.map((w) => {
                      const isSelected = selectedMwsId === w.id
                      return (
                        <tr
                          key={w.id}
                          style={{
                            borderBottom: '1px solid var(--border)',
                            background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                          }}
                        >
                          <td style={{ padding: '8px 6px', fontWeight: 600 }}>{w.MWS}</td>
                          <td style={{ padding: '8px 6px', fontFamily: 'monospace', fontSize: 11, color: 'var(--muted)' }}>
                            {w.id}
                          </td>
                          <td style={{ padding: '8px 6px' }}>{typeof w.area_km2 === 'number' ? w.area_km2.toFixed(2) : '—'}</td>
                          <td style={{ padding: '8px 6px', fontWeight: 600 }}>
                            {typeof w.final_risk_score === 'number'
                              ? w.final_risk_score.toFixed(1)
                              : typeof w.risk_score === 'number'
                              ? w.risk_score.toFixed(1)
                              : '—'}
                          </td>
                          <td style={{ padding: '8px 6px' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '2px 6px',
                                borderRadius: 4,
                                fontSize: 10,
                                fontWeight: 700,
                                background:
                                  w.risk_category === 'CRITICAL'
                                    ? '#ffebee'
                                    : w.risk_category === 'HIGH'
                                    ? '#fff3e0'
                                    : w.risk_category === 'MODERATE'
                                    ? '#fffde7'
                                    : '#e8f5e9',
                                color:
                                  w.risk_category === 'CRITICAL'
                                    ? '#c62828'
                                    : w.risk_category === 'HIGH'
                                    ? '#e65100'
                                    : w.risk_category === 'MODERATE'
                                    ? '#f57f17'
                                    : '#1b5e20',
                              }}
                            >
                              {getLocalizedRiskCategory(w.risk_category || '—', dict)}
                            </span>
                          </td>
                          <td style={{ padding: '8px 6px' }}>{getDriverDisplay(w.primary_driver, dict).label || '—'}</td>
                          <td style={{ padding: '8px 6px' }}>
                            {typeof w.health_index === 'number' ? w.health_index.toFixed(1) : '—'}
                          </td>
                          <td style={{ padding: '8px 6px' }}>{w.intervention_priority || '—'}</td>
                          <td style={{ padding: '8px 6px' }}>
                            {typeof w.stream_len_km === 'number' ? `${w.stream_len_km.toFixed(2)} km` : '—'}
                          </td>
                          <td style={{ padding: '8px 6px' }}>
                            <button
                              onClick={() => {
                                setSelectedMwsId(w.id)
                                onSelectMws(w.id)
                                setScope('mws')
                              }}
                              style={{
                                padding: '3px 8px',
                                fontSize: 11,
                                fontWeight: 600,
                                borderRadius: 4,
                                border: '1px solid var(--border)',
                                background: '#fff',
                                cursor: 'pointer',
                              }}
                            >
                              {dict.dashboard.triageInspectDossier} →
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        </>
      ) : (
        <>
          {/* Single MWS Dossier View */}
          <div style={{ marginBottom: 18, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{dict.mwsProfile.eyebrow}:</span>
            <select
              value={selectedMwsId}
              onChange={(e) => {
                setSelectedMwsId(e.target.value)
                onSelectMws(e.target.value)
              }}
              style={{
                padding: '6px 12px',
                fontSize: 12,
                borderRadius: 4,
                border: '1px solid var(--border)',
                background: '#fff',
                minWidth: 260,
              }}
            >
              {watersheds.map((w) => {
                const score =
                  typeof w.final_risk_score === 'number'
                    ? w.final_risk_score
                    : typeof w.risk_score === 'number'
                    ? w.risk_score
                    : null
                return (
                  <option key={w.id} value={w.id}>
                    {w.MWS} ({w.id}) — {getLocalizedRiskCategory(w.risk_category || '—', dict)} ({typeof score === 'number' ? score.toFixed(1) : '—'})
                  </option>
                )
              })}
            </select>
          </div>

          <div className="detail-hero">
            <BasinMap
              variant="Reports & Exports"
              selectedMws={mwsReport?.MWS}
              selectedId={mwsReport?.id}
              gisBoundaries={gisBoundaries}
              gisStatus={gisStatus}
              gisError={gisError}
              onSelectMws={(id) => {
                setSelectedMwsId(id)
                onSelectMws(id)
              }}
            />
            <div className="detail-hud">
              <span className="hud-title">{dict.subscreens.individualMwsDossier}</span>
              <div className="hud-metric">
                <span className="hud-label">{dict.mwsProfile.eyebrow}</span>
                <span className="hud-value" style={{ fontSize: 20 }}>
                  {mwsReport?.MWS ?? '—'} <span style={{ fontSize: 12, color: 'var(--muted)' }}>({dict.dashboard.colGisId}: {mwsReport?.id ?? selectedMwsId})</span>
                </span>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.mwsProfile.morphometryTitle}</span>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  {dict.mwsProfile.catchmentAreaLabel}: <strong>{mwsReport?.area_km2 ?? '—'} km²</strong> · {dict.mwsProfile.streamLength}: <strong>{mwsReport?.stream_len_km ?? '—'} km</strong> · {dict.mwsProfile.drainageDensity}: <strong>{mwsReport?.drainage_density ?? '—'} km/km²</strong>
                </div>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.mwsProfile.riskDecompositionTitle}</span>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  {dict.mwsProfile.finalRiskScoreLabel}: <strong>{typeof mwsReport?.risk?.risk_score === 'number' ? mwsReport.risk.risk_score.toFixed(1) : '—'} / 100</strong> ({getLocalizedRiskCategory(mwsReport?.risk?.risk_category ?? '—', dict)})
                  <br />
                  {dict.mwsProfile.primaryDriverHeroLabel}: <strong>{getDriverDisplay(mwsReport?.risk?.primary_driver, dict).label ?? '—'}</strong>
                </div>
              </div>
              <div className="hud-metric">
                <span className="hud-label">{dict.sidebar.waterQuality} ({dict.header.simulation})</span>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  WQI: <strong>{mwsReport?.water_quality.wqi != null ? `${mwsReport.water_quality.wqi} WQI` : '—'}</strong> ({mwsReport?.water_quality.quality_category ?? '—'})
                </div>
              </div>
              <button
                className="outline-button full"
                onClick={() => setScreen('Micro-Watershed Profile')}
              >
                {dict.mwsProfile.profileTitle} →
              </button>
            </div>
          </div>

          {/* Multi-Panel Dossier Columns */}
          <div className="detail-columns" style={{ marginTop: 24 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <Panel title={dict.mwsProfile.actionLinkageTitle} eyebrow="MODEL 2 INTERVENTIONS">
                <div className="activity-list">
                  <div>
                    <span>Priority</span>
                    <strong style={{ color: 'var(--primary)', fontWeight: 700 }}>
                      {mwsReport?.interventions.intervention_priority || 'STANDARD'}
                    </strong>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.actionPrimaryBadge}</span>
                    <strong>{mwsReport?.interventions.primary_intervention || 'Catchment conservation'}</strong>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.actionSecondaryBadge}</span>
                    <span>{mwsReport?.interventions.secondary_intervention || 'Contour bunding'}</span>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.actionLongTermBadge}</span>
                    <span>{mwsReport?.interventions.long_term_intervention || 'Riparian buffer restoration'}</span>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.actionMonitoringBadge}</span>
                    <span>{mwsReport?.interventions.monitoring_focus || 'Precipitation and soil runoff'}</span>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.actionMonitoringSensors}</span>
                    <span>{mwsReport?.interventions.iot_sensors || 'Rainfall and soil moisture'}</span>
                  </div>
                </div>
              </Panel>

              <Panel title={dict.mwsProfile.lulcCompositionTitle} eyebrow="MODEL 1 SENTINEL-2 10M">
                <div className="provenance">
                  <div>
                    <span>{dict.mwsProfile.dominantLulcMetricLabel.toUpperCase()}</span>
                    <strong>{mwsReport?.lulc.dominant_class || 'Agriculture'}</strong>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.lulcCompositionEyebrow}</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4, fontSize: 11 }}>
                      <div>{dict.mwsProfile.lulcAgri}: <strong>{mwsReport?.lulc.agriculture_pct ?? 0}%</strong></div>
                      <div>{dict.mwsProfile.lulcForest}: <strong>{mwsReport?.lulc.forest_pct ?? 0}%</strong></div>
                      <div>{dict.mwsProfile.lulcWater}: <strong>{mwsReport?.lulc.water_pct ?? 0}%</strong></div>
                      <div>{dict.mwsProfile.lulcBuiltup}: <strong>{mwsReport?.lulc.builtup_pct ?? 0}%</strong></div>
                      <div>{dict.mwsProfile.lulcBarren}: <strong>{mwsReport?.lulc.barren_pct ?? 0}%</strong></div>
                    </div>
                  </div>
                  <div>
                    <span>{dict.mwsProfile.coverageLabel.toUpperCase()}</span>
                    <strong>{mwsReport?.lulc.lulc_coverage || 'GOOD'}</strong>
                  </div>
                  {mwsReport?.lulc?.lulc_coverage === 'LOW' && (
                    <div
                      style={{
                        padding: '6px 10px',
                        borderRadius: 4,
                        background: '#fff8ec',
                        border: '1px solid #edc58e',
                        color: '#774a0e',
                        fontSize: 11,
                        marginTop: 8,
                      }}
                    >
                      ⚠ {dict.mwsProfile.lulcLowRasterWarning}
                    </div>
                  )}
                </div>
              </Panel>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <Panel title={dict.subscreens.wqTitle} eyebrow="WATER QUALITY [SIMULATION]">
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 4,
                    background: '#fef3c7',
                    border: '1px solid #fde68a',
                    color: '#92400e',
                    fontSize: 11,
                    fontWeight: 600,
                    marginBottom: 12,
                  }}
                >
                  ⚠ {dict.subscreens.wqSimulationNotice}
                </div>
                <div className="activity-list">
                  <div>
                    <span>WQI Score</span>
                    <strong>{mwsReport?.water_quality.wqi != null ? `${mwsReport.water_quality.wqi} WQI` : '—'} ({mwsReport?.water_quality.quality_category ?? '—'})</strong>
                  </div>
                  <div>
                    <span>pH Value</span>
                    <span>{mwsReport?.water_quality.ph ?? '—'} (Ideal: 6.5 - 8.5)</span>
                  </div>
                  <div>
                    <span>Total Dissolved Solids (TDS)</span>
                    <span>{mwsReport?.water_quality.tds ?? '—'} mg/L</span>
                  </div>
                  <div>
                    <span>Turbidity</span>
                    <span>{mwsReport?.water_quality.turbidity ?? '—'} NTU</span>
                  </div>
                  <div>
                    <span>Water Temperature</span>
                    <span>{mwsReport?.water_quality.temperature ?? '—'} °C</span>
                  </div>
                </div>
              </Panel>

              <Panel title={`${dict.subscreens.liveTelemetryStream} & ${dict.subscreens.fieldObsTitle}`} eyebrow="GROUND-TRUTH & SENSORS">
                <div style={{ marginBottom: 14 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>
                    {mode === 'live' ? `${dict.subscreens.liveTelemetryStream}:` : `${dict.sidebar.simScenario}:`}
                  </span>
                  {mode === 'live' && mwsReport?.live_iot.available ? (
                    <div style={{ marginTop: 6, padding: '10px 12px', background: '#ecfdf5', borderRadius: 4, border: '1px solid #a7f3d0' }}>
                      <strong style={{ color: '#065f46', fontSize: 12 }}>● {dict.subscreens.liveTelemetryStream.toUpperCase()}</strong>
                      <div style={{ fontSize: 11, marginTop: 4, color: '#047857' }}>
                        Rainfall: {mwsReport.live_iot.rainfall_mm ?? '—'} mm · Moisture: {mwsReport.live_iot.soil_moisture_pct ?? '—'}% · Alert: {mwsReport.live_iot.compound_alert_level ?? 'NORMAL'}
                      </div>
                    </div>
                  ) : mode === 'live' ? (
                    <div
                      style={{
                        marginTop: 6,
                        padding: '10px 12px',
                        background: '#f8fafc',
                        borderRadius: 4,
                        border: '1px solid var(--border)',
                        color: 'var(--muted)',
                        fontSize: 11,
                      }}
                    >
                      🔒 <strong>{dict.common.noData}.</strong> {dict.dashboard.waitingForLiveTelemetryDesc}
                    </div>
                  ) : (
                    <div
                      style={{
                        marginTop: 6,
                        padding: '10px 12px',
                        background: '#f8fafc',
                        borderRadius: 4,
                        border: '1px solid var(--border)',
                        color: 'var(--muted)',
                        fontSize: 11,
                      }}
                    >
                      🔒 <strong>{dict.sidebar.simScenario}.</strong> {dict.sidebar.simScenarioDesc}
                    </div>
                  )}
                </div>

                <div>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>
                    {dict.subscreens.fieldObsTitle}:
                  </span>
                  {mwsReport && mwsReport.field_evidence.count > 0 ? (
                    <div style={{ marginTop: 6, padding: '10px 12px', background: '#eff6ff', borderRadius: 4, border: '1px solid #bfdbfe' }}>
                      <strong style={{ color: '#1e40af', fontSize: 12 }}>
                        {mwsReport.field_evidence.count} {dict.subscreens.fieldObsTitle}
                      </strong>
                    </div>
                  ) : (
                    <div
                      style={{
                        marginTop: 6,
                        padding: '10px 12px',
                        background: '#f8fafc',
                        borderRadius: 4,
                        border: '1px solid var(--border)',
                        color: 'var(--muted)',
                        fontSize: 11,
                      }}
                    >
                      🔒 <strong>{dict.common.noData}.</strong>
                    </div>
                  )}
                </div>
              </Panel>
            </div>
          </div>
        </>
      )}
    </>
  )
}

export default function Page() {
  const { dict } = useLanguage()
  const [mode, setMode] = useState<Mode>('live')
  const [mws, setMws] = useState('ALL')
  const [screen, setScreen] = useState<Screen>('Dashboard')
  const [lang, setLang] = useState<Language>('en')

  // API State
  const [apiStatus, setApiStatus] = useState<DataStatus>('loading')
  const [profileStatus, setProfileStatus] = useState<DataStatus>('available')
  const [wqStatus, setWqStatus] = useState<DataStatus>('loading')
  const [watersheds, setWatersheds] = useState<WatershedSummary[]>([])
  const [basinSummary, setBasinSummary] = useState<BasinSummary | null>(null)
  const [lulcSummary, setLulcSummary] = useState<LulcBasinSummary | null>(null)
  const [wqSummary, setWqSummary] = useState<WaterQualitySummary | null>(null)
  const [wqRecord, setWqRecord] = useState<WaterQualityRecord | null>(null)
  const [cropAdvisory, setCropAdvisory] = useState<WatershedCropAdvisory | null>(null)
  const [cropStatus, setCropStatus] = useState<DataStatus>('loading')
  const [selectedProfile, setSelectedProfile] = useState<WatershedDetail | null>(null)
  const [liveTelemetry, setLiveTelemetry] = useState<LiveRiskResult | null>(null)
  const [fieldObservations, setFieldObservations] = useState<EvidenceItem[]>([])
  const [fieldObsStatus, setFieldObsStatus] = useState<DataStatus>('loading')

  // GIS State
  const [gisBoundaries, setGisBoundaries] = useState<MwsGeoJsonCollection | null>(null)
  const [gisStatus, setGisStatus] = useState<DataStatus>('loading')
  const [gisError, setGisError] = useState<string | null>(null)

  // Fetch initial data on mount
  useEffect(() => {
    let isMounted = true

    async function loadData() {
      setApiStatus('loading')
      setGisStatus('loading')
      setWqStatus('loading')
      setFieldObsStatus('loading')
      const [wRes, bRes, gRes, lRes, qRes, fRes] = await Promise.all([
        fetchWatersheds(),
        fetchBasinSummary(),
        fetchMwsBoundariesGeoJson(),
        fetchLulcSummary(),
        fetchWaterQualitySummary(),
        fetchFieldObservations(),
      ])

      if (!isMounted) return

      if (wRes.status === 'available' && wRes.data) {
        setWatersheds(wRes.data)
        setApiStatus('available')
      } else {
        setApiStatus('unavailable')
      }

      if (bRes.status === 'available' && bRes.data) {
        setBasinSummary(bRes.data)
      }

      if (lRes.status === 'available' && lRes.data) {
        setLulcSummary(lRes.data)
      }

      if (qRes.status === 'available' && qRes.data) {
        setWqSummary(qRes.data)
        setWqStatus('available')
      } else {
        setWqStatus('unavailable')
      }

      if (fRes.status === 'available' && fRes.data) {
        setFieldObservations(fRes.data)
        setFieldObsStatus('available')
      } else if (fRes.status === 'unavailable') {
        setFieldObservations([])
        setFieldObsStatus('unavailable')
      } else {
        setFieldObservations([])
        setFieldObsStatus('available')
      }

      if (gRes.status === 'available' && gRes.data) {
        setGisBoundaries(gRes.data)
        setGisStatus('available')
      } else {
        setGisBoundaries(null)
        setGisStatus('unavailable')
        setGisError(gRes.error || 'GIS boundaries unavailable')
      }
    }

    loadData()
    return () => {
      isMounted = false
    }
  }, [])

  // When a specific watershed is selected
  useEffect(() => {
    let isMounted = true
    if (mws === 'ALL' || !mws) {
      setSelectedProfile(null)
      setProfileStatus('available')
      setWqRecord(null)
      setCropAdvisory(null)
      setCropStatus('available')
      return
    }

    async function loadProfileAndWq() {
      setProfileStatus('loading')
      setWqStatus('loading')
      setCropStatus('loading')
      const [pRes, qRes, cRes] = await Promise.all([
        fetchWatershedProfile(mws),
        fetchWaterQualityMws(mws, mode),
        fetchCropAdvisory(mws),
      ])
      if (!isMounted) return
      if (pRes.status === 'available' && pRes.data) {
        setSelectedProfile(pRes.data)
        setProfileStatus('available')
      } else {
        setSelectedProfile(null)
        setProfileStatus('unavailable')
      }
      if (qRes.status === 'available' && qRes.data) {
        setWqRecord(qRes.data)
        setWqStatus('available')
      } else {
        setWqRecord(null)
        setWqStatus('unavailable')
      }
      if (cRes.status === 'available' && cRes.data) {
        setCropAdvisory(cRes.data)
        setCropStatus('available')
      } else {
        setCropAdvisory(null)
        setCropStatus('unavailable')
      }
    }
    loadProfileAndWq()
    return () => {
      isMounted = false
    }
  }, [mws, mode])

  // When switching to Micro-Watershed Profile, Water Quality, or Crop Intelligence, ensure an MWS is selected
  useEffect(() => {
    if (
      (screen === 'Micro-Watershed Profile' || screen === 'Water Quality' || screen === 'Crop Intelligence') &&
      (mws === 'ALL' || !mws) &&
      watersheds.length > 0
    ) {
      setMws(watersheds[0].id)
    }
  }, [screen, mws, watersheds])

  // Live IoT telemetry polling when mode === 'live' (polling every 1.5s for fast auto-updating)
  useEffect(() => {
    if (mode !== 'live') return

    let isMounted = true
    async function pollTelemetry() {
      const res = await fetchLatestTelemetry(mws && mws !== 'ALL' ? mws : undefined)
      if (isMounted) {
        if (res.status === 'available' && res.data) {
          setLiveTelemetry(res.data)
        } else if (res.status === 'unavailable' || res.status === 'no_data') {
          // If offline or no data, mark device stale or null
          setLiveTelemetry((prev) => {
            if (prev) {
              return { ...prev, is_stale: true, connection_status: 'OFFLINE / NO DATA' }
            }
            return null
          })
        }
      }
      // Keep water quality record synchronized with live ESP32 sensors
      if (mws && mws !== 'ALL') {
        const wqRes = await fetchWaterQualityMws(mws, 'live')
        if (isMounted && wqRes.status === 'available' && wqRes.data) {
          setWqRecord(wqRes.data)
        }
      }
    }

    pollTelemetry()
    const interval = setInterval(pollTelemetry, 1500)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [mode, mws])

  const handleSelectMws = (val: string) => {
    const match = watersheds.find((w) => w.id === val || w.MWS === val)
    setMws(match ? match.id : val)
  }

  const [observationMarker, setObservationMarker] = useState<ObservationMarkerData | null>(null)

  const handleViewOnGis = (obs: EvidenceItem) => {
    if (obs.id) handleSelectMws(obs.id)
    else if (obs.MWS) handleSelectMws(obs.MWS)
    if (typeof obs.latitude === 'number' && typeof obs.longitude === 'number') {
      setObservationMarker({
        latitude: obs.latitude,
        longitude: obs.longitude,
        MWS: obs.MWS,
        id: obs.id,
        filename: obs.filename,
        lulc_class: obs.lulc_class,
      })
    }
    setScreen('GIS Explorer')
  }

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [screen])

  return (
    <div className="app-shell">
      <Header
        mode={mode}
        setMode={setMode}
        screen={screen}
        setScreen={setScreen}
        mws={mws}
        setMws={setMws}
        watersheds={watersheds}
        apiStatus={apiStatus}
        lang={lang}
        setLang={setLang}
      />
      <Sidebar mode={mode} screen={screen} setScreen={setScreen} apiStatus={apiStatus} lang={lang} />
      <main className="main-content">
        {screen === 'Dashboard' ? (
          <Dashboard
            mode={mode}
            setScreen={setScreen}
            basin={basinSummary}
            watersheds={watersheds}
            selectedProfile={selectedProfile}
            liveTelemetry={liveTelemetry}
            apiStatus={apiStatus}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            onSelectMws={handleSelectMws}
          />
        ) : screen === 'Micro-Watershed Profile' ? (
          <MicroWatershedProfile
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            profileStatus={profileStatus}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
            basin={basinSummary}
            cropAdvisory={cropAdvisory}
            cropStatus={cropStatus}
          />
        ) : screen === 'Crop Intelligence' ? (
          <CropIntelligenceScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            cropAdvisory={cropAdvisory}
            cropStatus={cropStatus}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
            basin={basinSummary}
            lang={lang}
          />
        ) : screen === 'LULC Analysis' ? (
          <LulcAnalysisScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            lulcSummary={lulcSummary}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
          />
        ) : screen === 'Water Quality' ? (
          <WaterQualityScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            wqSummary={wqSummary}
            wqRecord={wqRecord}
            wqStatus={wqStatus}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
          />
        ) : screen === 'IoT Network' ? (
          <IotNetworkScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            liveTelemetry={liveTelemetry}
            setLiveTelemetry={setLiveTelemetry}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
          />
        ) : screen === 'Field Observations' ? (
          <FieldObservationsScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            observations={fieldObservations}
            obsStatus={fieldObsStatus}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            onSelectMws={handleSelectMws}
            onObservationsUpdated={(newObs) => setFieldObservations(newObs)}
            onNavigateToGis={handleViewOnGis}
          />
        ) : screen === 'Reports & Exports' ? (
          <ReportsExportsScreen
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            watersheds={watersheds}
            selectedProfile={selectedProfile}
            onSelectMws={handleSelectMws}
          />
        ) : (
          <DetailScreen
            screen={screen}
            mode={mode}
            setScreen={setScreen}
            apiStatus={apiStatus}
            selectedProfile={selectedProfile}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            onSelectMws={handleSelectMws}
            liveTelemetry={liveTelemetry}
            observationMarker={observationMarker}
            onClearObservationMarker={() => setObservationMarker(null)}
            cropAdvisory={cropAdvisory}
            cropStatus={cropStatus}
          />
        )}
        <footer>
          <span>{dict.common.footerTitle}</span>
          <span>
            {dict.common.footerDataMode}: {mode === 'live' ? dict.header.liveIot : dict.header.simulation} · {dict.common.footerApi}: {apiStatus} · v2.8.1
          </span>
        </footer>
      </main>
    </div>
  )
}

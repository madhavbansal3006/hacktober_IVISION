'use client'

import React from 'react'
import {
  WatershedCropAdvisory,
  WatershedDetail,
  WatershedSummary,
  BasinSummary,
  MwsGeoJsonCollection,
  DataStatus,
  Screen,
} from '../lib/types'
import { CropSuggestions } from './CropSuggestions'
import { GisMap } from './GisMap'
import { Language, translations } from '../lib/translations'

interface CropIntelligenceScreenProps {
  mode: 'simulation' | 'live'
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  cropAdvisory: WatershedCropAdvisory | null
  cropStatus: DataStatus
  selectedProfile: WatershedDetail | null
  gisBoundaries: MwsGeoJsonCollection | null
  gisStatus: DataStatus
  gisError: string | null
  watersheds: WatershedSummary[]
  onSelectMws: (mwsId: string) => void
  basin?: BasinSummary | null
  lang?: Language
}

export function CropIntelligenceScreen({
  mode,
  setScreen,
  apiStatus,
  cropAdvisory,
  cropStatus,
  selectedProfile,
  gisBoundaries,
  gisStatus,
  gisError,
  watersheds,
  onSelectMws,
  lang = 'en',
}: CropIntelligenceScreenProps) {
  const t = translations[lang]
  const isOffline = apiStatus === 'unavailable' || cropStatus === 'unavailable'
  const isLoading = cropStatus === 'loading'

  const water = cropAdvisory?.water_summary
  const topCrop = cropAdvisory?.recommended_crops?.[0]
  const cautionCount = cropAdvisory?.caution_crops?.length ?? 0

  return (
    <>
      {/* Header */}
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            AGRO-HYDROLOGICAL DECISION SUPPORT / SHIGGAON BASIN
          </span>
          <h1>
            {selectedProfile
              ? `Crop Intelligence · Micro-Watershed ${selectedProfile.MWS}`
              : 'Catchment Crop Intelligence'}
          </h1>
          <p>
            {selectedProfile
              ? `Water-optimized crop recommendations and drought mitigation prescriptions for ${selectedProfile.MWS} (${selectedProfile.id}).`
              : 'Select any micro-watershed to view tailored crop suitability based on moisture, rainfall, salinity, and slope.'}
          </p>
        </div>
        <div className="heading-actions">
          <button className="outline-button" onClick={() => setScreen('GIS Explorer')}>
            View on Map ↗
          </button>
          <button
            className="outline-button"
            onClick={() => setScreen('Micro-Watershed Profile')}
          >
            Catchment Profile →
          </button>
          <button className="outline-button" onClick={() => setScreen('Dashboard')}>
            ← Back to Dashboard
          </button>
        </div>
      </div>

      {/* Offline Alert */}
      {isOffline && (
        <div className="notice warning">
          <strong>Backend API Disconnected.</strong> Connect backend on localhost:8000 to load real crop suitability models.
        </div>
      )}

      {/* Watershed Quick Selection Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 10,
          background: 'var(--surface-low)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '10px 16px',
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.08em' }}>
            SELECT CATCHMENT:
          </span>
          <select
            value={selectedProfile?.id || ''}
            onChange={(e) => onSelectMws(e.target.value)}
            style={{
              padding: '6px 10px',
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: '#fff',
              fontSize: 12,
              fontWeight: 600,
              minWidth: 220,
            }}
          >
            {watersheds.map((w) => (
              <option key={w.id} value={w.id}>
                {w.MWS} ({w.id}) — {w.dominant_class || 'Agri'} · Risk: {w.final_risk_score ?? '—'}
              </option>
            ))}
          </select>

          {/* Quick chip for Golden Catchment */}
          <button
            onClick={() => onSelectMws('g_mws.240575')}
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              padding: '5px 10px',
              borderRadius: 4,
              background: selectedProfile?.MWS === '4D4F2m3' ? 'var(--primary)' : '#fff',
              color: selectedProfile?.MWS === '4D4F2m3' ? '#fff' : 'var(--primary)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
          >
            ★ Golden Catchment (4D4F2m3)
          </button>
        </div>

        <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
          {selectedProfile
            ? `GIS ID: ${selectedProfile.id} | Area: ${selectedProfile.area_km2 ?? '—'} km²`
            : '66 Micro-Watersheds Monitored'}
        </div>
      </div>

      {/* Top 4 Summary Cards */}
      <div className="metric-grid">
        <div className="metric">
          <span className="metric-label">TOP RECOMMENDED CROP</span>
          <div className="metric-value" style={{ fontSize: 20, fontWeight: 800 }}>
            {isOffline || !topCrop ? '—' : topCrop.crop_name.split('(')[0].trim()}
          </div>
          <span className="trend green">
            {isOffline || !topCrop ? '' : `${topCrop.suitability_score.toFixed(1)}% Match · ${topCrop.suitability_tier}`}
          </span>
        </div>

        <div className="metric">
          <span className="metric-label">CATCHMENT WATER STRESS</span>
          <div
            className="metric-value"
            style={{
              color:
                (water?.water_stress_score ?? 0) > 55
                  ? 'var(--red)'
                  : (water?.water_stress_score ?? 0) > 40
                  ? 'var(--amber)'
                  : 'var(--primary)',
            }}
          >
            {isOffline || !water ? '—' : `${water.water_stress_score.toFixed(1)}`}
            <small>/100</small>
          </div>
          <span
            className={`trend ${
              (water?.water_stress_score ?? 0) > 55
                ? 'red'
                : (water?.water_stress_score ?? 0) > 40
                ? 'amber'
                : 'green'
            }`}
          >
            {water ? `${water.water_stress_level} DEFICIT REGIME` : 'Model 2 Calibrated'}
          </span>
        </div>

        <div className="metric">
          <span className="metric-label">IRRIGATION WATER QUALITY</span>
          <div className="metric-value" style={{ fontSize: 22, color: 'var(--secondary)' }}>
            {isOffline || !water?.wqi ? '—' : `${water.wqi.toFixed(1)} WQI`}
          </div>
          <span className="trend">
            {water?.tds_mg_l ? `${Math.round(water.tds_mg_l)} mg/L TDS · pH ${water.ph?.toFixed(1)}` : 'Simulated standard'}
          </span>
        </div>

        <div className="metric">
          <span className="metric-label">RESTRICTED / HIGH-RISK CROPS</span>
          <div className="metric-value" style={{ color: cautionCount > 0 ? 'var(--red)' : 'var(--primary)' }}>
            {isOffline ? '—' : `${cautionCount}`}
          </div>
          <span className="trend red">
            {cautionCount > 0 ? 'Aquifer Depletion Warning' : 'Safe for Cultivation'}
          </span>
        </div>
      </div>

      {/* Catchment Hero: Map + Water Context */}
      <div className="detail-hero" style={{ marginBottom: 18 }}>
        <div style={{ height: 320, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
          <GisMap
            variant="Micro-Watershed Profile"
            selectedMws={selectedProfile?.MWS}
            selectedId={selectedProfile?.id}
            gisBoundaries={gisBoundaries}
            gisStatus={gisStatus}
            gisError={gisError}
            onSelectMws={onSelectMws}
            height={320}
          />
        </div>

        <div className="detail-summary" style={{ borderRadius: 6 }}>
          <span className="eyebrow">
            {selectedProfile ? `HYDROLOGICAL CONTEXT · ${selectedProfile.MWS}` : 'SELECT A WATERSHED'}
          </span>
          <h2>
            {selectedProfile
              ? `Micro-Watershed ${selectedProfile.MWS} Water Regime`
              : 'Select a Micro-Watershed'}
          </h2>
          <p>
            {selectedProfile
              ? `Catchment ${selectedProfile.MWS} encompasses ${selectedProfile.area_km2 ?? '—'} km² in Shiggaon Taluk. Dominant land cover is ${selectedProfile.lulc?.dominant_class || 'Agriculture'}. Mean elevation is ${selectedProfile.elevation_mean ?? '—'}m with an average slope of ${selectedProfile.slope_mean ?? '—'}°.`
              : 'Click any catchment polygon on the map or choose from the dropdown to inspect tailored crop recommendations.'}
          </p>

          <div className="summary-stats">
            <div className="metric" style={{ background: 'transparent', border: 0, padding: 0 }}>
              <span className="metric-label" style={{ color: '#a9e2a0' }}>WATER STRESS</span>
              <div className="metric-value" style={{ color: '#fff', fontSize: 20 }}>
                {water?.water_stress_score ? `${water.water_stress_score.toFixed(1)}/100` : '—'}
              </div>
            </div>

            <div className="metric" style={{ background: 'transparent', border: 0, padding: 0 }}>
              <span className="metric-label" style={{ color: '#a9e2a0' }}>FLOOD RISK</span>
              <div className="metric-value" style={{ color: '#fff', fontSize: 20 }}>
                {water?.flood_risk_score ? `${water.flood_risk_score.toFixed(1)}/100` : '—'}
              </div>
            </div>

            <div className="metric" style={{ background: 'transparent', border: 0, padding: 0 }}>
              <span className="metric-label" style={{ color: '#a9e2a0' }}>TOP CROP</span>
              <div className="metric-value" style={{ color: '#fff', fontSize: 18 }}>
                {topCrop ? topCrop.crop_name.split('(')[0].trim() : '—'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Crop Suggestions Container */}
      <div className="panel" style={{ borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <div className="panel-head" style={{ marginBottom: 14 }}>
          <div>
            <span className="eyebrow">DECISION SUPPORT ENGINE</span>
            <h2 style={{ fontSize: 18, fontWeight: 800 }}>
              Calibrated Crop Recommendations & Irrigation Strategy
            </h2>
          </div>
          <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>
            Northern Transition Zone (Zone 8) · Haveri District
          </span>
        </div>

        <CropSuggestions
          advisory={cropAdvisory}
          status={cropStatus}
          mwsCode={selectedProfile?.MWS}
          mwsId={selectedProfile?.id}
          lang={lang}
        />
      </div>
    </>
  )
}

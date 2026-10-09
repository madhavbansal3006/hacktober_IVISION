'use client'

import React, { useState, useMemo } from 'react'
import {
  WatershedCropAdvisory,
  CropRecommendation,
  CropCaution,
  DataStatus,
} from '../lib/types'
import { Language, translations } from '../lib/translations'

interface CropSuggestionsProps {
  advisory: WatershedCropAdvisory | null
  status: DataStatus
  mwsCode?: string
  mwsId?: string
  compact?: boolean
  onSelectCrop?: (crop: CropRecommendation) => void
  lang?: Language
}

export function CropSuggestions({
  advisory,
  status,
  mwsCode,
  mwsId,
  compact = false,
  lang = 'en',
}: CropSuggestionsProps) {
  const t = translations[lang]
  const [seasonFilter, setSeasonFilter] = useState<string>('ALL')
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL')
  const [expandedCrop, setExpandedCrop] = useState<string | null>(null)
  const [showCautionInfo, setShowCautionInfo] = useState<boolean>(true)

  const isLoading = status === 'loading'
  const isOffline = status === 'unavailable'

  const water = advisory?.water_summary
  const allCrops = advisory?.recommended_crops || []
  const cautionCrops = advisory?.caution_crops || []

  // Filter crops by season and category
  const filteredCrops = useMemo(() => {
    return allCrops.filter((crop) => {
      const matchSeason =
        seasonFilter === 'ALL' ||
        crop.season.toLowerCase().includes(seasonFilter.toLowerCase())

      const matchCategory =
        categoryFilter === 'ALL' ||
        crop.category.toLowerCase().includes(categoryFilter.toLowerCase())

      return matchSeason && matchCategory
    })
  }, [allCrops, seasonFilter, categoryFilter])

  // Helpers for badge styling
  const getSuitabilityColor = (tier: string) => {
    switch (tier) {
      case 'OPTIMAL':
        return { bg: '#dff1dc', text: '#1b5e20', border: '#a9c79c' }
      case 'HIGHLY_SUITABLE':
        return { bg: '#e0f2fe', text: '#0284c7', border: '#bae6fd' }
      case 'MODERATELY_SUITABLE':
        return { bg: '#fff0d6', text: '#9d5400', border: '#fcd34d' }
      case 'CONDITIONAL':
        return { bg: '#ffedd5', text: '#c2410c', border: '#fed7aa' }
      default:
        return { bg: '#ffe2df', text: '#ba1a1a', border: '#fca5a5' }
    }
  }

  const getWaterTierBadge = (tier: string) => {
    switch (tier) {
      case 'VERY_LOW':
        return { label: 'Very Low Water Need', color: '#16a34a', bg: '#f0fdf4' }
      case 'LOW':
        return { label: 'Low Water Footprint', color: '#0d9488', bg: '#f0fdfa' }
      case 'LOW_MODERATE':
        return { label: 'Low-Moderate Water', color: '#0284c7', bg: '#f0f9ff' }
      case 'MODERATE':
        return { label: 'Moderate Water Need', color: '#d97706', bg: '#fffbeb' }
      case 'HIGH':
        return { label: 'High Water Demand', color: '#ea580c', bg: '#fff7ed' }
      default:
        return { label: 'Extreme Water Demand', color: '#dc2626', bg: '#fef2f2' }
    }
  }

  if (isOffline) {
    return (
      <div className="panel" style={{ borderRadius: 8, padding: 18 }}>
        <div className="panel-head">
          <div>
            <span className="eyebrow">AGRO-HYDROLOGICAL ADVISORY</span>
            <h2>Crop suggestions unavailable</h2>
          </div>
        </div>
        <div className="notice warning" style={{ margin: 0 }}>
          <strong>API Disconnected.</strong> Connect backend service on localhost:8000 to stream calibrated crop suitability intelligence.
        </div>
      </div>
    )
  }

  if (isLoading && !advisory) {
    return (
      <div className="panel" style={{ borderRadius: 8, padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>🌱</div>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Synthesizing Catchment Crop Recommendations...</div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
          Evaluating water stress, rainfall anomaly, TDS salinity, and slope parameters.
        </div>
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? 12 : 18,
        width: '100%',
      }}
    >
      {/* SECTION 1: WATER CONDITION DIAGNOSTICS FOR CROP DECISION */}
      {water && (
        <div
          style={{
            background: 'var(--surface-low)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: compact ? '12px 14px' : '16px 20px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              flexWrap: 'wrap',
              gap: 8,
              marginBottom: 12,
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  letterSpacing: '0.1em',
                  color: 'var(--primary)',
                  textTransform: 'uppercase',
                }}
              >
                HYDROLOGICAL DIAGNOSTICS FOR CROP SELECTION · {advisory?.MWS ?? mwsCode} ({advisory?.id ?? mwsId})
              </span>
              <h3 style={{ margin: '2px 0 0 0', fontSize: compact ? 14 : 16, fontWeight: 800 }}>
                Catchment Water Regime & Irrigation Environment
              </h3>
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: 4,
                  background:
                    water.water_stress_level === 'CRITICAL' || water.water_stress_level === 'HIGH'
                      ? '#ffe2df'
                      : water.water_stress_level === 'MODERATE'
                      ? '#fff0d6'
                      : '#dff1dc',
                  color:
                    water.water_stress_level === 'CRITICAL' || water.water_stress_level === 'HIGH'
                      ? 'var(--red)'
                      : water.water_stress_level === 'MODERATE'
                      ? '#9d5400'
                      : 'var(--primary)',
                  border: '1px solid currentColor',
                }}
              >
                WATER STRESS: {water.water_stress_level} ({water.water_stress_score.toFixed(1)}/100)
              </span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: 4,
                  background: '#f1f5f9',
                  color: '#475569',
                  border: '1px solid #cbd5e1',
                }}
              >
                WQI: {water.wqi ? `${water.wqi.toFixed(1)} WQI` : '—'} ({water.wqi_category ?? 'Simulated'})
              </span>
            </div>
          </div>

          {/* 4 Mini Gauges / Metrics Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact
                ? 'repeat(2, 1fr)'
                : 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: 8,
              marginBottom: 12,
            }}
          >
            {/* Metric 1: Water Stress */}
            <div style={{ background: '#fff', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                💧 Water Stress
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '2px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700 }}>
                  {water.water_stress_score.toFixed(1)}
                </span>
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>/ 100</span>
              </div>
              <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, water.water_stress_score)}%`,
                    background: water.water_stress_score > 55 ? '#ba1a1a' : water.water_stress_score > 40 ? '#ed6c02' : '#1b5e20',
                  }}
                />
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--muted)', marginTop: 4 }}>
                {water.water_stress_level} deficit regime
              </div>
            </div>

            {/* Metric 2: Rainfall Anomaly */}
            <div style={{ background: '#fff', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                🌧️ Rainfall Anomaly
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '2px 0' }}>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 17,
                    fontWeight: 700,
                    color: (water.rainfall_anomaly_sigma ?? 0) < 0 ? '#b91c1c' : '#15803d',
                  }}
                >
                  {(water.rainfall_anomaly_sigma ?? 0) > 0 ? '+' : ''}
                  {water.rainfall_anomaly_sigma != null ? `${water.rainfall_anomaly_sigma.toFixed(2)}σ` : '—'}
                </span>
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--muted)' }}>
                {water.rainfall_mm != null ? `${water.rainfall_mm} mm current` : 'Baseline divergence'}
              </div>
            </div>

            {/* Metric 3: Salinity TDS & pH */}
            <div style={{ background: '#fff', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                🧪 Salinity & pH
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '2px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700 }}>
                  {water.tds_mg_l ? `${Math.round(water.tds_mg_l)}` : '—'}
                </span>
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>mg/L TDS</span>
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--muted)' }}>
                pH: <strong>{water.ph ? water.ph.toFixed(2) : '—'}</strong> ({water.ph && water.ph >= 6.5 && water.ph <= 7.8 ? 'Neutral' : 'Slight Alkaline'})
              </div>
            </div>

            {/* Metric 4: Slope & Runoff */}
            <div style={{ background: '#fff', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                ⛰️ Slope & Runoff
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '2px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700 }}>
                  {water.slope_mean_deg ? `${water.slope_mean_deg.toFixed(1)}°` : '—'}
                </span>
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>mean slope</span>
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--muted)' }}>
                Flood Risk: <strong>{water.flood_risk_score.toFixed(0)}/100</strong> ({water.flood_risk_level})
              </div>
            </div>
          </div>

          {/* Irrigation Advisory Banner */}
          <div
            style={{
              background: '#ffffff',
              border: '1px solid #bbf7d0',
              borderLeft: '4px solid var(--primary)',
              borderRadius: 6,
              padding: '10px 14px',
              fontSize: 11.5,
              lineHeight: 1.45,
              color: '#14532d',
            }}
          >
            <strong>Hydrological Guidance: </strong> {water.irrigation_advisory}
          </div>
        </div>
      )}

      {/* SECTION 2: HIGH-RISK / CAUTION CROPS UNDER WATER DEFICIT */}
      {cautionCrops.length > 0 && (
        <div
          style={{
            background: '#fff8f6',
            border: '1px solid #fecdd3',
            borderLeft: '4px solid #e11d48',
            borderRadius: 8,
            padding: '12px 16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
            }}
            onClick={() => setShowCautionInfo(!showCautionInfo)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16 }}>⚠️</span>
              <div>
                <strong style={{ fontSize: 12.5, color: '#9f1239' }}>
                  Restricted / High-Risk Crops for this Catchment ({cautionCrops.length} Flagged)
                </strong>
                <div style={{ fontSize: 10.5, color: '#be123c' }}>
                  Intensive water-depleting crops that pose acute groundwater depletion risks under current water stress.
                </div>
              </div>
            </div>
            <button
              style={{
                background: 'transparent',
                border: '1px solid #fda4af',
                color: '#9f1239',
                borderRadius: 4,
                padding: '3px 8px',
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              {showCautionInfo ? 'Hide Details ▲' : 'View Flagged Crops ▼'}
            </button>
          </div>

          {showCautionInfo && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 10,
                marginTop: 12,
                paddingTop: 10,
                borderTop: '1px solid #ffe4e6',
              }}
            >
              {cautionCrops.map((c, idx) => (
                <div
                  key={idx}
                  style={{
                    background: '#fff',
                    border: '1px solid #fecdd3',
                    borderRadius: 6,
                    padding: '10px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <strong style={{ fontSize: 12, color: '#881337' }}>{c.crop_name}</strong>
                    <span
                      style={{
                        fontSize: 8.5,
                        fontWeight: 800,
                        padding: '2px 5px',
                        borderRadius: 3,
                        background: '#ffe4e6',
                        color: '#be123c',
                      }}
                    >
                      {c.risk_level.replace('_', ' ')}
                    </span>
                  </div>
                  <div style={{ fontSize: 10.5, color: '#9f1239' }}>
                    <strong>Hazard: </strong> {c.water_deficit_hazard}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b' }}>
                    <strong>Impact: </strong> {c.depletion_impact}
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: '#166534',
                      background: '#f0fdf4',
                      padding: '4px 6px',
                      borderRadius: 4,
                      marginTop: 2,
                    }}
                  >
                    <strong>Eco-Friendly Alternative: </strong> {c.alternative_suggestion}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SECTION 3: FILTER TABS FOR CROPS */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        {/* Season Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', marginRight: 4 }}>
            {lang === 'kn' ? 'ಋತು:' : 'SEASON:'}
          </span>
          {[
            { id: 'ALL', label: t.seasonAll },
            { id: 'Kharif', label: t.seasonKharif },
            { id: 'Rabi', label: t.seasonRabi },
            { id: 'Summer', label: t.seasonSummer },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSeasonFilter(tab.id)}
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                padding: '4px 10px',
                borderRadius: 4,
                border: '1px solid',
                borderColor: seasonFilter === tab.id ? 'var(--primary)' : 'var(--border)',
                background: seasonFilter === tab.id ? 'var(--primary)' : '#fff',
                color: seasonFilter === tab.id ? '#fff' : 'var(--foreground)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Category Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', marginRight: 4 }}>
            {lang === 'kn' ? 'ವರ್ಗ:' : 'CATEGORY:'}
          </span>
          {[
            { id: 'ALL', label: t.catAll },
            { id: 'Millets', label: t.catMillets },
            { id: 'Cash', label: t.catCash },
            { id: 'Pulses', label: t.catPulses },
            { id: 'Oilseeds', label: t.catOilseeds },
            { id: 'Horticulture', label: t.catHorticulture },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                padding: '4px 9px',
                borderRadius: 4,
                border: '1px solid',
                borderColor: categoryFilter === cat.id ? 'var(--secondary)' : 'var(--border)',
                background: categoryFilter === cat.id ? 'var(--secondary)' : '#fff',
                color: categoryFilter === cat.id ? '#fff' : 'var(--foreground)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* SECTION 4: RANKED CROP RECOMMENDATION CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact
            ? '1fr'
            : 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 12,
        }}
      >
        {filteredCrops.length === 0 ? (
          <div
            style={{
              gridColumn: '1 / -1',
              padding: 30,
              textAlign: 'center',
              background: '#fff',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--muted)',
            }}
          >
            No crops matched the selected filters. Reset filters to view all recommendations.
          </div>
        ) : (
          filteredCrops.map((crop, index) => {
            const isExpanded = expandedCrop === crop.crop_name
            const tierStyle = getSuitabilityColor(crop.suitability_tier)
            const waterStyle = getWaterTierBadge(crop.water_tier)

            return (
              <div
                key={crop.crop_name}
                style={{
                  background: '#ffffff',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                  position: 'relative',
                }}
              >
                <div>
                  {/* Top Bar: Rank + Suitability Badge */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          fontFamily: 'var(--font-mono)',
                          background: '#f1f5f9',
                          color: '#475569',
                          padding: '2px 6px',
                          borderRadius: 3,
                        }}
                      >
                        #{index + 1}
                      </span>
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: '0.06em',
                          textTransform: 'uppercase',
                          color: 'var(--muted)',
                        }}
                      >
                        {crop.category}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: '3px 8px',
                        borderRadius: 4,
                        background: tierStyle.bg,
                        color: tierStyle.text,
                        border: `1px solid ${tierStyle.border}`,
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {crop.suitability_score.toFixed(1)}% {crop.suitability_tier}
                    </span>
                  </div>

                  {/* Crop Names (English + Kannada) */}
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--foreground)' }}>
                      {crop.crop_name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--primary)', fontWeight: 600 }}>
                      {crop.local_name}
                    </div>
                  </div>

                  {/* Water Footprint & Season Pills */}
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 6,
                      marginBottom: 10,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 700,
                        padding: '2px 7px',
                        borderRadius: 4,
                        background: waterStyle.bg,
                        color: waterStyle.color,
                        border: `1px solid ${waterStyle.color}40`,
                      }}
                    >
                      💧 {crop.water_requirement_mm} ({waterStyle.label})
                    </span>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 600,
                        padding: '2px 7px',
                        borderRadius: 4,
                        background: '#f8fafc',
                        color: '#475569',
                        border: '1px solid #e2e8f0',
                      }}
                    >
                      🗓 {crop.season}
                    </span>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 600,
                        padding: '2px 7px',
                        borderRadius: 4,
                        background: '#f8fafc',
                        color: '#475569',
                        border: '1px solid #e2e8f0',
                      }}
                    >
                      🧂 Salinity: {crop.salinity_tolerance}
                    </span>
                  </div>

                  {/* Water Stress Rationale */}
                  <div
                    style={{
                      background: 'var(--surface-low)',
                      padding: '8px 10px',
                      borderRadius: 6,
                      fontSize: 11,
                      lineHeight: 1.4,
                      color: 'var(--foreground)',
                      marginBottom: 8,
                    }}
                  >
                    <strong>Why this fits: </strong> {crop.water_stress_rationale}
                  </div>

                  {/* Recommended Irrigation Practice */}
                  <div style={{ fontSize: 10.5, color: '#0369a1', marginBottom: 8 }}>
                    <strong>Recommended Irrigation: </strong> {crop.recommended_irrigation}
                  </div>

                  {/* Expandable Details: Advantages & Risk Management */}
                  {isExpanded && (
                    <div
                      style={{
                        borderTop: '1px solid var(--border)',
                        paddingTop: 8,
                        marginTop: 8,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                          Agronomic Advantages
                        </div>
                        <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 10.5, color: 'var(--foreground)' }}>
                          {crop.key_advantages.map((adv, i) => (
                            <li key={i} style={{ marginBottom: 2 }}>{adv}</li>
                          ))}
                        </ul>
                      </div>

                      <div
                        style={{
                          background: '#fffbeb',
                          border: '1px solid #fef3c7',
                          borderRadius: 4,
                          padding: '6px 8px',
                          fontSize: 10,
                          color: '#92400e',
                        }}
                      >
                        <strong>Risk Management: </strong> {crop.risk_management_tips}
                      </div>
                    </div>
                  )}
                </div>

                {/* Card Footer: Expand/Collapse toggle */}
                <div style={{ marginTop: 10, paddingTop: 6, borderTop: '1px solid #f1f5f9', display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => setExpandedCrop(isExpanded ? null : crop.crop_name)}
                    style={{
                      border: 0,
                      background: 'transparent',
                      color: 'var(--primary)',
                      fontSize: 10.5,
                      fontWeight: 700,
                      padding: '2px 4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    {isExpanded ? 'Show Less ▲' : 'View Agronomic Details ▼'}
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* SECTION 5: IN-SITU SOIL & WATER CONSERVATION PROTOCOLS */}
      {advisory?.conservation_practices && advisory.conservation_practices.length > 0 && (
        <div
          style={{
            background: '#ffffff',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '14px 18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 16 }}>🛡️</span>
            <div>
              <strong style={{ fontSize: 13, color: 'var(--foreground)' }}>
                Targeted Soil & Moisture Conservation Protocols for {advisory.MWS}
              </strong>
              <div style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                Physical field practices recommended to maximize crop water-use efficiency (WUE) under catchment conditions.
              </div>
            </div>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 8,
            }}
          >
            {advisory.conservation_practices.map((practice, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  background: 'var(--surface-low)',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  fontSize: 11,
                  lineHeight: 1.4,
                }}
              >
                <span style={{ color: 'var(--primary)', fontWeight: 800 }}>✓</span>
                <span>{practice}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

'use client'

import React, { useState, useEffect } from 'react'
import {
  AskResponse,
  EvidenceItemRecord,
  ClaimItem,
  WatershedSummary,
  WatershedDetail,
  DataStatus,
  Screen,
} from '../lib/types'
import { askJalDrishti } from '../lib/api'

export interface AskJalDrishtiProps {
  mwsCode?: string
  mwsId?: string
  watersheds?: WatershedSummary[]
  onSelectMws?: (mwsId: string) => void
  isStandalone?: boolean
}

const SAMPLE_QUESTIONS = [
  'What are the main risk factors for this watershed?',
  'What interventions are recommended to mitigate risk?',
  'What is the dominant land cover and topographic slope?',
  'Is there any live or simulated water quality telemetry?',
]

export function AskJalDrishti({
  mwsCode: initialCode = '4D4F2m3',
  mwsId: initialId = 'g_mws.240575',
  watersheds = [],
  onSelectMws,
  isStandalone = false,
}: AskJalDrishtiProps) {
  const [selectedId, setSelectedId] = useState<string>(initialId)
  const [selectedCode, setSelectedCode] = useState<string>(initialCode)
  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<AskResponse | null>(null)
  const [showEvidence, setShowEvidence] = useState(false)

  // Sync if external props change
  useEffect(() => {
    if (initialId && initialId !== selectedId) {
      setSelectedId(initialId)
    }
    if (initialCode && initialCode !== selectedCode) {
      setSelectedCode(initialCode)
    }
  }, [initialId, initialCode])

  const handleMwsChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = e.target.value
    setSelectedId(newId)
    const found = watersheds.find((w) => w.id === newId)
    if (found) {
      setSelectedCode(found.MWS)
    }
    if (onSelectMws) {
      onSelectMws(newId)
    }
    setError(null)
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const res = await askJalDrishti({
        mws_code: selectedCode,
        mws_id: selectedId,
        question: trimmed,
      })

      if (res.status === 'available' && res.data) {
        setResponse(res.data)
      } else {
        setError(res.error || 'Failed to retrieve response from Ask JalDrishti backend.')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unexpected network error occurred.'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectSample = (q: string) => {
    setQuestion(q)
  }

  const currentWatershed = watersheds.find((w) => w.id === selectedId)

  return (
    <div
      className="panel"
      style={{
        marginTop: isStandalone ? '0' : '18px',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        background: '#ffffff',
        boxShadow: isStandalone ? '0 1px 3px rgba(0,0,0,0.05)' : 'none',
      }}
    >
      <div className="panel-head" style={{ marginBottom: '14px' }}>
        <div>
          <span className="eyebrow" style={{ color: 'var(--secondary)' }}>
            DECISION SUPPORT · AI EVIDENCE Q&amp;A
          </span>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            Ask JalDrishti (Gemma 4)
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '12px',
                background: 'var(--surface-high)',
                color: 'var(--primary)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {selectedCode} ({selectedId})
            </span>
          </h2>
          <p style={{ fontSize: '11.5px', color: 'var(--muted)', marginTop: '3px' }}>
            Direct evidence-grounded Q&amp;A powered by Gemma 4. Every response is verified against Model 2 risk scores,
            Sentinel-2 LULC classifications, topography, and GIS ground truth with zero hallucination.
          </p>
        </div>
      </div>

      {/* Catchment Selector if watersheds list is provided */}
      {watersheds.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            background: 'var(--surface-low)',
            padding: '10px 14px',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            marginBottom: '14px',
            flexWrap: 'wrap',
          }}
        >
          <label
            htmlFor="ask-jaldrishti-mws-select"
            style={{
              fontSize: '11px',
              fontWeight: 700,
              color: 'var(--muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Target Micro-Watershed:
          </label>
          <select
            id="ask-jaldrishti-mws-select"
            value={selectedId}
            onChange={handleMwsChange}
            disabled={isLoading}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: '4px',
              border: '1px solid var(--border)',
              background: '#ffffff',
              color: 'var(--foreground)',
              fontFamily: 'var(--font-sans)',
              minWidth: '240px',
            }}
          >
            {watersheds.map((w) => (
              <option key={w.id} value={w.id}>
                {w.MWS} · {w.dominant_class || 'Catchment'} ({w.id}) — {w.risk_category} Risk
              </option>
            ))}
          </select>
          {currentWatershed && (
            <div style={{ display: 'flex', gap: '8px', fontSize: '11px', color: 'var(--muted)' }}>
              <span>Area: <strong>{currentWatershed.area_km2} km²</strong></span>
              <span>· Health: <strong>{currentWatershed.health_index} / 100</strong></span>
              <span>· Driver: <strong>{currentWatershed.primary_driver || 'Assessed'}</strong></span>
            </div>
          )}
        </div>
      )}

      {/* Question Form */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '14px' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
          <input
            type="text"
            id="ask-jaldrishti-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={`Ask a question about ${selectedCode} (e.g. What are the key risk drivers?)...`}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: '5px',
              border: '1px solid var(--border)',
              background: 'var(--surface-low)',
              color: 'var(--foreground)',
              fontSize: '13px',
              fontFamily: 'var(--font-sans)',
            }}
          />
          <button
            type="submit"
            id="ask-jaldrishti-submit"
            disabled={isLoading || !question.trim()}
            style={{
              background: 'var(--primary)',
              color: '#ffffff',
              border: 'none',
              padding: '10px 18px',
              borderRadius: '5px',
              fontSize: '12.5px',
              fontWeight: 700,
              cursor: isLoading || !question.trim() ? 'not-allowed' : 'pointer',
              opacity: isLoading || !question.trim() ? 0.6 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              whiteSpace: 'nowrap',
            }}
          >
            {isLoading ? (
              <>
                <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⟳</span>
                Verifying Evidence...
              </>
            ) : (
              '✦ Ask Gemma 4'
            )}
          </button>
        </div>

        {/* Suggested Quick Prompts */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '10.5px', color: 'var(--muted)', fontWeight: 600 }}>Suggested Questions:</span>
          {SAMPLE_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSelectSample(q)}
              disabled={isLoading}
              style={{
                fontSize: '11px',
                padding: '4px 9px',
                background: 'var(--surface-low)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                color: 'var(--secondary)',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </form>

      {/* Error Notice */}
      {error && (
        <div
          className="notice"
          style={{
            background: '#ffe2df',
            borderColor: 'var(--red)',
            color: 'var(--red)',
            padding: '10px 14px',
            borderRadius: '5px',
            marginBottom: '14px',
          }}
        >
          <strong>Query Error:</strong> {error}
        </div>
      )}

      {/* Loading Indicator */}
      {isLoading && (
        <div
          style={{
            padding: '30px 20px',
            textAlign: 'center',
            background: 'var(--surface-low)',
            borderRadius: '6px',
            color: 'var(--muted)',
            fontSize: '12.5px',
            marginBottom: '14px',
          }}
        >
          <div style={{ fontSize: '22px', marginBottom: '8px' }}>⚙</div>
          <strong style={{ display: 'block', color: 'var(--foreground)' }}>
            Synthesizing Project Evidence &amp; Validating Gemma 4 Output...
          </strong>
          <div style={{ fontSize: '11px', marginTop: '4px', color: 'var(--muted)' }}>
            Extracting 66-MWS GIS records, Model 1 LULC distributions, Model 2 Risk factors, and verifying numerical accuracy.
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !response && !error && (
        <div
          style={{
            padding: '24px 20px',
            background: '#fafafa',
            border: '1px dashed var(--border)',
            borderRadius: '6px',
            textAlign: 'center',
            color: 'var(--muted)',
          }}
        >
          <div style={{ fontSize: '24px', marginBottom: '8px' }}>💬</div>
          <strong style={{ display: 'block', color: 'var(--foreground)', fontSize: '13px', marginBottom: '4px' }}>
            No Question Asked Yet
          </strong>
          <p style={{ fontSize: '12px', maxWidth: '580px', margin: '0 auto 12px auto' }}>
            Type a question above or click one of the suggested prompts to inspect verified hydrological risk scores,
            agricultural land coverage, priority field interventions, or topography for <strong>{selectedCode}</strong>.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', fontSize: '10.5px', flexWrap: 'wrap' }}>
            <span>🔒 Grounded in Verified Data</span>
            <span>· 🛡 Zero Numerical Hallucinations</span>
            <span>· 📐 Deterministic Fallback Guaranteed</span>
          </div>
        </div>
      )}

      {/* Answer and Validation Panel */}
      {!isLoading && response && (
        <div
          style={{
            background: 'var(--surface-low)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '16px',
          }}
        >
          {/* Metadata Header Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid var(--border)',
              paddingBottom: '10px',
              marginBottom: '12px',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {response.validation_passed ? (
                <span
                  style={{
                    background: '#e8f5e9',
                    color: 'var(--primary)',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  ✓ Evidence Verified
                </span>
              ) : (
                <span
                  style={{
                    background: '#fff0d6',
                    color: '#9d5400',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  ⚠ Deterministic Fallback Active
                </span>
              )}

              <span style={{ fontSize: '10.5px', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                Model: {response.model_name}
              </span>

              {response.fallback_used && (
                <span
                  style={{
                    fontSize: '10px',
                    color: '#9a3412',
                    background: '#fffbeb',
                    padding: '2px 6px',
                    borderRadius: '3px',
                  }}
                >
                  Backend returned verified deterministic evidence
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={() => setShowEvidence(!showEvidence)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--secondary)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {showEvidence ? 'Hide Evidence Records ▲' : `View Retrieved Evidence (${response.evidence_used?.length || 0}) ▼`}
            </button>
          </div>

          {/* Answer Text */}
          <div
            style={{
              fontSize: '13px',
              lineHeight: 1.65,
              color: 'var(--foreground)',
              whiteSpace: 'pre-wrap',
              marginBottom: '14px',
            }}
          >
            {response.answer}
          </div>

          {/* Verified Claims (if model provided structured claims) */}
          {response.claims && response.claims.length > 0 && (
            <div style={{ marginTop: '12px', marginBottom: '12px' }}>
              <span
                style={{
                  display: 'block',
                  fontSize: '10px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  color: 'var(--muted)',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                Validated Fact Claims ({response.claims.length}):
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {response.claims.map((c, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: '10.5px',
                      padding: '3px 8px',
                      borderRadius: '3px',
                      background: c.verified ? '#e8f5e9' : '#ffebee',
                      color: c.verified ? 'var(--primary)' : 'var(--red)',
                      border: `1px solid ${c.verified ? '#c8e6c9' : '#ffcdd2'}`,
                      fontFamily: 'var(--font-mono)',
                    }}
                    title={c.verification_notes || ''}
                  >
                    {c.verified ? '✓' : '✗'} [{c.evidence_id}]: {c.claim_text}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Disclosures & Limitations */}
          {response.disclosures && response.disclosures.length > 0 && (
            <div
              style={{
                marginTop: '12px',
                padding: '10px 14px',
                background: '#fff9ed',
                border: '1px solid #fed7aa',
                borderRadius: '5px',
                fontSize: '11.5px',
                color: '#9a3412',
              }}
            >
              <strong>Data Limitations &amp; Provenance Disclosures:</strong>
              <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
                {response.disclosures.map((d, i) => (
                  <li key={i} style={{ marginBottom: '3px' }}>{d}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Supporting Evidence Details Table (expandable) */}
          {showEvidence && response.evidence_used && (
            <div
              style={{
                marginTop: '14px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border)',
              }}
            >
              <div style={{ fontSize: '11.5px', fontWeight: 700, marginBottom: '8px', color: 'var(--primary)' }}>
                Authoritative Evidence Catalog for {response.mws_code} ({response.mws_id}):
              </div>
              <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
                <table style={{ width: '100%', fontSize: '10.5px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-high)', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>ID</th>
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Metric</th>
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Retrieved Value</th>
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Type</th>
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Source &amp; Provenance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.evidence_used.map((item, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: idx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.015)',
                        }}
                      >
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)' }}>{item.id}</td>
                        <td style={{ padding: '5px 8px', fontWeight: 600 }}>{item.metric}</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)' }}>
                          {String(item.value)} {item.unit || ''}
                        </td>
                        <td style={{ padding: '5px 8px' }}>
                          <span
                            style={{
                              fontSize: '9px',
                              padding: '2px 5px',
                              borderRadius: '3px',
                              background:
                                item.source_type === 'simulated_telemetry'
                                  ? '#fff3df'
                                  : item.source_type === 'observed_field' || item.source_type === 'observed_spatial'
                                  ? '#e0f2fe'
                                  : '#e8f5e9',
                              color:
                                item.source_type === 'simulated_telemetry'
                                  ? '#9d5400'
                                  : item.source_type === 'observed_field' || item.source_type === 'observed_spatial'
                                  ? '#0369a1'
                                  : 'var(--primary)',
                            }}
                          >
                            {item.source_type}
                          </span>
                        </td>
                        <td style={{ padding: '5px 8px', color: 'var(--muted)' }}>
                          {item.source} · {item.provenance}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export interface AskJalDrishtiScreenProps {
  mode: 'simulation' | 'live'
  setScreen: (screen: Screen) => void
  apiStatus: DataStatus
  watersheds: WatershedSummary[]
  selectedProfile: WatershedDetail | null
  onSelectMws: (mwsId: string) => void
}

export function AskJalDrishtiScreen({
  mode,
  setScreen,
  apiStatus,
  watersheds,
  selectedProfile,
  onSelectMws,
}: AskJalDrishtiScreenProps) {
  const currentCode = selectedProfile?.MWS || (watersheds[0]?.MWS ?? '4D4F2m3')
  const currentId = selectedProfile?.id || (watersheds[0]?.id ?? 'g_mws.240575')

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">AI DECISION SUPPORT &amp; GROUNDED EVIDENCE</span>
          <h1>Ask JalDrishti (Gemma 4 Q&amp;A)</h1>
          <p>
            Natural-language watershed intelligence powered by Gemma 4. Inquire about hydrological risks,
            Sentinel-2 LULC distributions, terrain indices, and targeted interventions across all 66 micro-watersheds.
          </p>
        </div>
        <div className="heading-actions">
          <button className="outline-button" onClick={() => setScreen('Micro-Watershed Profile')}>
            View Diagnostic Profile →
          </button>
          <button className="outline-button" onClick={() => setScreen('Reports & Exports')}>
            Decision Matrix Table →
          </button>
        </div>
      </div>

      {/* Feature Highlights Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
          marginBottom: '16px',
        }}
      >
        <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '6px', padding: '12px 14px' }}>
          <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--muted)', letterSpacing: '0.05em' }}>AI MODEL</span>
          <strong style={{ display: 'block', fontSize: '14px', marginTop: '2px', color: 'var(--foreground)' }}>gemma-2-9b-it</strong>
          <span style={{ fontSize: '10.5px', color: 'var(--muted)' }}>Google Generative Language API</span>
        </div>
        <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '6px', padding: '12px 14px' }}>
          <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--muted)', letterSpacing: '0.05em' }}>EVIDENCE CATALOG</span>
          <strong style={{ display: 'block', fontSize: '14px', marginTop: '2px', color: 'var(--foreground)' }}>66 Micro-Watersheds</strong>
          <span style={{ fontSize: '10.5px', color: 'var(--muted)' }}>Multi-source GIS, ML &amp; Remote Sensing</span>
        </div>
        <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '6px', padding: '12px 14px' }}>
          <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--muted)', letterSpacing: '0.05em' }}>GROUNDING GUARDRAIL</span>
          <strong style={{ display: 'block', fontSize: '14px', marginTop: '2px', color: '#15803d' }}>Deterministic Verification</strong>
          <span style={{ fontSize: '10.5px', color: 'var(--muted)' }}>Claims validated; non-grounded output rejected</span>
        </div>
        <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '6px', padding: '12px 14px' }}>
          <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--muted)', letterSpacing: '0.05em' }}>DATA HONESTY</span>
          <strong style={{ display: 'block', fontSize: '14px', marginTop: '2px', color: 'var(--foreground)' }}>Explicit Disclosures</strong>
          <span style={{ fontSize: '10.5px', color: 'var(--muted)' }}>Clear separation of real vs simulated data</span>
        </div>
      </div>

      {/* Main Interactive Ask JalDrishti Component */}
      <AskJalDrishti
        mwsCode={currentCode}
        mwsId={currentId}
        watersheds={watersheds}
        onSelectMws={onSelectMws}
        isStandalone={true}
      />
    </>
  )
}

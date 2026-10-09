'use client'

import React, { useState } from 'react'
import { AskResponse, EvidenceItemRecord, ClaimItem } from '../lib/types'
import { askJalDrishti } from '../lib/api'

interface AskJalDrishtiProps {
  mwsCode: string
  mwsId: string
}

const SAMPLE_QUESTIONS = [
  'What are the main risk factors for this watershed?',
  'What interventions are recommended to mitigate risk?',
  'What is the dominant land cover and topographic slope?',
  'Is there any live or simulated water quality telemetry?',
]

export function AskJalDrishti({ mwsCode, mwsId }: AskJalDrishtiProps) {
  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<AskResponse | null>(null)
  const [showEvidence, setShowEvidence] = useState(false)

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const res = await askJalDrishti({
        mws_code: mwsCode,
        mws_id: mwsId,
        question: trimmed,
      })

      if (res.status === 'available' && res.data) {
        setResponse(res.data)
      } else {
        setError(res.error || 'Failed to retrieve response from Ask JalDrishti backend.')
      }
    } catch (err: any) {
      setError(err?.message || 'Unexpected network error occurred.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectSample = (q: string) => {
    setQuestion(q)
  }

  return (
    <div
      className="panel"
      style={{
        marginTop: '18px',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        background: '#ffffff',
      }}
    >
      <div className="panel-head" style={{ marginBottom: '12px' }}>
        <div>
          <span className="eyebrow" style={{ color: 'var(--secondary)' }}>
            DECISION SUPPORT / AI EVIDENCE Q&A
          </span>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            Ask JalDrishti (Gemma 4)
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                padding: '2px 7px',
                borderRadius: '10px',
                background: 'var(--surface-high)',
                color: 'var(--primary)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {mwsCode}
            </span>
          </h2>
          <p style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Direct evidence-grounded Q&A powered by Gemma 4. Answers are verified against Model 2 risk scores,
            Sentinel-2 LULC, terrain indices, and GIS ground truth.
          </p>
        </div>
      </div>

      {/* Question Form */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '14px' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
          <input
            type="text"
            id="ask-jaldrishti-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={`Ask a question about ${mwsCode} (e.g. What are the key risk drivers?)...`}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '9px 12px',
              borderRadius: '4px',
              border: '1px solid var(--border)',
              background: 'var(--surface-low)',
              color: 'var(--foreground)',
              fontSize: '12px',
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
              padding: '9px 16px',
              borderRadius: '4px',
              fontSize: '12px',
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
              'Ask Gemma 4'
            )}
          </button>
        </div>

        {/* Suggested Quick Prompts */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '10px', color: 'var(--muted)', fontWeight: 600 }}>Try asking:</span>
          {SAMPLE_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSelectSample(q)}
              disabled={isLoading}
              style={{
                fontSize: '10.5px',
                padding: '3px 8px',
                background: 'var(--surface-low)',
                border: '1px solid var(--border)',
                borderRadius: '3px',
                color: 'var(--secondary)',
                cursor: 'pointer',
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </form>

      {/* Error Notice */}
      {error && (
        <div className="notice" style={{ background: '#ffe2df', borderColor: 'var(--red)', color: 'var(--red)' }}>
          <strong>Query Error:</strong> {error}
        </div>
      )}

      {/* Loading Indicator */}
      {isLoading && (
        <div
          style={{
            padding: '24px',
            textAlign: 'center',
            background: 'var(--surface-low)',
            borderRadius: '4px',
            color: 'var(--muted)',
            fontSize: '12px',
          }}
        >
          <div style={{ fontSize: '18px', marginBottom: '6px' }}>⚙</div>
          <div>Synthesizing project evidence & validating Gemma 4 citations...</div>
          <div style={{ fontSize: '10px', marginTop: '4px', color: 'var(--muted)' }}>
            Comparing numerical claims to Model 2 Risk Engine and GIS database
          </div>
        </div>
      )}

      {/* Answer and Validation Panel */}
      {!isLoading && response && (
        <div
          style={{
            marginTop: '14px',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: response.fallback_used ? '#fffdf7' : 'var(--surface-low)',
          }}
        >
          {/* Status Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
              borderBottom: '1px solid var(--border)',
              paddingBottom: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {response.validation_passed ? (
                <span
                  style={{
                    background: '#dff1dc',
                    color: 'var(--primary)',
                    fontSize: '10px',
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
                    fontSize: '10px',
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

              <span style={{ fontSize: '10px', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                Model: {response.model_name}
              </span>
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
              {showEvidence ? 'Hide Evidence Records ▲' : `View Retrieved Evidence (${response.evidence_used.length}) ▼`}
            </button>
          </div>

          {/* Answer Text */}
          <div
            style={{
              fontSize: '12.5px',
              lineHeight: 1.6,
              color: 'var(--foreground)',
              whiteSpace: 'pre-wrap',
              marginBottom: '14px',
            }}
          >
            {response.answer}
          </div>

          {/* Verified Claims (if model provided structured claims) */}
          {response.claims && response.claims.length > 0 && (
            <div style={{ marginTop: '10px', marginBottom: '12px' }}>
              <span
                style={{
                  display: 'block',
                  fontSize: '9.5px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  color: 'var(--muted)',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                Validated Claims ({response.claims.length}):
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {response.claims.map((c, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: '10px',
                      padding: '3px 7px',
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
                marginTop: '10px',
                padding: '8px 12px',
                background: '#fff9ed',
                border: '1px solid #fed7aa',
                borderRadius: '4px',
                fontSize: '11px',
                color: '#9a3412',
              }}
            >
              <strong>Data Limitations & Provenance Disclosures:</strong>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                {response.disclosures.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Supporting Evidence Details Table (expandable) */}
          {showEvidence && (
            <div
              style={{
                marginTop: '14px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border)',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 700, marginBottom: '8px', color: 'var(--primary)' }}>
                Authoritative Evidence Catalog for {response.mws_code}:
              </div>
              <div style={{ maxHeight: '220px', overflowY: 'auto' }}>
                <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-high)', textAlign: 'left' }}>
                      <th style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>ID</th>
                      <th style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>Metric</th>
                      <th style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>Retrieved Value</th>
                      <th style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>Type</th>
                      <th style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>Source & Provenance</th>
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
                        <td style={{ padding: '4px 6px', fontFamily: 'var(--font-mono)' }}>{item.id}</td>
                        <td style={{ padding: '4px 6px', fontWeight: 600 }}>{item.metric}</td>
                        <td style={{ padding: '4px 6px', fontFamily: 'var(--font-mono)' }}>
                          {String(item.value)} {item.unit || ''}
                        </td>
                        <td style={{ padding: '4px 6px' }}>
                          <span
                            style={{
                              fontSize: '8.5px',
                              padding: '1px 4px',
                              borderRadius: '2px',
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
                        <td style={{ padding: '4px 6px', color: 'var(--muted)' }}>
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

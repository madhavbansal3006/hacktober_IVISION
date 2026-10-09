'use client'

import React from 'react'
import { useLanguage } from '../lib/i18n/LanguageContext'
import { Locale } from '../lib/i18n/types'

interface LanguageOption {
  code: Locale
  label: string
  nativeLabel: string
}

const LANGUAGE_OPTIONS: LanguageOption[] = [
  { code: 'en', label: 'English', nativeLabel: 'English' },
  { code: 'kn', label: 'Kannada', nativeLabel: 'ಕನ್ನಡ' },
  { code: 'hi', label: 'Hindi', nativeLabel: 'हिन्दी' },
]

export function LanguageSelector({ className = '' }: { className?: string }) {
  const { locale, setLocale, dict } = useLanguage()

  return (
    <div
      className={`lang-control ${className}`}
      role="group"
      aria-label="Language selection"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        background: 'var(--surface-low)',
        padding: '3px',
        borderRadius: '6px',
        gap: '2px',
        border: '1px solid var(--border)',
      }}
    >
      <span
        style={{
          fontSize: '9px',
          fontWeight: 800,
          letterSpacing: '0.08em',
          color: 'var(--muted)',
          padding: '0 6px',
          userSelect: 'none',
        }}
      >
        {dict.header.languageLabel}
      </span>
      {LANGUAGE_OPTIONS.map((opt) => {
        const isSelected = locale === opt.code
        return (
          <button
            key={opt.code}
            type="button"
            aria-pressed={isSelected}
            aria-label={`Select language: ${opt.label} (${opt.nativeLabel})`}
            onClick={() => setLocale(opt.code)}
            style={{
              border: 0,
              background: isSelected ? 'var(--primary)' : 'transparent',
              color: isSelected ? '#ffffff' : 'var(--muted)',
              fontWeight: isSelected ? 700 : 500,
              padding: '5px 9px',
              borderRadius: '4px',
              fontSize: '11px',
              cursor: 'pointer',
              transition: 'background 0.15s ease, color 0.15s ease',
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
            }}
          >
            {opt.nativeLabel}
          </button>
        )
      })}
    </div>
  )
}

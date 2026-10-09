'use client'

import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from 'react'
import { Locale, Translations } from './types'
import { en } from './locales/en'
import { kn } from './locales/kn'
import { hi } from './locales/hi'

const LOCALES: Record<Locale, Translations> = {
  en,
  kn,
  hi,
}

const STORAGE_KEY = 'jaldrishti_locale'

interface LanguageContextType {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (path: string, params?: Record<string, string | number>) => string
  dict: Translations
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

function resolvePath(obj: any, path: string): string | undefined {
  if (!obj) return undefined
  const parts = path.split('.')
  let current: any = obj
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part]
    } else {
      return undefined
    }
  }
  return typeof current === 'string' ? current : undefined
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('en')
  const [mounted, setMounted] = useState<boolean>(false)

  // Safe SSR hydration: read localStorage on mount
  useEffect(() => {
    setMounted(true)
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY) as Locale | null
      if (stored && (stored === 'en' || stored === 'kn' || stored === 'hi')) {
        setLocaleState(stored)
        document.documentElement.lang = stored
      } else {
        document.documentElement.lang = 'en'
      }
    } catch {
      // Storage unavailable or disabled
    }
  }, [])

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    try {
      window.localStorage.setItem(STORAGE_KEY, newLocale)
      document.documentElement.lang = newLocale
    } catch {
      // Storage unavailable or disabled
    }
  }

  const dict = useMemo(() => {
    return LOCALES[locale] || LOCALES.en
  }, [locale])

  const t = useMemo(() => {
    return (path: string, params?: Record<string, string | number>): string => {
      // 1. Try target locale dictionary
      let template = resolvePath(LOCALES[locale], path)

      // 2. Fall back to English dictionary if missing
      if (template === undefined) {
        template = resolvePath(LOCALES.en, path)
      }

      // 3. Fall back to path itself if not found anywhere
      if (template === undefined) {
        return path
      }

      // 4. Safely interpolate parameters if provided
      if (params) {
        let result = template
        for (const [key, value] of Object.entries(params)) {
          // Replace all occurrences of {key}
          result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), String(value))
        }
        return result
      }

      return template
    }
  }, [locale])

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t, dict }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext)
  if (!context) {
    // Graceful fallback if used outside provider (e.g. during test/isolated render)
    return {
      locale: 'en',
      setLocale: () => {},
      t: (path: string, params?: Record<string, string | number>) => {
        let template = resolvePath(LOCALES.en, path) || path
        if (params) {
          for (const [key, value] of Object.entries(params)) {
            template = template.replace(new RegExp(`\\{${key}\\}`, 'g'), String(value))
          }
        }
        return template
      },
      dict: LOCALES.en,
    }
  }
  return context
}

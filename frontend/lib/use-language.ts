'use client'

import { useState, useEffect, useCallback } from 'react'
import type { Lang } from './translations'

const STORAGE_KEY = 'ss_lang'

export function useLanguage() {
  const [lang, setLang] = useState<Lang>('en')

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as Lang | null
      if (stored === 'hi') setLang('hi')
    } catch { /* localStorage unavailable (SSR/private browsing) */ }
  }, [])

  const toggle = useCallback(() => {
    setLang((prev) => {
      const next: Lang = prev === 'en' ? 'hi' : 'en'
      try { localStorage.setItem(STORAGE_KEY, next) } catch { /* ignore */ }
      return next
    })
  }, [])

  return { lang, toggle }
}

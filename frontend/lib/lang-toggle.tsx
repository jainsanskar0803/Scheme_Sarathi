'use client'

import type { Lang } from './translations'

export function LangToggle({ lang, onToggle }: { lang: Lang; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      title={lang === 'en' ? 'Switch to Hindi' : 'Switch to English'}
      className="flex-shrink-0 flex items-center gap-0 rounded-full border border-gray-200 overflow-hidden text-xs font-semibold shadow-sm"
    >
      <span className={`px-2.5 py-1 transition-colors ${lang === 'en' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-400 hover:text-gray-600'}`}>
        EN
      </span>
      <span className={`px-2.5 py-1 transition-colors ${lang === 'hi' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-400 hover:text-gray-600'}`}>
        हिं
      </span>
    </button>
  )
}

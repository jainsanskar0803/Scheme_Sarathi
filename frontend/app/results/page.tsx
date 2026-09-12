'use client'

import { useEffect, useState, useMemo, useCallback, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { matchSchemes, translateTexts, ApiError } from '@/lib/api'
import type { MatchResponse, SchemeMatchResult, ConditionExplanation, Profile } from '@/lib/types'
import { useLanguage } from '@/lib/use-language'
import { LangToggle } from '@/lib/lang-toggle'
import { t } from '@/lib/translations'
import type { Lang } from '@/lib/translations'

interface CardTr { name: string; benefit: string }

const PAGE_SIZE = 20

// ─── Types ───────────────────────────────────────────────────────────────────

type Tab = 'eligible' | 'near_miss' | 'insufficient_information'
type SortKey = 'strength' | 'alpha' | 'source'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function rankScore(s: SchemeMatchResult): number {
  return (s.passed_rules?.length ?? 0) - (s.skipped_count ?? 0) * 0.5
}

function matchesSearch(s: SchemeMatchResult, q: string): boolean {
  if (!q) return true
  const lower = q.toLowerCase()
  return (
    s.scheme_name.toLowerCase().includes(lower) ||
    (s.benefit ?? '').toLowerCase().includes(lower) ||
    s.category_display.some((c) => c.toLowerCase().includes(lower)) ||
    s.tags.some((t) => t.toLowerCase().includes(lower))
  )
}

function sortSchemes(schemes: SchemeMatchResult[], sort: SortKey): SchemeMatchResult[] {
  const copy = [...schemes]
  if (sort === 'strength') return copy.sort((a, b) => rankScore(b) - rankScore(a))
  if (sort === 'alpha') return copy.sort((a, b) => a.scheme_name.localeCompare(b.scheme_name))
  if (sort === 'source') return copy.sort((a, b) => a.source.localeCompare(b.source))
  return copy
}

function extractCategories(schemes: SchemeMatchResult[]): string[] {
  const counts = new Map<string, number>()
  for (const s of schemes) {
    for (const c of s.category_display) {
      counts.set(c, (counts.get(c) ?? 0) + 1)
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([c]) => c)
    .slice(0, 12)
}

function formatIncome(v: number | null): string {
  if (v === null) return ''
  if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`
  if (v >= 1000) return `₹${(v / 1000).toFixed(0)}K`
  return `₹${v}`
}

// ─── Root Page ────────────────────────────────────────────────────────────────

export default function ResultsPage() {
  const { lang, toggle } = useLanguage()
  const T = t(lang)
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
          <Spinner size="lg" />
          <p className="text-gray-500 font-medium">{T.loadingResults}</p>
        </div>
      }
    >
      <ResultsContent lang={lang} onToggleLang={toggle} />
    </Suspense>
  )
}

// ─── Main Content ─────────────────────────────────────────────────────────────

function ResultsContent({ lang, onToggleLang }: { lang: Lang; onToggleLang: () => void }) {
  const T = t(lang)
  const router = useRouter()
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session')

  const [data, setData] = useState<MatchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // UI state
  const [activeTab, setActiveTab] = useState<Tab>('eligible')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [sort, setSort] = useState<SortKey>('strength')
  const [page, setPage] = useState(1)

  // Card-level Hindi translations: scheme_id → {name, benefit}
  const [cardTr, setCardTr] = useState<Map<string, CardTr>>(new Map())
  const translatingIds = useRef<Set<string>>(new Set())

  const loadResults = useCallback(async () => {
    if (!sessionId) { setError('No session found. Please start from the home page.'); setLoading(false); return }
    try {
      const cached = sessionStorage.getItem('match_results')
      if (cached) {
        const parsed = JSON.parse(cached) as MatchResponse
        if (parsed.session_id === sessionId) { setData(parsed); setLoading(false); return }
      }
    } catch { /* ignore */ }
    try {
      const results = await matchSchemes(sessionId)
      const toCache = { ...results, ineligible: [] }
      try { sessionStorage.setItem('match_results', JSON.stringify(toCache)) } catch { /* quota exceeded — skip cache */ }
      setData(results)
    } catch (err) {
      setError(err instanceof ApiError ? `Could not load results: ${err.message}` : 'Failed to load results.')
    } finally { setLoading(false) }
  }, [sessionId])

  useEffect(() => { loadResults() }, [loadResults])

  // Reset page when filters change
  useEffect(() => { setPage(1) }, [activeTab, search, category, sort])

  // Reset card translations when switching away from Hindi or when filter context changes
  useEffect(() => {
    if (lang !== 'hi') {
      setCardTr(new Map())
      translatingIds.current = new Set()
    }
  }, [lang, activeTab, search, category, sort])

  const activeSchemes = useMemo(() => {
    if (!data) return []
    return data[activeTab]
  }, [data, activeTab])

  const categories = useMemo(() => extractCategories(activeSchemes), [activeSchemes])

  const filtered = useMemo(() => {
    let list = activeSchemes
    if (search) list = list.filter((s) => matchesSearch(s, search))
    if (category !== 'all') list = list.filter((s) => s.category_display.includes(category))
    return sortSchemes(list, sort)
  }, [activeSchemes, search, category, sort])

  const paged = useMemo(() => filtered.slice(0, page * PAGE_SIZE), [filtered, page])
  const hasMore = paged.length < filtered.length

  // Translate scheme names + benefits for visible cards when Hindi is active
  useEffect(() => {
    if (lang !== 'hi' || paged.length === 0) return
    const toTr = paged.filter((s) => !translatingIds.current.has(s.scheme_id) && !cardTr.has(s.scheme_id))
    if (toTr.length === 0) return
    toTr.forEach((s) => translatingIds.current.add(s.scheme_id))

    const texts: (string | null)[] = []
    const meta: { id: string; ni: number; bi: number }[] = []
    for (const s of toTr) {
      meta.push({ id: s.scheme_id, ni: texts.length, bi: texts.length + 1 })
      texts.push(s.scheme_name, s.benefit || null)
    }

    let cancelled = false
    translateTexts(texts).then((trs) => {
      if (cancelled) return
      setCardTr((prev) => {
        const next = new Map(prev)
        for (const { id, ni, bi } of meta) {
          const orig = toTr.find((s) => s.scheme_id === id)!
          next.set(id, {
            name: (trs[ni] as string) || orig.scheme_name,
            benefit: (trs[bi] as string) || orig.benefit,
          })
        }
        return next
      })
    }).catch(() => {
      toTr.forEach((s) => translatingIds.current.delete(s.scheme_id))
    })
    return () => { cancelled = true }
  }, [lang, paged]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <LoadingState lang={lang} />
  if (error) return <ErrorState message={error} onBack={() => router.push('/')} lang={lang} />
  if (!data) return null

  const tabs: { key: Tab; emoji: string; label: string; count: number }[] = [
    { key: 'eligible', emoji: '🟢', label: T.tabEligible, count: data.eligible.length },
    { key: 'near_miss', emoji: '🟡', label: T.tabNearMiss, count: data.near_miss.length },
    { key: 'insufficient_information', emoji: '⚪', label: T.tabNeedInfo, count: data.insufficient_information.length },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sticky header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
              {T.backHome}
            </Link>
            <span className="text-gray-300">|</span>
            <span className="text-gray-900 font-bold text-base">{T.yourResults}</span>
          </div>
          <div className="flex items-center gap-2">
            <LangToggle lang={lang} onToggle={onToggleLang} />
            <Link
              href={`/interview?session=${sessionId}`}
              className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg font-medium hover:bg-indigo-100 transition-colors"
            >
              {T.refineProfile}
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-5 space-y-4">

        {/* Profile summary */}
        <ProfileStrip profile={data.profile} lang={lang} />

        {/* Stats overview */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
          <p className="text-gray-400 text-xs mb-3">
            {T.evaluatedSchemes(data.total_schemes, data.eligible.length + data.near_miss.length + data.insufficient_information.length)}
          </p>
          <div className="grid grid-cols-4 gap-2">
            {[
              { n: data.eligible.length, label: T.tabEligible, cls: 'text-green-600 bg-green-50 border-green-200' },
              { n: data.near_miss.length, label: T.tabNearMiss, cls: 'text-amber-600 bg-amber-50 border-amber-200' },
              { n: data.insufficient_information.length, label: T.tabNeedInfo, cls: 'text-gray-500 bg-gray-50 border-gray-200' },
              { n: data.ineligible.length, label: T.notEligible, cls: 'text-red-400 bg-red-50 border-red-200' },
            ].map(({ n, label, cls }) => (
              <div key={label} className={`rounded-xl border p-3 text-center ${cls}`}>
                <div className="text-xl font-extrabold">{n}</div>
                <div className="text-xs font-medium mt-0.5 opacity-75">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setSearch(''); setCategory('all') }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-lg text-sm font-semibold transition-all duration-150 ${
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span>{tab.emoji}</span>
              <span className="hidden sm:inline">{tab.label}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-bold ${
                activeTab === tab.key ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-200 text-gray-500'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search + Filters */}
        {activeSchemes.length > 0 && (
          <div className="flex flex-col sm:flex-row gap-2">
            {/* Search */}
            <div className="relative flex-1">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={T.searchPlaceholder}
                className="w-full pl-9 pr-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  ✕
                </button>
              )}
            </div>

            {/* Category filter */}
            {categories.length > 1 && (
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="text-sm bg-white border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:border-indigo-400 text-gray-700"
              >
                <option value="all">{T.allCategories}</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}

            {/* Sort */}
            {activeTab === 'eligible' && (
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="text-sm bg-white border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:border-indigo-400 text-gray-700"
              >
                <option value="strength">{T.sortBestMatch}</option>
                <option value="alpha">{T.sortAlpha}</option>
                <option value="source">{T.sortBySource}</option>
              </select>
            )}
          </div>
        )}

        {/* Results count */}
        {(search || category !== 'all') ? (
          <p className="text-xs text-gray-400">
            {T.showingOf(filtered.length, activeSchemes.length)}
            {search && <> {T.matching} &ldquo;<strong className="text-gray-600">{search}</strong>&rdquo;</>}
            {category !== 'all' && <> {T.inCategory} <strong className="text-gray-600">{category}</strong></>}
          </p>
        ) : null}

        {/* Empty state */}
        {filtered.length === 0 && (
          <EmptyState tab={activeTab} hasFilters={!!(search || category !== 'all')} sessionId={sessionId ?? ''} onClear={() => { setSearch(''); setCategory('all') }} lang={lang} />
        )}

        {/* Scheme cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {paged.map((scheme) => (
            activeTab === 'eligible' ? (
              <EligibleCard key={scheme.scheme_id} scheme={scheme} sessionId={sessionId ?? ''} lang={lang} tr={cardTr.get(scheme.scheme_id)} />
            ) : activeTab === 'near_miss' ? (
              <NearMissCard key={scheme.scheme_id} scheme={scheme} sessionId={sessionId ?? ''} lang={lang} tr={cardTr.get(scheme.scheme_id)} />
            ) : (
              <InsufficientCard key={scheme.scheme_id} scheme={scheme} sessionId={sessionId ?? ''} lang={lang} tr={cardTr.get(scheme.scheme_id)} />
            )
          ))}
        </div>

        {/* Load more */}
        {hasMore && (
          <div className="flex flex-col items-center gap-1 pb-6">
            <button
              onClick={() => setPage((p) => p + 1)}
              className="bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 px-6 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-sm"
            >
              {T.loadMore(Math.min(PAGE_SIZE, filtered.length - paged.length))}
            </button>
            <span className="text-xs text-gray-400">
              {T.showingCount(paged.length, filtered.length)}
            </span>
          </div>
        )}

        {/* Footer actions */}
        <div className="flex flex-col sm:flex-row gap-2 pb-8 pt-2">
          <Link
            href={`/interview?session=${sessionId}`}
            className="flex-1 text-center bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            {T.refineMyProfile}
          </Link>
          <button
            onClick={() => router.push('/')}
            className="flex-1 text-center bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            {T.newSession}
          </button>
        </div>
      </main>
    </div>
  )
}

// ─── Profile Strip ────────────────────────────────────────────────────────────

function ProfileStrip({ profile, lang }: { profile: Profile; lang: Lang }) {
  const T = t(lang)
  const chips: string[] = []
  if (profile.age) chips.push(`${profile.age} ${T.yrs}`)
  if (profile.gender) chips.push(profile.gender)
  if (profile.state) chips.push(profile.state)
  if (profile.occupation) chips.push(profile.occupation)
  if (profile.annual_income) chips.push(formatIncome(profile.annual_income) + T.perYr)
  if (profile.caste) chips.push(profile.caste.toUpperCase())
  if (profile.domicile) chips.push(profile.domicile)
  if (profile.is_disabled === true) chips.push(T.disabled)
  if (profile.has_bpl_card === true) chips.push(T.bpl)

  if (chips.length === 0) return null

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm px-4 py-3 flex flex-wrap gap-2 items-center">
      <span className="text-gray-400 text-xs font-medium">{T.yourProfile}</span>
      {chips.map((c) => (
        <span key={c} className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full font-medium">
          {c}
        </span>
      ))}
    </div>
  )
}

// ─── Eligible Card ────────────────────────────────────────────────────────────

function EligibleCard({ scheme, sessionId, lang, tr }: { scheme: SchemeMatchResult; sessionId: string; lang: Lang; tr?: CardTr }) {
  const T = t(lang)
  const [expanded, setExpanded] = useState(false)

  const passConditions = scheme.explanation.filter((c) => c.status === 'PASS')
  const uniquePass = dedupeConditions(passConditions)
  const showDocs = scheme.required_documents
    ? scheme.required_documents.split(/[,\n]/).map((d) => d.trim()).filter(Boolean).slice(0, 3)
    : []

  const displayName = tr?.name || scheme.scheme_name
  const displayBenefit = tr?.benefit || scheme.benefit

  return (
    <div className="bg-white border border-green-100 rounded-2xl shadow-sm overflow-hidden flex flex-col hover:shadow-md transition-shadow duration-200">
      {/* Header bar */}
      <div className="bg-green-50 border-b border-green-100 px-4 py-2 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-bold text-green-700">
          <span className="text-green-500">✓</span> {T.tabEligible}
        </span>
        <span className="text-xs text-gray-500 truncate max-w-[180px]">{scheme.source}</span>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        {/* Name */}
        <h3 className="text-gray-900 font-semibold text-sm leading-snug">{displayName}</h3>

        {/* Categories */}
        {scheme.category_display.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {scheme.category_display.slice(0, 3).map((c) => (
              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{c}</span>
            ))}
          </div>
        )}

        {/* Benefit */}
        {displayBenefit && (
          <div className="bg-green-50 border border-green-100 rounded-lg px-3 py-2">
            <p className="text-xs font-semibold text-green-700 mb-0.5">{T.benefit}</p>
            <p className="text-green-800 text-xs leading-relaxed line-clamp-2">{displayBenefit}</p>
          </div>
        )}

        {/* Why you qualify */}
        {uniquePass.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1.5">{T.whyQualify}</p>
            <ul className="space-y-1">
              {uniquePass.slice(0, expanded ? undefined : 3).map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                  <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                  <span><span className="font-medium">{c.label}:</span> {c.citizen_value_display} — {c.requirement}</span>
                </li>
              ))}
            </ul>
            {uniquePass.length > 3 && (
              <button onClick={() => setExpanded((v) => !v)} className="text-xs text-indigo-500 hover:text-indigo-700 mt-1 font-medium">
                {expanded ? T.showLess : T.moreConditions(uniquePass.length - 3)}
              </button>
            )}
          </div>
        )}

        {/* Documents teaser */}
        {showDocs.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1">{T.documentsNeeded}</p>
            <div className="flex flex-wrap gap-1">
              {showDocs.map((d) => (
                <span key={d} className="text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2 py-0.5 rounded-full">{d}</span>
              ))}
              {(scheme.required_documents?.split(/[,\n]/).filter(Boolean).length ?? 0) > 3 && (
                <span className="text-xs text-gray-400">+more</span>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-auto pt-2 flex items-center justify-between">
          {scheme.skipped_count > 0 && (
            <span className="text-xs text-gray-400">{T.conditionsNotChecked(scheme.skipped_count)}</span>
          )}
          <Link
            href={`/scheme/${scheme.scheme_id}?session=${sessionId}`}
            className="ml-auto text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
          >
            {T.fullDetails}
          </Link>
        </div>
      </div>
    </div>
  )
}

// ─── Near Miss Card ───────────────────────────────────────────────────────────

function NearMissCard({ scheme, sessionId, lang, tr }: { scheme: SchemeMatchResult; sessionId: string; lang: Lang; tr?: CardTr }) {
  const T = t(lang)
  const nearMissConditions = scheme.explanation.filter((c) => c.status === 'NEAR_MISS')
  const passConditions = dedupeConditions(scheme.explanation.filter((c) => c.status === 'PASS'))
  const displayName = tr?.name || scheme.scheme_name
  const displayBenefit = tr?.benefit || scheme.benefit

  return (
    <div className="bg-white border border-amber-100 rounded-2xl shadow-sm overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      {/* Header bar */}
      <div className="bg-amber-50 border-b border-amber-100 px-4 py-2 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-700">
          <span>~</span> {T.nearMissBadge.replace('~ ', '')}
        </span>
        <span className="text-xs text-gray-500 truncate max-w-[180px]">{scheme.source}</span>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        <h3 className="text-gray-900 font-semibold text-sm leading-snug">{displayName}</h3>

        {scheme.category_display.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {scheme.category_display.slice(0, 3).map((c) => (
              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{c}</span>
            ))}
          </div>
        )}

        {displayBenefit && (
          <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{displayBenefit}</p>
        )}

        {/* What failed */}
        {nearMissConditions.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 space-y-2">
            <p className="text-xs font-bold text-amber-800">{T.whatsHoldingBack}</p>
            {nearMissConditions.map((c, i) => (
              <div key={i} className="space-y-0.5">
                <div className="flex items-start gap-1.5">
                  <span className="text-amber-500 mt-0.5 flex-shrink-0 text-xs">▲</span>
                  <span className="text-xs text-amber-900">
                    <span className="font-semibold">{c.label}:</span>{' '}
                    {T.yourValue} <span className="font-semibold">{c.citizen_value_display}</span> {T.requirementIs} <span className="font-semibold">{c.requirement}</span>
                  </span>
                </div>
                {c.gap && (
                  <p className="text-xs text-amber-700 font-medium pl-4">
                    {T.gap} {c.gap}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* What you do meet */}
        {passConditions.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1">{T.conditionsYouMeet}</p>
            <ul className="space-y-1">
              {passConditions.slice(0, 3).map((c, i) => (
                <li key={i} className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="text-green-500 flex-shrink-0">✓</span>
                  <span>{c.label}: {c.citizen_value_display}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-auto pt-2">
          <Link
            href={`/scheme/${scheme.scheme_id}?session=${sessionId}`}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
          >
            {T.viewFullDetails}
          </Link>
        </div>
      </div>
    </div>
  )
}

// ─── Insufficient Info Card ───────────────────────────────────────────────────

function InsufficientCard({ scheme, sessionId, lang, tr }: { scheme: SchemeMatchResult; sessionId: string; lang: Lang; tr?: CardTr }) {
  const T = t(lang)
  const notProvided = scheme.explanation.filter((c) => c.status === 'NOT_PROVIDED')
  const passing = dedupeConditions(scheme.explanation.filter((c) => c.status === 'PASS'))
  const displayName = tr?.name || scheme.scheme_name
  const displayBenefit = tr?.benefit || scheme.benefit

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-bold text-gray-500">
          <span>?</span> {T.needInfoBadge.replace('? ', '')}
        </span>
        <span className="text-xs text-gray-400 truncate max-w-[180px]">{scheme.source}</span>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        <h3 className="text-gray-900 font-semibold text-sm leading-snug">{displayName}</h3>

        {scheme.category_display.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {scheme.category_display.slice(0, 3).map((c) => (
              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{c}</span>
            ))}
          </div>
        )}

        {displayBenefit && (
          <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{displayBenefit}</p>
        )}

        {/* Missing info */}
        {notProvided.length > 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5">
            <p className="text-xs font-bold text-gray-600 mb-1.5">{T.tellUsToCheck}</p>
            <ul className="space-y-1">
              {notProvided.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                  <span className="text-gray-400 flex-shrink-0">•</span>
                  <span>
                    <span className="font-medium">{c.label}</span>
                    {c.requirement && <span className="text-gray-400"> — {c.requirement}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* What you do meet */}
        {passing.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 mb-1">{T.alreadyConfirmed}</p>
            <div className="flex flex-wrap gap-1.5">
              {passing.slice(0, 4).map((c, i) => (
                <span key={i} className="text-xs bg-green-50 text-green-700 border border-green-100 px-2 py-0.5 rounded-full">
                  ✓ {c.label}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto pt-2 flex items-center gap-3">
          <Link
            href={`/interview?session=${sessionId}`}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
          >
            {T.completeProfile}
          </Link>
          <Link
            href={`/scheme/${scheme.scheme_id}?session=${sessionId}`}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            {T.viewDetails}
          </Link>
        </div>
      </div>
    </div>
  )
}

// ─── Shared Utilities ─────────────────────────────────────────────────────────

function dedupeConditions(conditions: ConditionExplanation[]): ConditionExplanation[] {
  const seen = new Set<string>()
  return conditions.filter((c) => {
    const key = `${c.field}:${c.requirement}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function EmptyState({ tab, hasFilters, sessionId, onClear, lang }: { tab: Tab; hasFilters: boolean; sessionId: string; onClear: () => void; lang: Lang }) {
  const T = t(lang)
  if (hasFilters) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
        <p className="text-gray-500 text-sm mb-3">{T.noFilterMatch}</p>
        <button onClick={onClear} className="text-indigo-600 text-sm font-medium hover:text-indigo-800">
          {T.clearFilters}
        </button>
      </div>
    )
  }

  const messages: Record<Tab, { icon: string; title: string; body: string }> = {
    eligible: { icon: '🎉', title: T.noEligibleTitle, body: T.noEligibleBody },
    near_miss: { icon: '🎯', title: T.noNearMissTitle, body: T.noNearMissBody },
    insufficient_information: { icon: '✅', title: T.noNeedInfoTitle, body: T.noNeedInfoBody },
  }

  const { icon, title, body } = messages[tab]

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-10 text-center">
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="text-gray-700 font-semibold mb-1">{title}</h3>
      <p className="text-gray-400 text-sm mb-4">{body}</p>
      <Link
        href={`/interview?session=${sessionId}`}
        className="inline-flex items-center gap-1 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
      >
        {T.completeProfileBtn}
      </Link>
    </div>
  )
}

function Spinner({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const sz = size === 'lg' ? 'w-12 h-12' : 'w-6 h-6'
  return (
    <svg className={`animate-spin ${sz} text-indigo-500`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function LoadingState({ lang }: { lang: Lang }) {
  const T = t(lang)
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-5">
      <Spinner size="lg" />
      <div className="text-center">
        <p className="text-gray-700 font-semibold text-lg">{T.evaluatingSchemes}</p>
        <p className="text-gray-400 text-sm mt-1">{T.justAMoment}</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2 max-w-xs">
        {T.loadingCategories.map((c) => (
          <span key={c} className="text-xs bg-indigo-100 text-indigo-600 px-3 py-1 rounded-full animate-pulse">{c}</span>
        ))}
      </div>
    </div>
  )
}

function ErrorState({ message, onBack, lang }: { message: string; onBack: () => void; lang: Lang }) {
  const T = t(lang)
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white border border-red-200 rounded-2xl px-8 py-8 text-center max-w-sm shadow-sm">
        <div className="text-4xl mb-3">⚠️</div>
        <h2 className="text-red-800 font-semibold mb-2">{T.somethingWrong}</h2>
        <p className="text-red-600 text-sm mb-5">{message}</p>
        <button onClick={onBack} className="bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors">
          {T.startOver}
        </button>
      </div>
    </div>
  )
}

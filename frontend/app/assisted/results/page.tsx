'use client'

import { useEffect, useState, useMemo, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  matchSchemes,
  getCitizen,
  listFollowups,
  setFollowup,
  ApiError,
} from '@/lib/api'
import type { CitizenRecord, FollowupRecord, FollowupStatus } from '@/lib/api'
import type { MatchResponse, SchemeMatchResult, ConditionExplanation } from '@/lib/types'

const WORKER_KEY = 'assisted_worker_id'

type Tab = 'eligible' | 'near_miss' | 'insufficient_information'

const STATUS_LABELS: Record<FollowupStatus, string> = {
  will_apply: 'Will Apply',
  applied: 'Applied',
  received: 'Received',
  rejected: 'Rejected',
  not_applicable: 'Not Applicable',
}

const STATUS_COLORS: Record<FollowupStatus, string> = {
  will_apply: 'bg-blue-50 text-blue-700 border-blue-200',
  applied: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  received: 'bg-green-50 text-green-700 border-green-200',
  rejected: 'bg-red-50 text-red-700 border-red-200',
  not_applicable: 'bg-gray-100 text-gray-500 border-gray-200',
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function AssistedResultsPage() {
  return (
    <Suspense fallback={<LoadingFull />}>
      <ResultsContent />
    </Suspense>
  )
}

// ─── Main content ─────────────────────────────────────────────────────────────

function ResultsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session')

  const [workerId, setWorkerId] = useState<string | null>(null)
  const [citizen, setCitizen] = useState<CitizenRecord | null>(null)
  const [data, setData] = useState<MatchResponse | null>(null)
  const [followups, setFollowups] = useState<Record<string, FollowupRecord>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // UI state
  const [activeTab, setActiveTab] = useState<Tab>('eligible')
  const [search, setSearch] = useState('')

  useEffect(() => {
    const id = localStorage.getItem(WORKER_KEY)
    if (!id) { router.replace('/assisted'); return }
    setWorkerId(id)
  }, [router])

  const load = useCallback(async () => {
    if (!sessionId) { setError('No session in URL.'); setLoading(false); return }
    try {
      const [matchData, citizenData, followupList] = await Promise.all([
        matchSchemes(sessionId),
        getCitizen(sessionId).catch(() => null),
        listFollowups(sessionId).catch(() => [] as FollowupRecord[]),
      ])
      setData(matchData)
      setCitizen(citizenData)
      const map: Record<string, FollowupRecord> = {}
      for (const f of followupList) map[f.scheme_id] = f
      setFollowups(map)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load results.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => { if (workerId) load() }, [workerId, load])

  async function handleFollowup(schemeId: string, schemeName: string, status: FollowupStatus) {
    if (!sessionId) return
    try {
      const record = await setFollowup(sessionId, schemeId, schemeName, status)
      setFollowups((prev) => ({ ...prev, [schemeId]: record }))
    } catch {
      // non-critical — user can retry
    }
  }

  const activeSchemes = useMemo(() => {
    if (!data) return []
    return data[activeTab]
  }, [data, activeTab])

  const filtered = useMemo(() => {
    if (!search) return activeSchemes
    const q = search.toLowerCase()
    return activeSchemes.filter(
      (s) =>
        s.scheme_name.toLowerCase().includes(q) ||
        (s.benefit ?? '').toLowerCase().includes(q) ||
        s.category_display.some((c) => c.toLowerCase().includes(q)),
    )
  }, [activeSchemes, search])

  if (loading) return <LoadingFull />
  if (error) return <ErrorFull message={error} onBack={() => router.push('/assisted/citizens')} />
  if (!data) return null

  const tabs: { key: Tab; label: string; count: number; color: string }[] = [
    { key: 'eligible', label: 'Eligible', count: data.eligible.length, color: 'text-green-700' },
    { key: 'near_miss', label: 'Near Miss', count: data.near_miss.length, color: 'text-amber-700' },
    {
      key: 'insufficient_information',
      label: 'Need Info',
      count: data.insufficient_information.length,
      color: 'text-gray-600',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <Link href="/assisted/citizens" className="text-indigo-600 hover:text-indigo-800 text-sm font-medium flex-shrink-0">
              ← Citizens
            </Link>
            <span className="text-gray-300">|</span>
            <div className="min-w-0">
              <span className="font-bold text-gray-900 text-sm truncate block">
                {citizen ? citizen.citizen_name : 'Results'}
              </span>
            </div>
          </div>
          <Link
            href={`/assisted/interview?session=${sessionId}`}
            className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg font-medium hover:bg-indigo-100 transition-colors flex-shrink-0"
          >
            Continue Interview
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-4 space-y-4">
        {/* Citizen info card */}
        {citizen && (
          <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 flex flex-wrap gap-3 items-center">
            <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-indigo-700 font-bold">
                {citizen.citizen_name.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 text-sm">{citizen.citizen_name}</p>
              {citizen.citizen_phone && (
                <p className="text-gray-400 text-xs">{citizen.citizen_phone}</p>
              )}
            </div>
            {citizen.notes && (
              <p className="text-xs text-gray-500 italic w-full sm:w-auto">{citizen.notes}</p>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { n: data.eligible.length, label: 'Eligible', cls: 'text-green-600 bg-green-50 border-green-200' },
            { n: data.near_miss.length, label: 'Near Miss', cls: 'text-amber-600 bg-amber-50 border-amber-200' },
            { n: data.insufficient_information.length, label: 'Need Info', cls: 'text-gray-500 bg-gray-50 border-gray-200' },
            { n: data.ineligible.length, label: 'Ineligible', cls: 'text-red-400 bg-red-50 border-red-200' },
          ].map(({ n, label, cls }) => (
            <div key={label} className={`rounded-xl border p-2.5 text-center ${cls}`}>
              <div className="text-lg font-extrabold">{n}</div>
              <div className="text-xs font-medium mt-0.5 opacity-75">{label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setSearch('') }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-lg text-sm font-semibold transition-all duration-150 ${
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className={activeTab === tab.key ? tab.color : ''}>{tab.label}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-bold ${
                activeTab === tab.key ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-200 text-gray-500'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search */}
        {activeSchemes.length > 0 && (
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search schemes…"
              className="w-full pl-9 pr-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                ✕
              </button>
            )}
          </div>
        )}

        {/* Empty state */}
        {filtered.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center">
            {search ? (
              <>
                <p className="text-gray-500 text-sm mb-2">No schemes match &quot;{search}&quot;.</p>
                <button onClick={() => setSearch('')} className="text-indigo-600 text-sm underline">Clear</button>
              </>
            ) : (
              <p className="text-gray-500 text-sm">No schemes in this category.</p>
            )}
          </div>
        )}

        {/* Scheme cards */}
        <div className="space-y-3">
          {filtered.map((scheme) => (
            <SchemeCard
              key={scheme.scheme_id}
              scheme={scheme}
              followup={followups[scheme.scheme_id] ?? null}
              tab={activeTab}
              onFollowup={handleFollowup}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="pb-8 pt-2">
          <Link
            href="/assisted/citizens"
            className="block text-center bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            ← Back to Citizens List
          </Link>
        </div>
      </main>
    </div>
  )
}

// ─── Scheme card ──────────────────────────────────────────────────────────────

function SchemeCard({
  scheme,
  followup,
  tab,
  onFollowup,
}: {
  scheme: SchemeMatchResult
  followup: FollowupRecord | null
  tab: Tab
  onFollowup: (id: string, name: string, status: FollowupStatus) => void
}) {
  const [showFollowup, setShowFollowup] = useState(false)
  const [saving, setSaving] = useState(false)

  async function pick(status: FollowupStatus) {
    setSaving(true)
    await onFollowup(scheme.scheme_id, scheme.scheme_name, status)
    setSaving(false)
    setShowFollowup(false)
  }

  const borderColor =
    tab === 'eligible'
      ? 'border-green-100'
      : tab === 'near_miss'
      ? 'border-amber-100'
      : 'border-gray-200'

  const headerColor =
    tab === 'eligible'
      ? 'bg-green-50 border-b border-green-100'
      : tab === 'near_miss'
      ? 'bg-amber-50 border-b border-amber-100'
      : 'bg-gray-50 border-b border-gray-200'

  const verdictLabel =
    tab === 'eligible' ? '✓ Eligible' : tab === 'near_miss' ? '~ Near Miss' : '? Need Info'

  const docs = scheme.required_documents
    ? scheme.required_documents.split(/[,\n]/).map((d) => d.trim()).filter(Boolean)
    : []

  const nearMiss = scheme.explanation?.filter((c) => c.status === 'NEAR_MISS') ?? []
  const notProvided = scheme.explanation?.filter((c) => c.status === 'NOT_PROVIDED') ?? []

  return (
    <div className={`bg-white border ${borderColor} rounded-2xl shadow-sm overflow-hidden`}>
      {/* Header */}
      <div className={`${headerColor} px-4 py-2 flex items-center justify-between gap-2`}>
        <span className="text-xs font-bold text-gray-600">{verdictLabel}</span>
        <span className="text-xs text-gray-400 truncate max-w-[160px]">{scheme.source}</span>
      </div>

      <div className="p-4 space-y-3">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">{scheme.scheme_name}</h3>

        {/* Categories */}
        {scheme.category_display.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {scheme.category_display.slice(0, 3).map((c) => (
              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{c}</span>
            ))}
          </div>
        )}

        {/* Benefit */}
        {scheme.benefit && (
          <p className="text-gray-600 text-xs leading-relaxed line-clamp-2">{scheme.benefit}</p>
        )}

        {/* Near miss gap */}
        {tab === 'near_miss' && nearMiss.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 space-y-1">
            <p className="text-xs font-bold text-amber-800">Gap</p>
            {nearMiss.map((c, i) => (
              <p key={i} className="text-xs text-amber-700">
                {c.label}: {c.citizen_value_display} (need {c.requirement})
                {c.gap && <span className="font-medium"> — {c.gap}</span>}
              </p>
            ))}
          </div>
        )}

        {/* Missing info */}
        {tab === 'insufficient_information' && notProvided.length > 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <p className="text-xs font-bold text-gray-600 mb-1">Missing info</p>
            {notProvided.map((c, i) => (
              <p key={i} className="text-xs text-gray-500">• {c.label}</p>
            ))}
          </div>
        )}

        {/* Required documents */}
        {docs.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1">Documents</p>
            <div className="flex flex-wrap gap-1">
              {docs.slice(0, 4).map((d) => (
                <span key={d} className="text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2 py-0.5 rounded-full">
                  {d}
                </span>
              ))}
              {docs.length > 4 && <span className="text-xs text-gray-400">+{docs.length - 4} more</span>}
            </div>
          </div>
        )}

        {/* Application method */}
        {scheme.application_method && (
          <p className="text-xs text-gray-400">
            <span className="font-medium text-gray-500">Apply: </span>
            {scheme.application_method}
          </p>
        )}

        {/* Follow-up */}
        <div className="pt-2 border-t border-gray-100 flex items-center justify-between gap-2">
          {followup ? (
            <div className="flex items-center gap-2">
              <span className={`text-xs border px-2.5 py-1 rounded-full font-semibold ${STATUS_COLORS[followup.status]}`}>
                {STATUS_LABELS[followup.status]}
              </span>
              <button
                onClick={() => setShowFollowup((v) => !v)}
                className="text-xs text-gray-400 hover:text-gray-600 underline"
              >
                Change
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowFollowup((v) => !v)}
              className="text-xs bg-white border border-gray-300 text-gray-600 hover:bg-gray-50 px-3 py-1.5 rounded-lg font-medium transition-colors"
            >
              + Set Follow-up
            </button>
          )}

          {scheme.official_website && (
            <a
              href={scheme.official_website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              Official Site →
            </a>
          )}
        </div>

        {/* Follow-up picker */}
        {showFollowup && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-2">
            <p className="text-xs font-semibold text-gray-600">Update Status</p>
            <div className="flex flex-wrap gap-2">
              {(Object.entries(STATUS_LABELS) as [FollowupStatus, string][]).map(([s, label]) => (
                <button
                  key={s}
                  disabled={saving}
                  onClick={() => pick(s)}
                  className={`text-xs border px-2.5 py-1 rounded-full font-medium transition-colors disabled:opacity-50 ${
                    followup?.status === s
                      ? STATUS_COLORS[s]
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {saving && followup?.status === s ? '…' : label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowFollowup(false)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Utility components ───────────────────────────────────────────────────────

function LoadingFull() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <svg className="animate-spin w-10 h-10 text-indigo-400" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  )
}

function ErrorFull({ message, onBack }: { message: string; onBack: () => void }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white border border-red-200 rounded-2xl px-8 py-8 text-center max-w-sm shadow-sm">
        <div className="text-4xl mb-3">⚠</div>
        <h2 className="text-red-800 font-semibold mb-2">Something went wrong</h2>
        <p className="text-red-600 text-sm mb-5">{message}</p>
        <button
          onClick={onBack}
          className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          Back to Citizens
        </button>
      </div>
    </div>
  )
}

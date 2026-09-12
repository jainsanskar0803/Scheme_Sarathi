'use client'

import { useEffect, useState, Suspense } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import type { SchemeMatchResult, MatchResponse, ConditionExplanation, ConditionStatus, Verdict } from '@/lib/types'
import { useLanguage } from '@/lib/use-language'
import { LangToggle } from '@/lib/lang-toggle'
import { t } from '@/lib/translations'
import type { Lang } from '@/lib/translations'

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function SchemeDetailPage() {
  const { lang, toggle } = useLanguage()
  return (
    <Suspense fallback={<Spinner />}>
      <SchemeDetailContent lang={lang} onToggleLang={toggle} />
    </Suspense>
  )
}

// ─── Data loader ──────────────────────────────────────────────────────────────

function SchemeDetailContent({ lang, onToggleLang }: { lang: Lang; onToggleLang: () => void }) {
  const T = t(lang)
  const params = useParams()
  const searchParams = useSearchParams()
  const schemeId = params.id as string
  const sessionId = searchParams.get('session') || ''

  const [scheme, setScheme] = useState<SchemeMatchResult | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    try {
      const cached = sessionStorage.getItem('match_results')
      if (!cached) { setNotFound(true); return }
      const data = JSON.parse(cached) as MatchResponse
      const found = [
        ...data.eligible,
        ...data.near_miss,
        ...data.insufficient_information,
        ...data.ineligible,
      ].find((s) => s.scheme_id === schemeId)
      found ? setScheme(found) : setNotFound(true)
    } catch {
      setNotFound(true)
    }
  }, [schemeId])

  if (notFound) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white border border-gray-200 rounded-2xl px-8 py-10 text-center max-w-md shadow-sm">
          <div className="text-5xl mb-4">🔍</div>
          <h2 className="text-gray-800 font-semibold text-lg mb-2">{T.schemeNotFound}</h2>
          <p className="text-gray-500 text-sm mb-6">{T.schemeNotFoundBody}</p>
          <Link
            href={sessionId ? `/results?session=${sessionId}` : '/'}
            className="inline-flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            {T.returnToResults}
          </Link>
        </div>
      </div>
    )
  }

  if (!scheme) return <Spinner />

  return <SchemeDetail scheme={scheme} sessionId={sessionId} lang={lang} onToggleLang={onToggleLang} />
}

// ─── Main detail view ─────────────────────────────────────────────────────────

function SchemeDetail({
  scheme,
  sessionId,
  lang,
  onToggleLang,
}: {
  scheme: SchemeMatchResult
  sessionId: string
  lang: Lang
  onToggleLang: () => void
}) {
  const T = t(lang)
  const verdict = scheme.verdict
  const isStateScheme = scheme.source.startsWith('State Government')
  const stateName = isStateScheme
    ? scheme.source.replace('State Government – ', '').replace('State Government', '').trim()
    : null

  const conditions = dedupeConditions(scheme.explanation)
  const passCount = conditions.filter((c) => c.status === 'PASS').length
  const failCount = conditions.filter((c) => c.status === 'FAIL').length
  const nearMissCount = conditions.filter((c) => c.status === 'NEAR_MISS').length
  const notProvidedCount = conditions.filter((c) => c.status === 'NOT_PROVIDED').length
  const totalChecked = conditions.length

  const docLines = parseDocuments(scheme.required_documents)
  const appSteps = parseApplicationSteps(scheme.application_method)
  const hasWebsite = scheme.official_website && scheme.official_website !== 'None' && scheme.official_website !== 'null'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sticky header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-2 min-w-0">
          <Link
            href={sessionId ? `/results?session=${sessionId}` : '/'}
            className="flex-shrink-0 text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center gap-1"
          >
            {T.backResultsHeader}
          </Link>
          <span className="text-gray-300 flex-shrink-0">|</span>
          <span className="text-gray-600 text-sm truncate flex-1">{scheme.scheme_name}</span>
          <LangToggle lang={lang} onToggle={onToggleLang} />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-5 space-y-4 pb-12">

        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2">
            <VerdictBadge verdict={verdict} lang={lang} />
            <span className="text-xs bg-indigo-50 text-indigo-600 border border-indigo-100 px-2.5 py-1 rounded-full font-medium">
              {isStateScheme ? T.stateGovt : T.centralGovt} Government
            </span>
            {scheme.category_display.map((c) => (
              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-2.5 py-1 rounded-full">
                {c}
              </span>
            ))}
          </div>

          {/* Name */}
          <h1 className="text-gray-900 font-bold text-xl leading-snug">{scheme.scheme_name}</h1>

          {/* State info */}
          {stateName && (
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <span>📍</span>
              <span>{T.availableIn} <span className="font-medium text-gray-700">{stateName}</span></span>
            </div>
          )}

          {/* Benefit */}
          {scheme.benefit && (
            <div className={`rounded-xl p-4 border ${benefitStyle(verdict)}`}>
              <p className={`text-xs font-bold uppercase tracking-wide mb-1 ${benefitLabelStyle(verdict)}`}>{T.benefit}</p>
              <p className={`text-sm leading-relaxed ${benefitTextStyle(verdict)}`}>{scheme.benefit}</p>
            </div>
          )}
        </div>

        {/* ── Eligibility Assessment ────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          {/* Verdict headline */}
          <div className={`px-5 py-4 border-b ${verdictHeaderBg(verdict)}`}>
            <div className="flex items-start gap-3">
              <span className="text-2xl flex-shrink-0 mt-0.5">{verdictIcon(verdict)}</span>
              <div>
                <p className={`font-bold text-base ${verdictTitleColor(verdict)}`}>
                  {getVerdictHeadline(T, verdict, passCount, totalChecked, failCount, nearMissCount)}
                </p>
                {totalChecked > 0 && (
                  <p className="text-sm text-gray-500 mt-0.5">
                    {T.conditionsSummary(passCount, totalChecked)}
                    {failCount > 0 && <span className="text-red-500"> · {T.conditionFailed(failCount)}</span>}
                    {nearMissCount > 0 && <span className="text-amber-500"> · {T.conditionClose(nearMissCount)}</span>}
                    {notProvidedCount > 0 && <span className="text-gray-400"> · {T.conditionUnknown(notProvidedCount)}</span>}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Conditions */}
          {conditions.length > 0 && (
            <div className="divide-y divide-gray-100">
              {conditions.map((cond, i) => (
                <ConditionRow key={`${cond.field}-${cond.requirement}-${i}`} condition={cond} sessionId={sessionId} lang={lang} />
              ))}
            </div>
          )}

          {conditions.length === 0 && (
            <div className="px-5 py-6 text-center text-gray-400 text-sm">
              {T.noConditions}
            </div>
          )}
        </div>

        {/* ── Additional Criteria ───────────────────────────────────────────── */}
        {scheme.unverified_criteria && scheme.unverified_criteria.length > 0 && (
          <Section title={T.additionalCriteria} icon="⚠️" accent="amber">
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-3">
              {T.additionalCriteriaNote}
            </p>
            <ul className="space-y-2">
              {scheme.unverified_criteria.map((c, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-gray-700">
                  <span className="text-amber-400 flex-shrink-0 mt-0.5">•</span>
                  <span className="leading-relaxed">{c}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* ── Missing Profile Info ──────────────────────────────────────────── */}
        {scheme.missing_information && scheme.missing_information.length > 0 && notProvidedCount > 0 && (
          <Section title={T.completeYourProfile} icon="👤" accent="indigo">
            <p className="text-sm text-gray-600 mb-3">{T.completeProfileNote}</p>
            <div className="flex flex-wrap gap-2 mb-4">
              {conditions
                .filter((c) => c.status === 'NOT_PROVIDED')
                .map((c, i) => (
                  <span key={i} className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 px-3 py-1.5 rounded-full font-medium">
                    {c.label}
                  </span>
                ))}
            </div>
            <Link
              href={sessionId ? `/interview?session=${sessionId}` : '/interview'}
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-800"
            >
              {T.completeProfileLink}
            </Link>
          </Section>
        )}

        {/* ── Required Documents ────────────────────────────────────────────── */}
        {docLines.length > 0 && (
          <Section title={T.requiredDocuments} icon="📄">
            <ul className="space-y-2 mb-4">
              {docLines.map((doc, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-gray-700">
                  <span className="text-gray-300 flex-shrink-0 mt-1 text-xs">▸</span>
                  <span className="leading-relaxed">{doc}</span>
                </li>
              ))}
            </ul>
            <Link
              href={sessionId ? `/documents?session=${sessionId}&scheme=${scheme.scheme_id}` : `/documents?scheme=${scheme.scheme_id}`}
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            >
              <span>📋</span>
              {T.checkMyDocuments}
            </Link>
          </Section>
        )}

        {/* ── How to Apply ──────────────────────────────────────────────────── */}
        {appSteps.length > 0 && (
          <Section title={T.howToApply} icon="📝">
            {appSteps.length === 1 ? (
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{appSteps[0]}</p>
            ) : (
              <ol className="space-y-3">
                {appSteps.map((step, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold flex items-center justify-center mt-0.5">
                      {i + 1}
                    </span>
                    <span className="text-sm text-gray-700 leading-relaxed">{step}</span>
                  </li>
                ))}
              </ol>
            )}
          </Section>
        )}

        {/* ── Official Website ──────────────────────────────────────────────── */}
        {hasWebsite && (
          <Section title={T.officialWebsite} icon="🌐">
            <a
              href={scheme.official_website!}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-indigo-600 hover:text-indigo-800 text-sm font-medium break-all underline underline-offset-2"
            >
              {scheme.official_website}
              <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </Section>
        )}

        {/* ── Source ───────────────────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm px-5 py-4">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-1">{T.sourceLabel}</p>
          <p className="text-sm text-gray-700 font-medium">{scheme.source}</p>
          <p className="text-xs text-gray-400 mt-1">{T.schemeIdLabel} {scheme.scheme_id}</p>
        </div>

        {/* ── Back ─────────────────────────────────────────────────────────── */}
        <Link
          href={sessionId ? `/results?session=${sessionId}` : '/'}
          className="inline-flex items-center gap-2 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 px-5 py-2.5 rounded-xl text-sm font-medium transition-colors shadow-sm"
        >
          {T.backToResultsBtn}
        </Link>
      </main>
    </div>
  )
}

// ─── Condition Row ────────────────────────────────────────────────────────────

function ConditionRow({ condition, sessionId, lang }: { condition: ConditionExplanation; sessionId: string; lang: Lang }) {
  const T = t(lang)
  const { status } = condition

  const rowBg: Record<ConditionStatus, string> = {
    PASS: 'bg-green-50/40',
    FAIL: 'bg-red-50/40',
    NEAR_MISS: 'bg-amber-50/40',
    NOT_PROVIDED: 'bg-gray-50/60',
  }

  const borderLeft: Record<ConditionStatus, string> = {
    PASS: 'border-l-2 border-green-400',
    FAIL: 'border-l-2 border-red-400',
    NEAR_MISS: 'border-l-2 border-amber-400',
    NOT_PROVIDED: 'border-l-2 border-gray-300',
  }

  return (
    <div className={`px-4 py-3.5 ${rowBg[status]} ${borderLeft[status]}`}>
      {/* Top row: label + status */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-800">{condition.label}</span>
        <StatusBadge status={status} lang={lang} />
      </div>

      {/* Requirement + citizen value */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs">
        <div>
          <span className="text-gray-400 font-medium">{T.requirement} </span>
          <span className="text-gray-700">{condition.requirement}</span>
        </div>
        <div>
          <span className="text-gray-400 font-medium">{T.yourValueLabel} </span>
          {condition.citizen_value_display && condition.citizen_value_display !== 'Not provided' ? (
            <span className={`font-semibold ${status === 'PASS' ? 'text-green-700' : status === 'FAIL' ? 'text-red-700' : status === 'NEAR_MISS' ? 'text-amber-700' : 'text-gray-400'}`}>
              {condition.citizen_value_display}
            </span>
          ) : (
            <span className="text-gray-400 italic">{T.notProvided}</span>
          )}
        </div>
      </div>

      {/* Near-miss gap + note */}
      {status === 'NEAR_MISS' && (condition.gap || condition.note) && (
        <div className="mt-2.5 bg-amber-100 border border-amber-200 rounded-lg px-3 py-2 space-y-0.5">
          {condition.gap && (
            <p className="text-xs font-bold text-amber-800">
              {T.gap} {condition.gap}
            </p>
          )}
          {condition.note && condition.note !== condition.gap && (
            <p className="text-xs text-amber-700">{condition.note}</p>
          )}
        </div>
      )}

      {/* FAIL reason */}
      {status === 'FAIL' && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className="text-red-400 text-xs">✗</span>
          <p className="text-xs text-red-600">{T.failReason}</p>
        </div>
      )}

      {/* NOT_PROVIDED hint */}
      {status === 'NOT_PROVIDED' && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className="text-gray-400 text-xs">?</span>
          <p className="text-xs text-gray-500">
            {T.notInProfile}{' '}
            <Link href={sessionId ? `/interview?session=${sessionId}` : '/interview'} className="text-indigo-500 hover:text-indigo-700 underline underline-offset-1">
              {T.addIt}
            </Link>
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({
  title,
  icon,
  children,
  accent = 'gray',
}: {
  title: string
  icon: string
  children: React.ReactNode
  accent?: 'gray' | 'amber' | 'indigo'
}) {
  const headerBg = { gray: 'bg-gray-50', amber: 'bg-amber-50', indigo: 'bg-indigo-50' }[accent]
  const headerBorder = { gray: 'border-gray-200', amber: 'border-amber-100', indigo: 'border-indigo-100' }[accent]

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      <div className={`px-5 py-3.5 border-b ${headerBg} ${headerBorder}`}>
        <h2 className="text-gray-900 font-bold text-sm flex items-center gap-2">
          <span>{icon}</span>
          {title}
        </h2>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  )
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status, lang }: { status: ConditionStatus; lang: Lang }) {
  const T = t(lang)
  const cfg: Record<ConditionStatus, { cls: string; label: string }> = {
    PASS:         { cls: 'bg-green-100 text-green-700', label: T.statusPass },
    FAIL:         { cls: 'bg-red-100 text-red-700',     label: T.statusFail },
    NEAR_MISS:    { cls: 'bg-amber-100 text-amber-700', label: T.statusClose },
    NOT_PROVIDED: { cls: 'bg-gray-100 text-gray-500',  label: T.statusUnknown },
  }
  const { cls, label } = cfg[status] ?? { cls: 'bg-gray-100 text-gray-500', label: status }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

// ─── Verdict Badge ────────────────────────────────────────────────────────────

function VerdictBadge({ verdict, lang }: { verdict: Verdict | string; lang: Lang }) {
  const T = t(lang)
  const cfg: Record<string, { cls: string; label: string }> = {
    eligible:                 { cls: 'bg-green-100 text-green-700 border-green-200',  label: T.verdictEligible },
    near_miss:                { cls: 'bg-amber-100 text-amber-700 border-amber-200',  label: T.verdictNearMiss },
    insufficient_information: { cls: 'bg-gray-100 text-gray-600 border-gray-200',    label: T.verdictNeedInfo },
    ineligible:               { cls: 'bg-red-100 text-red-700 border-red-200',        label: T.verdictIneligible },
  }
  const { cls, label } = cfg[verdict] ?? { cls: 'bg-gray-100 text-gray-500 border-gray-200', label: verdict }
  return (
    <span className={`inline-flex items-center text-sm font-bold px-3 py-1 rounded-full border ${cls}`}>
      {label}
    </span>
  )
}

// ─── Spinner ──────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <svg className="animate-spin w-10 h-10 text-indigo-500" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  )
}

// ─── Verdict helpers ──────────────────────────────────────────────────────────

function verdictIcon(v: string): string {
  return { eligible: '✅', near_miss: '⚡', ineligible: '❌', insufficient_information: '🔍' }[v] ?? '📋'
}

function getVerdictHeadline(
  T: ReturnType<typeof t>,
  v: string,
  pass: number,
  total: number,
  fail: number,
  near: number,
): string {
  switch (v) {
    case 'eligible':
      return total > 0 ? T.verdictHeadlineEligible(total) : T.verdictHeadlineEligibleZero
    case 'near_miss':
      return T.verdictHeadlineNearMiss(near)
    case 'ineligible':
      return T.verdictHeadlineIneligible(fail)
    case 'insufficient_information':
      return T.verdictHeadlineInsufficient
    default:
      return T.verdictDefault
  }
}

function verdictHeaderBg(v: string): string {
  return {
    eligible: 'bg-green-50 border-green-100',
    near_miss: 'bg-amber-50 border-amber-100',
    ineligible: 'bg-red-50 border-red-100',
    insufficient_information: 'bg-gray-50 border-gray-200',
  }[v] ?? 'bg-gray-50 border-gray-200'
}

function verdictTitleColor(v: string): string {
  return {
    eligible: 'text-green-800',
    near_miss: 'text-amber-800',
    ineligible: 'text-red-800',
    insufficient_information: 'text-gray-700',
  }[v] ?? 'text-gray-800'
}

function benefitStyle(v: string): string {
  return {
    eligible: 'bg-green-50 border-green-200',
    near_miss: 'bg-amber-50 border-amber-200',
    ineligible: 'bg-gray-50 border-gray-200',
    insufficient_information: 'bg-blue-50 border-blue-100',
  }[v] ?? 'bg-gray-50 border-gray-200'
}

function benefitLabelStyle(v: string): string {
  return {
    eligible: 'text-green-700',
    near_miss: 'text-amber-700',
    ineligible: 'text-gray-500',
    insufficient_information: 'text-blue-600',
  }[v] ?? 'text-gray-500'
}

function benefitTextStyle(v: string): string {
  return {
    eligible: 'text-green-900',
    near_miss: 'text-amber-900',
    ineligible: 'text-gray-700',
    insufficient_information: 'text-blue-900',
  }[v] ?? 'text-gray-700'
}

// ─── Parsing helpers ──────────────────────────────────────────────────────────

function dedupeConditions(conditions: ConditionExplanation[]): ConditionExplanation[] {
  const seen = new Set<string>()
  return conditions.filter((c) => {
    const key = `${c.field}|${c.requirement}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function parseDocuments(raw: string | null | undefined): string[] {
  if (!raw || raw === 'None') return []
  const byNewline = raw.split('\n').map((s) => s.trim()).filter(Boolean)
  if (byNewline.length > 1) return byNewline
  const byPeriod = raw.split('. ').map((s) => s.trim()).filter(Boolean)
  if (byPeriod.length > 1) return byPeriod
  return [raw.trim()]
}

function parseApplicationSteps(raw: string | null | undefined): string[] {
  if (!raw || raw === 'None') return []
  const stepPattern = /Step\s+\d+\s*:/gi
  const parts = raw.split(stepPattern).map((s) => s.trim()).filter(Boolean)
  if (parts.length > 1) return parts
  const numbered = raw.split(/\n\s*\d+\.\s+/).map((s) => s.trim()).filter(Boolean)
  if (numbered.length > 1) return numbered
  const byNewline = raw.split('\n').map((s) => s.trim()).filter(Boolean)
  if (byNewline.length > 1) return byNewline
  return [raw.trim()]
}

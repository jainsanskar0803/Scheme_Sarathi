import type { SchemeMatchResult, ConditionExplanation } from './types'
import { translateTexts } from './api'

const CACHE_PREFIX = 'tr_hi_'

function cacheKey(schemeId: string) {
  return `${CACHE_PREFIX}${schemeId}`
}

function readCache(schemeId: string): SchemeMatchResult | null {
  try {
    const raw = sessionStorage.getItem(cacheKey(schemeId))
    return raw ? (JSON.parse(raw) as SchemeMatchResult) : null
  } catch {
    return null
  }
}

function writeCache(scheme: SchemeMatchResult) {
  try {
    sessionStorage.setItem(cacheKey(scheme.scheme_id), JSON.stringify(scheme))
  } catch {
    // ignore quota errors
  }
}

// Collect every translatable string in a flat ordered list.
// Returns [texts, applyFn] where applyFn maps translated strings back.
function buildBatch(scheme: SchemeMatchResult): {
  texts: (string | null)[]
  apply: (translations: (string | null)[]) => SchemeMatchResult
} {
  const texts: (string | null)[] = []

  // Top-level fields
  texts.push(scheme.scheme_name)            // 0
  texts.push(scheme.benefit)                // 1
  texts.push(scheme.required_documents)     // 2
  texts.push(scheme.application_method)     // 3

  // category_display items
  const catStart = texts.length
  scheme.category_display.forEach((c) => texts.push(c))

  // tags
  const tagStart = texts.length
  scheme.tags.forEach((t) => texts.push(t))

  // unverified_criteria
  const uvStart = texts.length
  scheme.unverified_criteria.forEach((u) => texts.push(u))

  // missing_information
  const miStart = texts.length
  scheme.missing_information.forEach((m) => texts.push(m))

  // explanation rows: label, requirement, citizen_value_display, gap, note
  const expStart = texts.length
  scheme.explanation.forEach((e) => {
    texts.push(e.label)
    texts.push(e.requirement)
    texts.push(e.citizen_value_display)
    texts.push(e.gap)
    texts.push(e.note)
  })

  function apply(tr: (string | null)[]): SchemeMatchResult {
    const get = (i: number): string | null => tr[i] ?? null

    const newExp: ConditionExplanation[] = scheme.explanation.map((e, i) => ({
      ...e,
      label: get(expStart + i * 5 + 0) ?? e.label,
      requirement: get(expStart + i * 5 + 1) ?? e.requirement,
      citizen_value_display: get(expStart + i * 5 + 2) ?? e.citizen_value_display,
      gap: get(expStart + i * 5 + 3),
      note: get(expStart + i * 5 + 4),
    }))

    return {
      ...scheme,
      scheme_name: (get(0) ?? scheme.scheme_name) as string,
      benefit: (get(1) ?? scheme.benefit) as string,
      required_documents: get(2),
      application_method: get(3),
      category_display: scheme.category_display.map((_, i) => get(catStart + i) ?? scheme.category_display[i]),
      tags: scheme.tags.map((_, i) => get(tagStart + i) ?? scheme.tags[i]),
      unverified_criteria: scheme.unverified_criteria.map((_, i) => get(uvStart + i) ?? scheme.unverified_criteria[i]),
      missing_information: scheme.missing_information.map((_, i) => get(miStart + i) ?? scheme.missing_information[i]),
      explanation: newExp,
    }
  }

  return { texts, apply }
}

export async function translateScheme(scheme: SchemeMatchResult): Promise<SchemeMatchResult> {
  const cached = readCache(scheme.scheme_id)
  if (cached) return cached

  const { texts, apply } = buildBatch(scheme)
  const translations = await translateTexts(texts)
  const translated = apply(translations)
  writeCache(translated)
  return translated
}

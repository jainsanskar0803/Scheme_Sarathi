'use client'

import { useEffect, useRef, useState, Suspense, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { verifyDocument } from '@/lib/api'
import type { VerifyResponse } from '@/lib/api'
import type { MatchResponse, SchemeMatchResult } from '@/lib/types'

// ─── Types ────────────────────────────────────────────────────────────────────

// Status flow:
//   missing → uploading → rejected (not a doc or wrong type)
//                       → mismatch (right type, details don't match profile)
//                       → unverified (right type, details not readable / no profile)
//                       → confirmed (right type + all verifiable details match)
type DocStatus = 'missing' | 'uploading' | 'rejected' | 'mismatch' | 'unverified' | 'confirmed'

interface DocItem {
  label: string
  status: DocStatus
  preview: string | null   // image data URL (null for PDFs or no upload)
  fileName: string | null
  isPdf: boolean
  verifyResult: VerifyResponse | null
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <DocumentsContent />
    </Suspense>
  )
}

// ─── Content ──────────────────────────────────────────────────────────────────

function DocumentsContent() {
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session') || ''
  const schemeId = searchParams.get('scheme') || ''

  const [scheme, setScheme] = useState<SchemeMatchResult | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [docs, setDocs] = useState<DocItem[]>([])

  useEffect(() => {
    try {
      const cached = sessionStorage.getItem('match_results')
      if (!cached) { setNotFound(true); return }
      const data = JSON.parse(cached) as MatchResponse
      const found = [
        ...data.eligible,
        ...data.near_miss,
        ...data.insufficient_information,
        ...(data.ineligible ?? []),
      ].find((s) => s.scheme_id === schemeId)
      if (!found) { setNotFound(true); return }
      setScheme(found)

      const required = parseRequiredDocuments(found.required_documents)
      if (required.length === 0) { setNotFound(true); return }
      setDocs(required.map((label) => ({
        label,
        status: 'missing',
        preview: null,
        fileName: null,
        isPdf: false,
        verifyResult: null,
      })))
    } catch {
      setNotFound(true)
    }
  }, [schemeId])

  const updateDoc = useCallback((index: number, patch: Partial<DocItem>) => {
    setDocs((prev) => prev.map((d, i) => i === index ? { ...d, ...patch } : d))
  }, [])

  if (notFound) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white border border-gray-200 rounded-2xl px-8 py-10 text-center max-w-md shadow-sm">
          <div className="text-5xl mb-4">📄</div>
          <h2 className="text-gray-800 font-semibold text-lg mb-2">No document list found</h2>
          <p className="text-gray-500 text-sm mb-6">
            This scheme may not have a required documents list, or your session has expired.
          </p>
          <Link
            href={sessionId ? `/results?session=${sessionId}` : '/results'}
            className="inline-flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            ← Back to Results
          </Link>
        </div>
      </div>
    )
  }

  if (!scheme) return <Spinner />

  const confirmed = docs.filter((d) => d.status === 'confirmed').length
  const total = docs.length
  const allDone = confirmed === total && total > 0

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sticky header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-2 min-w-0">
          <Link
            href={sessionId ? `/scheme/${schemeId}?session=${sessionId}` : `/scheme/${schemeId}`}
            className="flex-shrink-0 text-indigo-600 hover:text-indigo-800 text-sm font-medium"
          >
            ← Scheme Details
          </Link>
          <span className="text-gray-300 flex-shrink-0">|</span>
          <span className="text-gray-600 text-sm truncate">{scheme.scheme_name}</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-5 space-y-4 pb-12">

        {/* ── Title + progress ───────────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-3">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center text-xl flex-shrink-0">
              🔍
            </div>
            <div>
              <h1 className="text-gray-900 font-bold text-lg leading-snug">Document Verification</h1>
              <p className="text-gray-500 text-sm mt-0.5 leading-relaxed">
                Upload each document. We verify the type and check that the details match your profile.
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="text-gray-500">{confirmed} of {total} verified</span>
              {allDone && <span className="text-green-600 font-semibold">All documents verified!</span>}
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${allDone ? 'bg-green-500' : 'bg-indigo-500'}`}
                style={{ width: total > 0 ? `${(confirmed / total) * 100}%` : '0%' }}
              />
            </div>
          </div>
        </div>

        {/* ── Disclaimer ─────────────────────────────────────────────────────── */}
        <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <span className="text-amber-500 flex-shrink-0 mt-0.5 text-base">⚠</span>
          <p className="text-xs text-amber-700 leading-relaxed">
            <span className="font-semibold">Notice:</span> Verification is based on visual features only.
            Scheme Sarathi does not connect to any government database and cannot confirm document authenticity.
            Always verify with the scheme authority.
          </p>
        </div>

        {/* ── Document cards ─────────────────────────────────────────────────── */}
        <div className="space-y-3">
          {docs.map((doc, i) => (
            <DocCard
              key={doc.label}
              doc={doc}
              sessionId={sessionId}
              onUpdate={(patch) => updateDoc(i, patch)}
            />
          ))}
        </div>

        {/* ── Back ───────────────────────────────────────────────────────────── */}
        <Link
          href={sessionId ? `/scheme/${schemeId}?session=${sessionId}` : `/scheme/${schemeId}`}
          className="inline-flex items-center gap-2 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 px-5 py-2.5 rounded-xl text-sm font-medium transition-colors shadow-sm"
        >
          ← Back to Scheme Details
        </Link>
      </main>
    </div>
  )
}

// ─── DocCard ──────────────────────────────────────────────────────────────────

function DocCard({
  doc,
  sessionId,
  onUpdate,
}: {
  doc: DocItem
  sessionId: string
  onUpdate: (patch: Partial<DocItem>) => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    const isPdf = file.type === 'application/pdf'
    const isImage = file.type.startsWith('image/')
    if (!isPdf && !isImage) return

    // Image preview
    if (isImage) {
      const reader = new FileReader()
      reader.onload = (e) => onUpdate({ preview: e.target?.result as string })
      reader.readAsDataURL(file)
    }

    onUpdate({ status: 'uploading', fileName: file.name, isPdf, verifyResult: null, preview: isPdf ? null : undefined })

    const base64 = await fileToBase64(file)

    try {
      const result = await verifyDocument(base64, file.type, doc.label, sessionId || null)

      let newStatus: DocStatus
      if (!result.is_real_document || !result.type_match) {
        newStatus = 'rejected'
      } else if (result.overall_verified) {
        newStatus = 'confirmed'
      } else {
        const hasMismatch = result.field_checks.some((f) => f.match === false)
        newStatus = hasMismatch ? 'mismatch' : 'unverified'
      }

      onUpdate({ status: newStatus, verifyResult: result })
    } catch {
      onUpdate({
        status: 'rejected',
        verifyResult: {
          is_real_document: false,
          identified_type: 'Unknown',
          confidence: 'low',
          type_match: false,
          extracted_fields: {},
          field_checks: [],
          overall_verified: false,
          rejection_reason: 'Verification failed. Please check your internet connection and try again.',
          disclaimer: '',
        },
      })
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleReset() {
    onUpdate({ status: 'missing', preview: null, fileName: null, isPdf: false, verifyResult: null })
  }

  const borderCls: Record<DocStatus, string> = {
    missing:    'border-gray-200',
    uploading:  'border-indigo-200',
    rejected:   'border-red-300',
    mismatch:   'border-amber-300',
    unverified: 'border-blue-200',
    confirmed:  'border-green-300',
  }

  const badgeCls: Record<DocStatus, string> = {
    missing:    'bg-gray-100 text-gray-500',
    uploading:  'bg-indigo-100 text-indigo-600',
    rejected:   'bg-red-100 text-red-700',
    mismatch:   'bg-amber-100 text-amber-700',
    unverified: 'bg-blue-100 text-blue-700',
    confirmed:  'bg-green-100 text-green-700',
  }

  const badgeLabel: Record<DocStatus, string> = {
    missing:    'Missing',
    uploading:  'Verifying…',
    rejected:   'Rejected',
    mismatch:   'Details Mismatch',
    unverified: 'Needs Confirmation',
    confirmed:  'Verified',
  }

  return (
    <div className={`bg-white rounded-2xl border ${borderCls[doc.status]} shadow-sm overflow-hidden`}>
      {/* Card header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/60">
        <div className="flex items-center gap-2 min-w-0">
          <StatusIcon status={doc.status} />
          <span className="text-sm font-semibold text-gray-800 truncate">{doc.label}</span>
        </div>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0 ${badgeCls[doc.status]}`}>
          {badgeLabel[doc.status]}
        </span>
      </div>

      <div className="p-4 space-y-3">

        {/* Missing — upload zone */}
        {doc.status === 'missing' && (
          <UploadZone onFile={handleFile} onDrop={handleDrop} fileRef={fileRef} />
        )}

        {/* Uploading */}
        {doc.status === 'uploading' && (
          <div className="flex items-center gap-3 py-3">
            <svg className="animate-spin w-5 h-5 text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-gray-700">Verifying document…</p>
              <p className="text-xs text-gray-400">{doc.fileName}</p>
            </div>
          </div>
        )}

        {/* ── Rejected ──────────────────────────────────────────────────────── */}
        {doc.status === 'rejected' && doc.verifyResult && (
          <div className="space-y-3">
            <PreviewRow doc={doc} />
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-red-500 text-base">✗</span>
                <p className="text-sm font-semibold text-red-800">
                  {doc.verifyResult.is_real_document ? 'Wrong Document Type' : 'Not a Valid Document'}
                </p>
              </div>
              {doc.verifyResult.rejection_reason && (
                <p className="text-xs text-red-700 leading-relaxed pl-6">
                  {doc.verifyResult.rejection_reason}
                </p>
              )}
              {doc.verifyResult.identified_type && doc.verifyResult.identified_type !== 'Unknown' && (
                <p className="text-xs text-red-600 pl-6">
                  Detected: <span className="font-medium">{doc.verifyResult.identified_type}</span>
                  {' '}({doc.verifyResult.confidence} confidence)
                </p>
              )}
            </div>
            <button
              onClick={handleReset}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            >
              Upload Correct Document
            </button>
          </div>
        )}

        {/* ── Mismatch ──────────────────────────────────────────────────────── */}
        {doc.status === 'mismatch' && doc.verifyResult && (
          <div className="space-y-3">
            <PreviewRow doc={doc} />
            <TypeMatchBadge result={doc.verifyResult} />
            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 space-y-1">
              <p className="text-xs font-semibold text-amber-800">Details don&apos;t fully match your profile</p>
              <p className="text-xs text-amber-700 leading-relaxed">{doc.verifyResult.rejection_reason}</p>
            </div>
            <FieldChecksTable checks={doc.verifyResult.field_checks} />
            <ExtractedFieldsRow extracted={doc.verifyResult.extracted_fields} />
            <div className="flex gap-2">
              <button
                onClick={() => onUpdate({ status: 'confirmed' })}
                className="flex-1 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium px-3 py-2.5 rounded-xl transition-colors"
              >
                Confirm Anyway
              </button>
              <button
                onClick={handleReset}
                className="bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm px-3 py-2.5 rounded-xl transition-colors"
              >
                Replace
              </button>
            </div>
          </div>
        )}

        {/* ── Unverified (right type, details not readable / no profile) ─────── */}
        {doc.status === 'unverified' && doc.verifyResult && (
          <div className="space-y-3">
            <PreviewRow doc={doc} />
            <TypeMatchBadge result={doc.verifyResult} />
            {doc.verifyResult.field_checks.length > 0 && (
              <FieldChecksTable checks={doc.verifyResult.field_checks} />
            )}
            <ExtractedFieldsRow extracted={doc.verifyResult.extracted_fields} />
            {doc.verifyResult.field_checks.length === 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
                <p className="text-xs text-blue-700">
                  Document type matches. Some fields couldn&apos;t be verified — confirm if this is the correct document.
                </p>
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => onUpdate({ status: 'confirmed' })}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-3 py-2.5 rounded-xl transition-colors"
              >
                ✓ Confirm Document
              </button>
              <button
                onClick={handleReset}
                className="bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm px-3 py-2.5 rounded-xl transition-colors"
              >
                Replace
              </button>
            </div>
          </div>
        )}

        {/* ── Confirmed ─────────────────────────────────────────────────────── */}
        {doc.status === 'confirmed' && doc.verifyResult && (
          <div className="space-y-3">
            <PreviewRow doc={doc} />
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
              <span className="text-green-600 text-lg">✓</span>
              <div>
                <p className="text-sm font-semibold text-green-800">
                  {doc.verifyResult.identified_type} verified
                </p>
                {doc.verifyResult.field_checks.filter((f) => f.match === true).length > 0 && (
                  <p className="text-xs text-green-600">
                    {doc.verifyResult.field_checks.filter((f) => f.match === true).map((f) => f.label).join(' · ')} matched
                  </p>
                )}
              </div>
            </div>
            {doc.verifyResult.field_checks.length > 0 && (
              <FieldChecksTable checks={doc.verifyResult.field_checks} />
            )}
            <button
              onClick={handleReset}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors underline underline-offset-2"
            >
              Remove and re-upload
            </button>
          </div>
        )}

      </div>
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function PreviewRow({ doc }: { doc: DocItem }) {
  if (!doc.fileName) return null
  return (
    <div className="flex items-center gap-3">
      {doc.isPdf ? (
        <div className="w-12 h-12 rounded-lg border border-gray-200 bg-red-50 flex items-center justify-center text-xl flex-shrink-0">
          📑
        </div>
      ) : doc.preview ? (
        <div className="w-12 h-12 rounded-lg border border-gray-200 overflow-hidden flex-shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={doc.preview} alt="preview" className="w-full h-full object-cover" />
        </div>
      ) : null}
      <p className="text-xs text-gray-500 truncate">{doc.fileName}</p>
    </div>
  )
}

function TypeMatchBadge({ result }: { result: VerifyResponse }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400">Identified as:</span>
      <span className="text-xs font-semibold text-gray-700 bg-gray-100 px-2.5 py-1 rounded-full">
        {result.identified_type}
      </span>
      <ConfidencePill confidence={result.confidence} />
    </div>
  )
}

function FieldChecksTable({ checks }: { checks: VerifyResponse['field_checks'] }) {
  if (checks.length === 0) return null
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-3 py-2 text-gray-500 font-medium">Field</th>
            <th className="text-left px-3 py-2 text-gray-500 font-medium">Your Profile</th>
            <th className="text-left px-3 py-2 text-gray-500 font-medium">On Document</th>
            <th className="text-center px-3 py-2 text-gray-500 font-medium">Match</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {checks.map((c) => (
            <tr key={c.field} className={c.match === false ? 'bg-red-50/40' : c.match === true ? 'bg-green-50/30' : ''}>
              <td className="px-3 py-2 font-medium text-gray-700">{c.label}</td>
              <td className="px-3 py-2 text-gray-600">{c.profile_value}</td>
              <td className="px-3 py-2 text-gray-600">{c.document_value ?? <span className="text-gray-300 italic">not visible</span>}</td>
              <td className="px-3 py-2 text-center">
                {c.match === true  && <span className="text-green-600 font-bold">✓</span>}
                {c.match === false && <span className="text-red-600 font-bold">✗</span>}
                {c.match === null  && <span className="text-gray-300">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ExtractedFieldsRow({ extracted }: { extracted: Record<string, string | null> }) {
  const visible = Object.entries(extracted).filter(([, v]) => v != null) as [string, string][]
  if (visible.length === 0) return null
  const labels: Record<string, string> = {
    name: 'Name', date_of_birth: 'DOB', gender: 'Gender',
    state: 'State', document_number: 'Document No.',
  }
  return (
    <div className="flex flex-wrap gap-2">
      {visible.map(([k, v]) => (
        <span key={k} className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full">
          {labels[k] ?? k}: <span className="font-medium">{v}</span>
        </span>
      ))}
    </div>
  )
}

// ─── UploadZone ───────────────────────────────────────────────────────────────

function UploadZone({
  onFile,
  onDrop,
  fileRef,
}: {
  onFile: (f: File) => void
  onDrop: (e: React.DragEvent) => void
  fileRef: React.RefObject<HTMLInputElement>
}) {
  const [dragging, setDragging] = useState(false)

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { setDragging(false); onDrop(e) }}
      onClick={() => fileRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-5 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors
        ${dragging ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30'}`}
    >
      <div className="text-2xl">📸</div>
      <p className="text-sm font-medium text-gray-600">Tap or drag to upload</p>
      <p className="text-xs text-gray-400">Photo (JPG / PNG / WEBP) or PDF scan</p>
      <input
        ref={fileRef}
        type="file"
        accept="image/*,.pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
          e.target.value = ''
        }}
      />
    </div>
  )
}

// ─── ConfidencePill ───────────────────────────────────────────────────────────

function ConfidencePill({ confidence }: { confidence: 'high' | 'medium' | 'low' }) {
  const cfg = {
    high:   { cls: 'bg-green-100 text-green-700',  label: 'High confidence' },
    medium: { cls: 'bg-amber-100 text-amber-700',  label: 'Medium confidence' },
    low:    { cls: 'bg-red-100 text-red-600',      label: 'Low confidence' },
  }[confidence]
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

// ─── StatusIcon ───────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: DocStatus }) {
  if (status === 'confirmed') return <span className="text-green-500 text-base font-bold">✓</span>
  if (status === 'rejected')  return <span className="text-red-500 text-base font-bold">✗</span>
  if (status === 'mismatch')  return <span className="text-amber-500 text-base">⚠</span>
  if (status === 'unverified') return <span className="text-blue-400 text-base">?</span>
  if (status === 'uploading') return (
    <svg className="animate-spin w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
  return <span className="text-gray-300 text-base">○</span>
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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseRequiredDocuments(raw: string | null | undefined): string[] {
  if (!raw || raw === 'None' || raw === 'null') return []
  const numbered = raw.split(/\d+[.)]\s+/)
  if (numbered.length > 2) {
    return numbered.map((s) => s.trim().replace(/\.$/, '').trim()).filter((s) => s.length > 3)
  }
  const byLine = raw.split('\n').map((s) => s.trim()).filter((s) => s.length > 3)
  if (byLine.length > 1) return byLine
  const byPeriod = raw.split('. ').map((s) => s.trim().replace(/\.$/, '')).filter((s) => s.length > 3)
  if (byPeriod.length > 1) return byPeriod
  return [raw.trim()]
}

async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

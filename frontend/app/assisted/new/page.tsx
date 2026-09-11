'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createCitizen, ApiError } from '@/lib/api'

const WORKER_KEY = 'assisted_worker_id'

export default function NewCitizenPage() {
  const router = useRouter()
  const [workerId, setWorkerId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const id = localStorage.getItem(WORKER_KEY)
    if (!id) {
      router.replace('/assisted')
      return
    }
    setWorkerId(id)
  }, [router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!workerId) return
    if (!name.trim()) {
      setError('Citizen name is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const record = await createCitizen(
        workerId,
        name.trim(),
        phone.trim() || undefined,
        notes.trim() || undefined,
      )
      router.push(`/assisted/interview?session=${record.session_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create citizen.')
      setSaving(false)
    }
  }

  if (!workerId) return null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <Link
            href="/assisted/citizens"
            className="text-gray-500 hover:text-gray-700 text-sm"
          >
            ← Back
          </Link>
          <span className="text-gray-900 font-bold text-sm">New Citizen</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6">
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
          <h1 className="text-gray-900 font-bold text-lg mb-1">Add Citizen</h1>
          <p className="text-gray-500 text-sm mb-6">
            A new session will be created. You will be taken to the interview next.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => { setName(e.target.value); setError(null) }}
                placeholder="e.g. Ramesh Kumar"
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                autoFocus
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Mobile Number <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. 9876543210"
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Notes <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. BPL household, referred by Anganwadi worker"
                rows={3}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 resize-none"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Creating…
                </>
              ) : (
                'Start Interview →'
              )}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}

'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { listCitizens, ApiError } from '@/lib/api'
import type { CitizenRecord } from '@/lib/api'

const WORKER_KEY = 'assisted_worker_id'

export default function CitizensPage() {
  const router = useRouter()
  const [workerId, setWorkerId] = useState<string | null>(null)
  const [citizens, setCitizens] = useState<CitizenRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const id = localStorage.getItem(WORKER_KEY)
    if (!id) {
      router.replace('/assisted')
      return
    }
    setWorkerId(id)
  }, [router])

  const load = useCallback(async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      const list = await listCitizens(id)
      list.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      setCitizens(list)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load citizens.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (workerId) load(workerId)
  }, [workerId, load])

  function handleLogout() {
    localStorage.removeItem(WORKER_KEY)
    router.push('/assisted')
  }

  const filtered = citizens.filter((c) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      c.citizen_name.toLowerCase().includes(q) ||
      (c.citizen_phone ?? '').includes(q)
    )
  })

  if (!workerId) return null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-orange-400 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xs">S</span>
            </div>
            <div>
              <span className="font-bold text-gray-900 text-sm">Citizens</span>
              <span className="text-gray-400 text-xs ml-2">Worker: {workerId}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/assisted/new"
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
            >
              + New Citizen
            </Link>
            <button
              onClick={handleLogout}
              className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-4 space-y-3">
        {/* Search */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or phone…"
            className="w-full pl-9 pr-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => workerId && load(workerId)} className="text-xs underline">
              Retry
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && citizens.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-2xl p-10 text-center">
            <div className="text-4xl mb-3">👤</div>
            <h3 className="font-semibold text-gray-700 mb-1">No citizens yet</h3>
            <p className="text-gray-400 text-sm mb-5">
              Add a citizen to start an interview and find eligible schemes.
            </p>
            <Link
              href="/assisted/new"
              className="inline-flex items-center gap-1 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              + Add First Citizen
            </Link>
          </div>
        )}

        {/* No search results */}
        {!loading && !error && citizens.length > 0 && filtered.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500 text-sm">
            No citizens match &quot;{search}&quot;.{' '}
            <button onClick={() => setSearch('')} className="text-indigo-600 underline">
              Clear
            </button>
          </div>
        )}

        {/* Citizen list */}
        {!loading && (
          <div className="space-y-2">
            {filtered.map((c) => (
              <CitizenCard key={c.session_id} citizen={c} />
            ))}
          </div>
        )}

        {/* Count */}
        {!loading && citizens.length > 0 && (
          <p className="text-xs text-gray-400 text-center pb-6">
            {filtered.length} of {citizens.length} citizen{citizens.length !== 1 ? 's' : ''}
          </p>
        )}
      </main>
    </div>
  )
}

function CitizenCard({ citizen }: { citizen: CitizenRecord }) {
  const date = new Date(citizen.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  return (
    <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3.5 flex items-center justify-between gap-3 hover:border-indigo-200 hover:shadow-sm transition-all">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
          <span className="text-indigo-700 font-bold text-sm">
            {citizen.citizen_name.charAt(0).toUpperCase()}
          </span>
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-gray-900 text-sm truncate">{citizen.citizen_name}</p>
          <p className="text-gray-400 text-xs">
            {citizen.citizen_phone ? `${citizen.citizen_phone} · ` : ''}
            {date}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <Link
          href={`/assisted/interview?session=${citizen.session_id}`}
          className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg font-medium hover:bg-indigo-100 transition-colors"
        >
          Interview
        </Link>
        <Link
          href={`/assisted/results?session=${citizen.session_id}`}
          className="text-xs bg-green-50 text-green-700 border border-green-200 px-3 py-1.5 rounded-lg font-medium hover:bg-green-100 transition-colors"
        >
          Results
        </Link>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

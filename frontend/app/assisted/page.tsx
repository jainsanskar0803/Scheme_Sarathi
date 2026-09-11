'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const WORKER_KEY = 'assisted_worker_id'

export default function AssistedLoginPage() {
  const router = useRouter()
  const [workerId, setWorkerId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const stored = localStorage.getItem(WORKER_KEY)
    if (stored) {
      router.replace('/assisted/citizens')
    }
  }, [router])

  function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    const id = workerId.trim()
    if (!id) {
      setError('Please enter your Worker ID.')
      return
    }
    localStorage.setItem(WORKER_KEY, id)
    router.push('/assisted/citizens')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-indigo-900 to-indigo-800 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-9 h-9 bg-orange-400 rounded-xl flex items-center justify-center">
            <span className="text-white font-bold text-base">S</span>
          </div>
          <span className="text-white font-bold text-xl tracking-tight">Scheme Sarathi</span>
        </div>

        <div className="bg-white rounded-2xl shadow-xl px-6 py-8">
          <h1 className="text-gray-900 font-bold text-xl mb-1">Assisted Mode</h1>
          <p className="text-gray-500 text-sm mb-6">For CSC / NGO field workers</p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Worker ID
              </label>
              <input
                type="text"
                value={workerId}
                onChange={(e) => { setWorkerId(e.target.value); setError('') }}
                placeholder="e.g. CSC_DELHI_001"
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                autoFocus
              />
              {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
            </div>

            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors"
            >
              Enter Dashboard
            </button>
          </form>

          <p className="text-center text-xs text-gray-400 mt-5">
            Citizen?{' '}
            <Link href="/" className="text-indigo-600 hover:underline">
              Use self-service mode
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

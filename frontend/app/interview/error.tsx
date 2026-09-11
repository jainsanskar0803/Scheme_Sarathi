'use client'

import { useEffect } from 'react'
import Link from 'next/link'

export default function InterviewError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white border border-red-200 rounded-2xl px-8 py-8 text-center max-w-sm shadow-sm">
        <div className="text-4xl mb-3">⚠</div>
        <h2 className="text-red-800 font-semibold mb-2">Something went wrong</h2>
        <p className="text-red-600 text-sm mb-5">{error.message || 'An unexpected error occurred.'}</p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            Try again
          </button>
          <Link
            href="/"
            className="bg-white border border-gray-200 text-gray-600 px-5 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Home
          </Link>
        </div>
      </div>
    </div>
  )
}

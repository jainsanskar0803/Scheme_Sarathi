'use client'

import { useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

function RedirectContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session')

  useEffect(() => {
    if (sessionId) {
      router.replace(`/interview?session=${sessionId}&from=assisted`)
    } else {
      router.replace('/assisted/citizens')
    }
  }, [router, sessionId])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <svg className="animate-spin w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  )
}

export default function AssistedInterviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <RedirectContent />
    </Suspense>
  )
}

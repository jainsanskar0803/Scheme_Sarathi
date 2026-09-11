'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createProfile, ApiError } from '@/lib/api'

export default function HomePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleStart() {
    setLoading(true)
    setError(null)
    try {
      const { session_id } = await createProfile()
      router.push(`/interview?session=${session_id}`)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Could not connect to backend: ${err.message}`)
      } else {
        setError('An unexpected error occurred. Please try again.')
      }
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-indigo-900 to-indigo-800 flex flex-col">
      {/* Header */}
      <header className="px-6 py-5 flex items-center justify-between max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-orange-400 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="text-white font-semibold text-lg tracking-tight">Scheme Sarathi</span>
        </div>
        <nav className="hidden md:flex items-center gap-6 text-indigo-200 text-sm">
          <span className="text-indigo-300">Supports: English · Hindi · Hinglish</span>
        </nav>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 bg-indigo-800/60 border border-indigo-600/40 rounded-full px-4 py-1.5 mb-8 backdrop-blur-sm">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          <span className="text-indigo-200 text-sm font-medium">AI-powered · Free · No login required</span>
        </div>

        {/* Title */}
        <h1 className="text-5xl md:text-7xl font-extrabold text-white leading-tight mb-6 tracking-tight">
          Scheme{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-300 to-orange-500">
            Sarathi
          </span>
        </h1>
        <p className="text-xl md:text-2xl text-indigo-200 font-medium mb-4 max-w-2xl">
          Find government schemes you qualify for
        </p>
        <p className="text-indigo-300 text-base md:text-lg mb-12 max-w-xl leading-relaxed">
          AI-powered eligibility matching across{' '}
          <span className="text-orange-400 font-bold">3,397</span> central and state schemes.
          Just tell us about yourself — we&apos;ll find what you deserve.
        </p>

        {/* CTA */}
        <div className="flex flex-col items-center gap-4">
          <button
            onClick={handleStart}
            disabled={loading}
            className="group relative inline-flex items-center gap-3 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-white font-bold text-lg px-10 py-4 rounded-2xl shadow-2xl shadow-orange-500/30 transition-all duration-200 hover:scale-105 hover:shadow-orange-500/40 disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {loading ? (
              <>
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Starting...
              </>
            ) : (
              <>
                Find My Benefits
                <span className="group-hover:translate-x-1 transition-transform duration-200">→</span>
              </>
            )}
          </button>

          {error && (
            <div className="bg-red-900/40 border border-red-500/40 text-red-200 rounded-xl px-5 py-3 text-sm max-w-sm text-center">
              {error}
            </div>
          )}

          <p className="text-indigo-400 text-sm mt-2">
            Supports English · Hindi · Hinglish
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-20 max-w-4xl w-full">
          <FeatureCard
            icon="💬"
            title="AI Interview"
            description="Answer a few questions in plain English or Hindi. Our AI extracts your profile automatically."
            accent="indigo"
          />
          <FeatureCard
            icon="📋"
            title="3,397 Schemes"
            description="Comprehensive database covering education, agriculture, health, housing and more."
            accent="orange"
          />
          <FeatureCard
            icon="⚡"
            title="Instant Results"
            description="Get personalized eligibility results with clear explanations — no paperwork needed."
            accent="green"
          />
        </div>

        {/* Stats row */}
        <div className="flex flex-wrap justify-center gap-8 mt-16 text-center">
          <StatItem value="3,397" label="Total Schemes" />
          <StatItem value="28+" label="States & UTs" />
          <StatItem value="10+" label="Categories" />
          <StatItem value="3" label="Languages" />
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-6 text-indigo-400 text-sm border-t border-indigo-800/50">
        <p>Scheme Sarathi · Helping citizens discover their entitlements</p>
        <p className="mt-1 text-indigo-500 text-xs">Data sourced from official government portals · Not affiliated with Government of India</p>
      </footer>
    </div>
  )
}

function FeatureCard({
  icon,
  title,
  description,
  accent,
}: {
  icon: string
  title: string
  description: string
  accent: 'indigo' | 'orange' | 'green'
}) {
  const borderColors = {
    indigo: 'border-indigo-500/30 hover:border-indigo-400/60',
    orange: 'border-orange-500/30 hover:border-orange-400/60',
    green: 'border-green-500/30 hover:border-green-400/60',
  }
  const iconBg = {
    indigo: 'bg-indigo-700/50',
    orange: 'bg-orange-700/30',
    green: 'bg-green-700/30',
  }

  return (
    <div
      className={`bg-indigo-900/40 backdrop-blur-sm border ${borderColors[accent]} rounded-2xl p-6 text-left transition-all duration-200 hover:bg-indigo-800/40`}
    >
      <div className={`w-12 h-12 ${iconBg[accent]} rounded-xl flex items-center justify-center text-2xl mb-4`}>
        {icon}
      </div>
      <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
      <p className="text-indigo-300 text-sm leading-relaxed">{description}</p>
    </div>
  )
}

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-3xl font-extrabold text-orange-400">{value}</div>
      <div className="text-indigo-300 text-sm mt-1">{label}</div>
    </div>
  )
}

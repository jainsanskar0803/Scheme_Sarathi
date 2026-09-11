'use client'

import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { createProfile, sendChatMessage, matchSchemes, transcribeAudio, speakText, ApiError } from '@/lib/api'
import type { ChatMessage, Completeness } from '@/lib/types'

// ─── Types ────────────────────────────────────────────────────────────────────

type VoiceState = 'idle' | 'recording' | 'transcribing' | 'error'

const INITIAL_MESSAGE =
  "Namaste! I'm your Scheme Sarathi assistant. Tell me about yourself — your age, state, occupation, and income. The more you share, the better I can match you to the right government schemes."

function generateId() {
  return Math.random().toString(36).slice(2, 10)
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function InterviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><LoadingSpinner label="Loading interview..." /></div>}>
      <InterviewContent />
    </Suspense>
  )
}

// ─── Main content ─────────────────────────────────────────────────────────────

function InterviewContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session')
  const fromAssisted = searchParams.get('from') === 'assisted'

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isMatchLoading, setIsMatchLoading] = useState(false)
  const [completeness, setCompleteness] = useState<Completeness | null>(null)
  const [interviewDone, setInterviewDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [initialized, setInitialized] = useState(false)

  // Voice state
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const [ttsOn, setTtsOn] = useState(false)          // speaker toggle
  const [lastLang, setLastLang] = useState('en')     // track last detected language for TTS
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)
  const lastWasVoiceRef = useRef(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  // ── Session init ─────────────────────────────────────────────────────────────

  useEffect(() => {
    if (initialized) return
    setInitialized(true)
    if (!sessionId) {
      createProfile()
        .then(({ session_id }) => router.replace(`/interview?session=${session_id}`))
        .catch(() => setError('Failed to connect to backend. Please try again.'))
      return
    }
    setMessages([{ id: generateId(), role: 'assistant', content: INITIAL_MESSAGE, timestamp: new Date() }])
  }, [sessionId, router, initialized])

  // ── TTS playback ─────────────────────────────────────────────────────────────

  async function playTTS(text: string, language: string) {
    try {
      ttsAudioRef.current?.pause()
      const result = await speakText(text, language)
      const audio = new Audio(`data:audio/wav;base64,${result.audio_base64}`)
      ttsAudioRef.current = audio
      audio.play().catch(() => {}) // iOS autoplay restriction — silent fail
    } catch {
      // TTS is enhancement only; never block the chat flow
    }
  }

  // ── Text send ────────────────────────────────────────────────────────────────

  async function handleSend(textOverride?: string) {
    const text = (textOverride ?? inputValue).trim()
    if (!text || isLoading || !sessionId) return

    lastWasVoiceRef.current = !!textOverride  // true when called from voice flow
    const userMsg: ChatMessage = { id: generateId(), role: 'user', content: text, timestamp: new Date() }
    setMessages((prev) => [...prev, userMsg])
    setInputValue('')
    setIsLoading(true)
    setError(null)

    try {
      const data = await sendChatMessage(sessionId, text)
      setCompleteness(data.completeness)
      setLastLang(data.language)

      setMessages((prev) =>
        prev.map((m) => m.id === userMsg.id
          ? { ...m, extracted: Object.keys(data.extracted).length > 0 ? data.extracted : undefined }
          : m,
        ),
      )

      if (data.next_question === null) {
        setInterviewDone(true)
        const doneMsg: ChatMessage = {
          id: generateId(), role: 'assistant',
          content: data.language === 'hi'
            ? 'बढ़िया! आपकी सभी जानकारी मिल गई। अपनी योजनाएं देखने के लिए नीचे का बटन दबाएं।'
            : "Great! I have enough information to find relevant schemes for you. Click the button below to see your results.",
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, doneMsg])
        if (ttsOn || lastWasVoiceRef.current) playTTS(doneMsg.content, data.language)
      } else {
        const aiMsg: ChatMessage = { id: generateId(), role: 'assistant', content: data.next_question, timestamp: new Date() }
        setMessages((prev) => [...prev, aiMsg])
        if (ttsOn || lastWasVoiceRef.current) playTTS(data.next_question, data.language)
      }
    } catch (err) {
      setError(err instanceof ApiError ? `Error: ${err.message}` : 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  // ── Voice recording ──────────────────────────────────────────────────────────

  async function startRecording() {
    setVoiceError(null)
    ttsAudioRef.current?.pause()   // stop any playing TTS before recording

    if (typeof MediaRecorder === 'undefined') {
      setVoiceError('Voice input is not supported in this browser. Please type your message.')
      return
    }

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err) {
      if (err instanceof DOMException) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setVoiceError('Microphone access denied. Please allow microphone access in your browser/device settings and try again.')
        } else if (err.name === 'NotFoundError') {
          setVoiceError('No microphone found. Please connect a microphone and try again.')
        } else {
          setVoiceError('Could not access microphone. Please check your device settings.')
        }
      } else {
        setVoiceError('Could not start recording.')
      }
      return
    }

    // Pick the best supported MIME type
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find(
      (t) => MediaRecorder.isTypeSupported(t),
    ) || ''

    const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    audioChunksRef.current = []
    mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(audioChunksRef.current, { type: mimeType || 'audio/webm' })
      await runTranscription(blob)
    }
    mr.start(100)
    mediaRecorderRef.current = mr
    setVoiceState('recording')
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    setVoiceState('transcribing')
  }

  async function runTranscription(blob: Blob) {
    try {
      const result = await transcribeAudio(blob)
      const text = result.text.trim()
      if (!text) {
        setVoiceError('No speech detected. Please try again.')
        setVoiceState('error')
        return
      }
      // Show transcription in input field briefly, then auto-send
      setInputValue(text)
      setVoiceState('idle')
      setTtsOn(true)    // entering voice mode → enable TTS output automatically
      await handleSend(text)
    } catch {
      setVoiceError('Transcription failed. Please try again or type your message.')
      setVoiceState('error')
    }
  }

  function dismissVoiceError() {
    setVoiceError(null)
    setVoiceState('idle')
  }

  // ── Match / find benefits ────────────────────────────────────────────────────

  async function handleFindBenefits() {
    if (!sessionId || isMatchLoading) return
    setIsMatchLoading(true)
    setError(null)
    try {
      const results = await matchSchemes(sessionId)
      const toCache = { ...results, ineligible: [] }
      try { sessionStorage.setItem('match_results', JSON.stringify(toCache)) } catch {
        const minimal = { ...results, ineligible: [], near_miss: results.near_miss.slice(0, 50), eligible: results.eligible.slice(0, 200), insufficient_information: results.insufficient_information }
        sessionStorage.setItem('match_results', JSON.stringify(minimal))
      }
      const dest = fromAssisted
        ? `/assisted/results?session=${sessionId}`
        : `/results?session=${sessionId}`
      router.push(dest)
    } catch (err) {
      setError(err instanceof ApiError ? `Matching failed: ${err.message}` : 'Could not fetch results. Please try again.')
      setIsMatchLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const progressPercent = completeness ? Math.round(completeness.core_percent * 100) : 0
  const showFindButton = interviewDone || (completeness !== null && completeness.core_percent >= 0.8)

  if (!sessionId && !error) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center"><LoadingSpinner label="Starting your session..." /></div>
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => router.push(fromAssisted ? '/assisted/citizens' : '/')}
            className="text-indigo-600 hover:text-indigo-800 transition-colors text-sm font-medium flex-shrink-0"
          >
            {fromAssisted ? '← Citizens' : '← Home'}
          </button>

          {/* Progress bar */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Profile Complete</span>
              <span className="text-xs font-bold text-indigo-600">{progressPercent}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-500 to-indigo-600 h-2 rounded-full transition-all duration-300" style={{ width: `${progressPercent}%` }} />
            </div>
          </div>

          {/* TTS toggle */}
          <button
            onClick={() => {
              setTtsOn((v) => {
                if (v) ttsAudioRef.current?.pause()
                return !v
              })
            }}
            title={ttsOn ? 'Turn off voice responses' : 'Turn on voice responses'}
            className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-colors border ${
              ttsOn ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-300 text-gray-400 hover:border-indigo-400 hover:text-indigo-500'
            }`}
          >
            {ttsOn ? <SpeakerOnIcon /> : <SpeakerOffIcon />}
          </button>

          {/* Filled field chips (desktop only) */}
          {completeness && completeness.filled.length > 0 && (
            <div className="hidden lg:flex flex-wrap gap-1 max-w-xs">
              {completeness.filled.slice(0, 4).map((f) => (
                <span key={f} className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">{f}</span>
              ))}
              {completeness.filled.length > 4 && <span className="text-xs text-gray-400">+{completeness.filled.length - 4}</span>}
            </div>
          )}
        </div>
      </header>

      {/* ── Chat area ───────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 py-6 flex flex-col gap-4 overflow-y-auto pb-44">
        {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex items-start gap-3">
            <AssistantAvatar />
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
              <div className="flex gap-1.5 items-center h-5">
                <div className="typing-dot w-2 h-2 bg-indigo-400 rounded-full" />
                <div className="typing-dot w-2 h-2 bg-indigo-400 rounded-full" />
                <div className="typing-dot w-2 h-2 bg-indigo-400 rounded-full" />
              </div>
            </div>
          </div>
        )}

        {/* Chat error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">{error}</div>
        )}

        {/* Find Benefits button */}
        {showFindButton && (
          <div className="flex flex-col items-center gap-3 my-4">
            <div className="text-sm text-gray-500 text-center">
              {interviewDone ? 'Interview complete!' : `Profile ${progressPercent}% complete — ready to find schemes!`}
            </div>
            <button
              onClick={handleFindBenefits}
              disabled={isMatchLoading}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold px-8 py-3.5 rounded-xl shadow-lg shadow-indigo-500/25 transition-all duration-200 hover:scale-105 disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:scale-100 text-base"
            >
              {isMatchLoading ? (
                <><svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>Evaluating schemes...</>
              ) : (
                <><span>🔍</span>Find My Benefits</>
              )}
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      {/* ── Fixed bottom input ───────────────────────────────────────────────── */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 space-y-2">

          {/* Missing fields chips */}
          {completeness && completeness.missing_core.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              <span className="text-xs text-gray-400">Still needed:</span>
              {completeness.missing_core.slice(0, 5).map((f) => (
                <span key={f} className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full">{f}</span>
              ))}
            </div>
          )}

          {/* Voice status banner */}
          {voiceState === 'recording' && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-3 py-2">
              <span className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse flex-shrink-0" />
              <span className="text-sm text-red-700 font-medium flex-1">Recording… speak now</span>
              <button onClick={stopRecording} className="text-xs text-red-600 font-semibold underline">Stop</button>
            </div>
          )}
          {voiceState === 'transcribing' && (
            <div className="flex items-center gap-2 bg-indigo-50 border border-indigo-200 rounded-xl px-3 py-2">
              <svg className="animate-spin w-4 h-4 text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm text-indigo-700">Transcribing…</span>
            </div>
          )}
          {voiceError && (
            <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              <span className="text-amber-500 flex-shrink-0 mt-0.5">⚠</span>
              <p className="text-xs text-amber-700 flex-1 leading-relaxed">{voiceError}</p>
              <button onClick={dismissVoiceError} className="text-amber-500 hover:text-amber-700 text-lg leading-none flex-shrink-0">×</button>
            </div>
          )}

          {/* Input row */}
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message… (Enter to send, Shift+Enter for new line)"
              rows={1}
              disabled={isLoading || isMatchLoading || voiceState === 'recording' || voiceState === 'transcribing'}
              className="flex-1 resize-none rounded-xl border border-gray-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none px-4 py-3 text-sm text-gray-800 placeholder-gray-400 transition-all max-h-32 disabled:bg-gray-50 disabled:cursor-not-allowed"
              style={{ minHeight: '48px' }}
              onInput={(e) => {
                const el = e.currentTarget
                el.style.height = 'auto'
                el.style.height = Math.min(el.scrollHeight, 128) + 'px'
              }}
            />

            {/* Mic button */}
            <MicButton
              voiceState={voiceState}
              disabled={isLoading || isMatchLoading}
              onStart={startRecording}
              onStop={stopRecording}
            />

            {/* Send button */}
            <button
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isLoading || isMatchLoading}
              className="flex-shrink-0 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-4 transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md"
              style={{ height: '48px', width: '48px' }}
              aria-label="Send"
            >
              <svg className="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>

          {/* Language / mode hint */}
          <div className="flex items-center justify-between px-1">
            <p className="text-xs text-gray-400">
              {voiceState === 'idle' && ttsOn ? '🔊 Voice responses on' : ''}
              {voiceState === 'idle' && !ttsOn ? 'Tap 🎤 to speak in Hindi, English, or Hinglish' : ''}
            </p>
            {ttsOn && voiceState === 'idle' && (
              <button onClick={() => { setTtsOn(false); ttsAudioRef.current?.pause() }} className="text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2">
                Turn off voice
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Mic button ───────────────────────────────────────────────────────────────

function MicButton({ voiceState, disabled, onStart, onStop }: {
  voiceState: VoiceState
  disabled: boolean
  onStart: () => void
  onStop: () => void
}) {
  const isRecording = voiceState === 'recording'
  const isBusy = voiceState === 'transcribing'

  return (
    <button
      onClick={isRecording ? onStop : onStart}
      disabled={disabled || isBusy}
      aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
      className={`flex-shrink-0 rounded-xl flex items-center justify-center transition-all focus:outline-none focus:ring-2 focus:ring-offset-1 ${
        isRecording
          ? 'bg-red-500 hover:bg-red-600 text-white focus:ring-red-400 animate-pulse'
          : isBusy
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-600 focus:ring-indigo-400'
      }`}
      style={{ height: '48px', width: '48px' }}
    >
      {isRecording ? <StopIcon /> : isBusy ? <SpinnerIcon /> : <MicIcon />}
    </button>
  )
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const isAssistant = message.role === 'assistant'

  if (isAssistant) {
    return (
      <div className="flex items-start gap-3 max-w-[85%]">
        <AssistantAvatar />
        <div className="flex flex-col gap-1.5">
          <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
            <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
          <span className="text-xs text-gray-400 pl-1">{formatTime(message.timestamp)}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-end gap-1.5 ml-auto max-w-[85%]">
      <div className="bg-gradient-to-br from-indigo-600 to-indigo-700 rounded-2xl rounded-tr-none px-4 py-3 shadow-sm">
        <p className="text-white text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>

      {/* Extracted field chips */}
      {message.extracted && Object.keys(message.extracted).length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-end">
          {Object.entries(message.extracted).map(([k, v]) => (
            <span key={k} className="text-xs bg-green-100 text-green-800 border border-green-200 px-2.5 py-0.5 rounded-full font-medium">
              ✓ {formatExtractedField(k, v)}
            </span>
          ))}
        </div>
      )}

      <span className="text-xs text-gray-400 pr-1">{formatTime(message.timestamp)}</span>
    </div>
  )
}

// ─── Small components ─────────────────────────────────────────────────────────

function AssistantAvatar() {
  return (
    <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-indigo-600 to-indigo-700 rounded-full flex items-center justify-center shadow-sm">
      <span className="text-white text-xs font-bold">S</span>
    </div>
  )
}

function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 text-gray-500">
      <svg className="animate-spin w-8 h-8 text-indigo-500" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {label && <p className="text-sm">{label}</p>}
    </div>
  )
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function MicIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function SpeakerOnIcon() {
  return (
    <svg className="w-4.5 h-4.5" style={{width:'18px',height:'18px'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-4-4H4V10h4l4-4z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728" />
    </svg>
  )
}

function SpeakerOffIcon() {
  return (
    <svg className="w-4.5 h-4.5" style={{width:'18px',height:'18px'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
    </svg>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

const _FIELD_LABELS: Record<string, string> = {
  age: 'Age', gender: 'Gender', state: 'State', district: 'District',
  domicile: 'Area', caste: 'Caste', annual_income: 'Income', occupation: 'Occupation',
  marital_status: 'Marital status', num_children: 'Children',
  is_disabled: 'Disability', has_bpl_card: 'BPL card',
  has_electricity_connection: 'Electricity', owns_house: 'Owns house',
  owns_vehicle: 'Vehicle', land_holding_acres: 'Land (acres)',
  is_student: 'Student', is_farmer: 'Farmer', is_artisan: 'Artisan',
  is_business_owner: 'Business owner',
}

function formatExtractedField(key: string, value: unknown): string {
  const label = _FIELD_LABELS[key] ?? key.replace(/_/g, ' ')
  let display: string
  if (typeof value === 'boolean') {
    display = value ? 'Yes' : 'No'
  } else if (key === 'annual_income' && typeof value === 'number') {
    display = value >= 100000
      ? `₹${(value / 100000).toFixed(value % 100000 === 0 ? 0 : 1)}L`
      : `₹${value.toLocaleString('en-IN')}`
  } else {
    const s = String(value)
    display = s.charAt(0).toUpperCase() + s.slice(1)
  }
  return `${label}: ${display}`
}

import type {
  CreateProfileResponse,
  UpdateProfileResponse,
  GetProfileResponse,
  ChatResponse,
  MatchResponse,
  Profile,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body?.detail || body?.message || message
    } catch {
      // ignore json parse errors
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

// POST /api/profile → create a new session
export async function createProfile(): Promise<CreateProfileResponse> {
  const res = await fetch(`${BASE_URL}/api/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return handleResponse<CreateProfileResponse>(res)
}

// PATCH /api/profile/{session_id} → update profile fields
export async function updateProfile(
  sessionId: string,
  fields: Partial<Profile>,
): Promise<UpdateProfileResponse> {
  const res = await fetch(`${BASE_URL}/api/profile/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  return handleResponse<UpdateProfileResponse>(res)
}

// GET /api/profile/{session_id} → fetch profile + completeness
export async function getProfile(sessionId: string): Promise<GetProfileResponse> {
  const res = await fetch(`${BASE_URL}/api/profile/${sessionId}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  return handleResponse<GetProfileResponse>(res)
}

// POST /api/chat → send a message in the interview
export async function sendChatMessage(
  sessionId: string,
  message: string,
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  return handleResponse<ChatResponse>(res)
}

// POST /api/match → run scheme matching
export async function matchSchemes(sessionId: string): Promise<MatchResponse> {
  const res = await fetch(`${BASE_URL}/api/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<MatchResponse>(res)
}

// POST /api/documents/identify → lightweight type-only identification (legacy)
export interface IdentifyResponse {
  identified_type: string
  confidence: 'high' | 'medium' | 'low'
  alternatives: string[]
  reason: string
  matched_required: string | null
  disclaimer: string
}

export async function identifyDocument(
  imageBase64: string,
  imageMime: string,
  requiredDocuments: string[],
): Promise<IdentifyResponse> {
  const res = await fetch(`${BASE_URL}/api/documents/identify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      image_mime: imageMime,
      required_documents: requiredDocuments,
    }),
  })
  return handleResponse<IdentifyResponse>(res)
}

// POST /api/documents/verify → full verification: type check + field matching
export interface FieldCheck {
  field: string
  label: string
  profile_value: string
  document_value: string | null
  match: boolean | null  // true=match, false=mismatch, null=unverifiable
}

export interface VerifyResponse {
  is_real_document: boolean
  identified_type: string
  confidence: 'high' | 'medium' | 'low'
  type_match: boolean
  extracted_fields: Record<string, string | null>
  field_checks: FieldCheck[]
  overall_verified: boolean
  rejection_reason: string | null
  disclaimer: string
}

export async function verifyDocument(
  imageBase64: string,
  imageMime: string,
  requiredDocument: string,
  sessionId?: string | null,
): Promise<VerifyResponse> {
  const res = await fetch(`${BASE_URL}/api/documents/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      image_mime: imageMime,
      required_document: requiredDocument,
      session_id: sessionId || null,
    }),
  })
  return handleResponse<VerifyResponse>(res)
}

// POST /api/voice/transcribe → convert speech audio to text
export interface TranscribeResponse {
  text: string
  language_code: string   // e.g. "hi-IN", "en-IN"
}

export async function transcribeAudio(blob: Blob): Promise<TranscribeResponse> {
  const ext = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm'
  const form = new FormData()
  form.append('file', blob, `recording.${ext}`)
  const res = await fetch(`${BASE_URL}/api/voice/transcribe`, {
    method: 'POST',
    body: form,
  })
  return handleResponse<TranscribeResponse>(res)
}

// POST /api/voice/speak → convert text to speech, returns base64 WAV
export interface SpeakResponse {
  audio_base64: string
  content_type: string
}

export async function speakText(text: string, language: string): Promise<SpeakResponse> {
  const res = await fetch(`${BASE_URL}/api/voice/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language }),
  })
  return handleResponse<SpeakResponse>(res)
}

// ─── Assisted Mode ───────────────────────────────────────────────────────────

export type FollowupStatus =
  | 'will_apply'
  | 'applied'
  | 'received'
  | 'rejected'
  | 'not_applicable'

export interface CitizenRecord {
  session_id: string
  worker_id: string
  citizen_name: string
  citizen_phone: string | null
  notes: string | null
  created_at: string
}

export interface FollowupRecord {
  session_id: string
  scheme_id: string
  scheme_name: string
  status: FollowupStatus
  notes: string | null
  updated_at: string
}

export async function createCitizen(
  workerId: string,
  citizenName: string,
  citizenPhone?: string,
  notes?: string,
): Promise<CitizenRecord> {
  const res = await fetch(`${BASE_URL}/api/assisted/citizens`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      worker_id: workerId,
      citizen_name: citizenName,
      citizen_phone: citizenPhone || null,
      notes: notes || null,
    }),
  })
  return handleResponse<CitizenRecord>(res)
}

export async function listCitizens(workerId: string): Promise<CitizenRecord[]> {
  const res = await fetch(
    `${BASE_URL}/api/assisted/citizens?worker_id=${encodeURIComponent(workerId)}`,
  )
  return handleResponse<CitizenRecord[]>(res)
}

export async function getCitizen(sessionId: string): Promise<CitizenRecord> {
  const res = await fetch(`${BASE_URL}/api/assisted/citizens/${sessionId}`)
  return handleResponse<CitizenRecord>(res)
}

export async function setFollowup(
  sessionId: string,
  schemeId: string,
  schemeName: string,
  status: FollowupStatus,
  notes?: string,
): Promise<FollowupRecord> {
  const res = await fetch(
    `${BASE_URL}/api/assisted/citizens/${sessionId}/followup/${encodeURIComponent(schemeId)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scheme_name: schemeName, status, notes: notes || null }),
    },
  )
  return handleResponse<FollowupRecord>(res)
}

export async function listFollowups(sessionId: string): Promise<FollowupRecord[]> {
  const res = await fetch(`${BASE_URL}/api/assisted/citizens/${sessionId}/followup`)
  return handleResponse<FollowupRecord[]>(res)
}

// POST /api/translate → batch English → Hindi translation via Sarvam AI
export async function translateTexts(texts: (string | null)[]): Promise<(string | null)[]> {
  const res = await fetch(`${BASE_URL}/api/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts }),
  })
  const data = await handleResponse<{ translations: (string | null)[] }>(res)
  return data.translations
}

export { ApiError }

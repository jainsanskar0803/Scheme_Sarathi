// ─── Profile & Completeness ──────────────────────────────────────────────────

export interface Profile {
  age: number | null
  state: string | null
  district: string | null
  gender: string | null
  occupation: string | null
  annual_income: number | null
  caste: string | null
  domicile: string | null
  marital_status: string | null
  land_holding_acres: number | null
  num_children: number | null
  is_disabled: boolean | null
  has_bpl_card: boolean | null
  has_electricity_connection: boolean | null
  owns_house: boolean | null
  owns_vehicle: boolean | null
  is_student: boolean | null
  is_farmer: boolean | null
  is_artisan: boolean | null
  is_business_owner: boolean | null
  [key: string]: unknown
}

export interface Completeness {
  core_percent: number
  filled: string[]
  missing_core: string[]
}

// ─── API Responses ───────────────────────────────────────────────────────────

export interface CreateProfileResponse {
  session_id: string
}

export interface UpdateProfileResponse {
  session_id: string
  profile: Profile
}

export interface GetProfileResponse {
  session_id: string
  profile: Profile
  completeness: Completeness
}

export interface ChatResponse {
  session_id: string
  extracted: Record<string, unknown>
  profile: Profile
  completeness: Completeness
  next_question: string | null
  language: string
}

// ─── Scheme Match ────────────────────────────────────────────────────────────

export type ConditionStatus = 'PASS' | 'NEAR_MISS' | 'FAIL' | 'NOT_PROVIDED'
export type Verdict = 'eligible' | 'near_miss' | 'ineligible' | 'insufficient_information'

export interface ConditionExplanation {
  field: string
  label: string
  requirement: string
  citizen_value_display: string
  status: ConditionStatus
  gap: string | null
  note: string | null
}

export interface SchemeMatchResult {
  scheme_id: string
  scheme_name: string
  category_display: string[]
  tags: string[]
  verdict: Verdict
  benefit: string
  passed_rules: unknown[]
  failed_rules: unknown[]
  near_miss_rules: unknown[]
  skipped_count: number
  explanation: ConditionExplanation[]
  unverified_criteria: string[]
  missing_information: string[]
  required_documents: string | null
  application_method: string | null
  source: string
  official_website: string | null
}

export interface MatchResponse {
  session_id: string
  profile: Profile
  completeness: Completeness
  eligible: SchemeMatchResult[]
  near_miss: SchemeMatchResult[]
  insufficient_information: SchemeMatchResult[]
  ineligible: SchemeMatchResult[]
  total_schemes: number
}

// ─── Chat Message (UI only) ───────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  extracted?: Record<string, unknown>
  timestamp: Date
}

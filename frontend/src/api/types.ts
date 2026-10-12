// Mirrors backend/app/schemas.py. Keep in sync.

export type ProviderSummary = {
  id: number
  name: string
  npi: string
  specialty: string
  risk_level: string
}

export type Visit = {
  id: number
  scheduled_at: string
  site_address: string
  status: string
  visit_type: 'scheduled' | 'unscheduled'
  provider: ProviderSummary
}

export type ProviderSearchHit = {
  provider: ProviderSummary
  practice_address: string
}

export type FieldResultValue = 'match' | 'partial' | 'no_match' | 'not_provided'
export type Band = 'green' | 'yellow' | 'red'

export type FieldResult = {
  field: string
  result: FieldResultValue
  points: number
  max: number
  reason: string
}

export type VerificationResult = {
  id: string
  created_at: string
  visit_id: number
  visit_type: 'scheduled' | 'unscheduled'
  provider: ProviderSummary
  mode: 'digital' | 'manual'
  channel: 'web' | 'android'
  flow: string | null
  authenticity: { status: 'verified' | 'failed' | 'not_checked'; checks: Record<string, boolean>; issuer: string | null }
  match: {
    score: number
    band: Band
    insufficient_data: boolean
    provided_weight: number
    hard_rule: string | null
    caps: string[]
    fields: FieldResult[]
  }
  outcome: { label: string; color: Band }
  photo_checked: boolean | null
  presented_ssn_masked: string | null
  portrait_data_url: string | null
  attributes: Record<string, boolean>
  // wallet: name/DOB attested by the credential; id_details: taken from the physical ID after a genuine credential;
  // manual: typed/scanned with no credential check; none: nothing compared
  match_source: 'wallet' | 'id_details' | 'manual' | 'none'
  supplements: string | null
  saved: boolean
}

export type Flow = 'A' | 'B' | 'C'

export type DigitalStart = {
  session_id: string
  flow: Flow
  // A/B: what navigator.credentials.get needs. C: the QR / deep link for a phone wallet.
  browser: { protocol?: string; request?: unknown; wallet_uri?: string; request_uri?: string }
  expires_in: number
}

export type DigitalStatus = { status: 'pending' | 'done'; result: VerificationResult | null }

export type ManualVerifyRequest = {
  visit_id: number
  first_name?: string
  last_name: string
  dob: string
  ssn?: string
  street?: string
  zip5?: string
  photo_checked: boolean
}

export type AuditEntry = {
  id: number
  created_at: string
  auditor: string
  visit_id: number
  visit_type: 'scheduled' | 'unscheduled'
  match_source: string
  provider_name: string
  provider_npi: string
  mode: 'digital' | 'manual'
  channel: string
  flow: string | null
  authenticity: string
  auth_checks: Record<string, boolean>
  issuer: string | null
  score: number | null
  band: Band
  outcome: string
  field_results: FieldResult[]
  photo_checked: boolean | null
  notes: string
  entry_hash: string
}

export type ChainCheck = { ok: boolean; entries: number; first_bad_id: number | null }
export type Health = { status: string; credence_configured: boolean }

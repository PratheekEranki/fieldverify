import type {
  AuditEntry,
  ChainCheck,
  DigitalStart,
  DigitalStatus,
  Flow,
  Health,
  ManualVerifyRequest,
  ProviderSearchHit,
  VerificationResult,
  Visit,
} from './types'

export class ApiError extends Error {
  code: string
  fields?: { field: string; message: string }[]
  constructor(code: string, message: string, fields?: { field: string; message: string }[]) {
    super(message)
    this.code = code
    this.fields = fields
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError('network', 'Cannot reach the FieldVerify server.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(err?.code ?? `http_${res.status}`, err?.message ?? `Request failed (${res.status})`, err?.fields)
  }
  return body as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  visits: () => request<Visit[]>('/api/visits'),
  visit: (id: number) => request<Visit>(`/api/visits/${id}`),
  searchProviders: (q: string) =>
    request<ProviderSearchHit[]>(`/api/providers/search?${new URLSearchParams({ q })}`),
  startUnscheduledVisit: (providerId: number) =>
    request<Visit>('/api/visits/unscheduled', { method: 'POST', body: JSON.stringify({ provider_id: providerId }) }),
  verifyManual: (body: ManualVerifyRequest) =>
    request<VerificationResult>('/api/verify/manual', { method: 'POST', body: JSON.stringify(body) }),
  result: (id: string) => request<VerificationResult>(`/api/verify/results/${id}`),
  digitalStart: (visitId: number, flow: Flow) =>
    request<DigitalStart>('/api/verify/digital/start', {
      method: 'POST',
      body: JSON.stringify({ visit_id: visitId, flow }),
    }),
  digitalComplete: (sessionId: string, data: string) =>
    request<VerificationResult>('/api/verify/digital/complete', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, data }),
    }),
  digitalStatus: (sessionId: string) => request<DigitalStatus>(`/api/verify/digital/status/${sessionId}`),
  saveToAudit: (resultId: string, notes: string) =>
    request<AuditEntry>('/api/audit', { method: 'POST', body: JSON.stringify({ result_id: resultId, notes }) }),
  audit: (filters: { mode?: string; band?: string }) => {
    const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][])
    return request<AuditEntry[]>(`/api/audit${q.size ? `?${q}` : ''}`)
  },
  verifyChain: () => request<ChainCheck>('/api/audit/verify-chain'),
  exportUrl: (filters: { mode?: string; band?: string }) => {
    const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][])
    return `/api/audit/export.csv${q.size ? `?${q}` : ''}`
  },
}

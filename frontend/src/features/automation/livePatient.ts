import type { ArtifactSection } from './types'

export type LiveSource = 'monday' | 'drk' | 'all'

export interface LiveMondayRecord {
  item_id: string
  group: string
  name: string
  dob: string
  phone: string
  address: string
  pos: string
  case_manager: string
  sent_to_cm: string
  referral_sent: string
  provider: string
  due_date: string
  appointment: string
  scheduled: string
  scheduled_complete: string
  visit: string
  sent_by: string
  agency_contact: string
  agency_phone: string
  stage: string
  referral_received: string
  qa_hold_reason: string
  discharge_reason: string
}

export interface LiveDrkRecord {
  patient_id: string
  name: string
  first_name: string
  last_name: string
  dob: string
  phone: string
  email: string
  address: string
  city: string
  mrn: string
  status: string
  facility: string
  home_health: string
  provider: string
  visit: string
  appointment: string
  observed_at: string
  sections: ArtifactSection[]
}

export interface LiveMatchField {
  field: string
  monday: string
  drk: string
  status: 'match' | 'mismatch' | 'missing'
}

export interface LiveMatch {
  status: 'match' | 'mismatch' | 'partial'
  fields: LiveMatchField[]
}

export interface LiveCandidate {
  item_id?: string
  patient_id?: string
  name: string
  dob?: string
  mrn?: string
}

export interface LivePatientResponse {
  slug?: string
  query?: { given_family: string; last_first: string; slug: string }
  observed_at?: string
  monday: LiveMondayRecord | null
  drk: LiveDrkRecord | null
  match: LiveMatch | null
  errors?: Array<{ source: string; message: string }>
  error?: string
  candidates?: { monday?: LiveCandidate[]; drk?: LiveCandidate[] }
}

export interface LiveSourceResult {
  status: number
  body: LivePatientResponse
  networkError: string | null
}

export async function fetchPatientSource(
  slug: string,
  source: Exclude<LiveSource, 'all'>,
  signal?: AbortSignal,
): Promise<LiveSourceResult> {
  try {
    const response = await fetch(
      `/api/patient/${encodeURIComponent(slug)}?source=${source}`,
      { signal },
    )
    const body = (await response.json()) as LivePatientResponse
    return { status: response.status, body, networkError: null }
  } catch (error) {
    if (signal?.aborted) throw error
    const message =
      error instanceof Error ? error.message : 'Patient API is unavailable'
    return {
      status: 0,
      body: { monday: null, drk: null, match: null },
      networkError: message,
    }
  }
}

export function displayValue(value: string | null | undefined): string {
  const text = (value ?? '').trim()
  return text || '—'
}

export function cityFromAddress(address: string | null | undefined): string {
  const parts = (address ?? '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
  if (parts.length >= 2) return parts[parts.length - 2] ?? address ?? ''
  return (address ?? '').trim()
}

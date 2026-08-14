import { useEffect, useState } from 'react'
import {
  fetchPatientSource,
  type LiveDrkRecord,
  type LiveMatch,
  type LiveMondayRecord,
  type LivePatientResponse,
} from './livePatient'

export interface LivePatientState {
  monday: LiveMondayRecord | null
  drk: LiveDrkRecord | null
  match: LiveMatch | null
  mondayStatus: number | null
  drkStatus: number | null
  mondayLoading: boolean
  drkLoading: boolean
  mondayError: string | null
  drkError: string | null
  mondayBody: LivePatientResponse | null
  drkBody: LivePatientResponse | null
}

const empty: LivePatientState = {
  monday: null,
  drk: null,
  match: null,
  mondayStatus: null,
  drkStatus: null,
  mondayLoading: true,
  drkLoading: true,
  mondayError: null,
  drkError: null,
  mondayBody: null,
  drkBody: null,
}

export function useLivePatient(slug: string): LivePatientState {
  const [state, setState] = useState<LivePatientState>(empty)

  useEffect(() => {
    const controller = new AbortController()
    setState(empty)

    void fetchPatientSource(slug, 'monday', controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setState((current) => ({
          ...current,
          mondayLoading: false,
          mondayStatus: result.status,
          monday: result.body.monday,
          mondayBody: result.body,
          mondayError:
            result.networkError ??
            sourceError(result.status, result.body, 'Monday'),
        }))
      })
      .catch(() => undefined)

    void fetchDrkWithRetry(slug, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setState((current) => ({
          ...current,
          drkLoading: false,
          drkStatus: result.status,
          drk: result.body.drk,
          match: result.body.match,
          drkBody: result.body,
          drkError:
            result.networkError ?? sourceError(result.status, result.body, 'DRK'),
        }))
      })
      .catch(() => undefined)

    return () => controller.abort()
  }, [slug])

  return state
}

function sourceError(
  status: number,
  body: LivePatientResponse,
  label: string,
): string | null {
  if (status === 200 || status === 404) return null
  if (status === 409) return `Multiple ${label} matches`
  const sourceError = body.errors?.find(
    (item) => item.source.toLowerCase() === label.toLowerCase(),
  )
  if (label === 'DRK' && (status === 502 || status === 0)) {
    return 'DRK chart is temporarily unavailable.'
  }
  if (sourceError?.message) return sourceError.message
  if (status === 502 || status === 0) return `${label} lookup failed`
  return body.error ?? `${label} lookup failed`
}

async function fetchDrkWithRetry(
  slug: string,
  signal: AbortSignal,
) {
  let result = await fetchPatientSource(slug, 'drk', signal)
  for (const delayMs of [500, 1_250]) {
    if (result.status !== 0 && result.status !== 502) return result
    await delay(delayMs, signal)
    result = await fetchPatientSource(slug, 'drk', signal)
  }
  return result
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(resolve, milliseconds)
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timeout)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

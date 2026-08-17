import { useEffect, useState } from 'react'

const RESERVED_SEGMENTS = new Set([
  'referrals',
  'src',
  'assets',
  'node_modules',
  'overview',
  'intake',
  'assignment',
  'handoff',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
  'patient',
  'api',
])

export function slugifyPatientKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function givenFamilySlug(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (trimmed.includes(',')) {
    const [family, given] = trimmed.split(',', 2)
    return slugifyPatientKey(`${given} ${family}`)
  }
  return slugifyPatientKey(trimmed)
}

export function nameMatchKey(value: string): string {
  return slugifyPatientKey(value).split('-').filter(Boolean).sort().join('-')
}

export function patientKeyFromPath(pathname: string): string | null {
  const parts = pathname
    .split('?')[0]
    .split('#')[0]
    .split('/')
    .map((part) => decodeURIComponent(part))
    .filter(Boolean)
  if (parts.length === 1 && !RESERVED_SEGMENTS.has(parts[0])) {
    return parts[0]
  }
  if (parts.length === 2 && parts[0] === 'patient' && parts[1]) {
    return parts[1]
  }
  return null
}

export function patientProfilePath(nameOrId: string): string {
  const slug = nameOrId.includes(',')
    ? givenFamilySlug(nameOrId)
    : slugifyPatientKey(nameOrId)
  return `/${encodeURIComponent(slug)}`
}

export function navigateAppPath(path: string) {
  if (window.location.pathname === path) return
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function usePatientPathKey(): string | null {
  const [pathname, setPathname] = useState(() => window.location.pathname)

  useEffect(() => {
    const sync = () => setPathname(window.location.pathname)
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  return patientKeyFromPath(pathname)
}

import rosters from './rosters.json'

export interface WcwCaseManager {
  name: string
  email: string | null
  phone: string | null
}

export interface WcwProvider {
  name: string
  npi: string | null
  city: string
  phone: string | null
  email: string | null
}

export interface WcwFacility {
  name: string
  address: string
  phone: string
}

export const WCW_CASE_MANAGERS = rosters.caseManagers as WcwCaseManager[]
export const WCW_PROVIDERS = rosters.providers as WcwProvider[]
export const WCW_FACILITIES = rosters.facilities as WcwFacility[]

export const WCW_NETWORK = {
  caseManagerCount: rosters.caseManagerCount as number,
  providerCount: rosters.providerCount as number,
  facilityCount: rosters.facilityCount as number,
} as const

const CITY_FALLBACKS: Record<string, string[]> = {
  riverside: ['Rancho Cucamonga', 'Menifee', 'Burbank', 'Los Angeles'],
  'long beach': ['Los Angeles', 'South Gate', 'Burbank'],
  downey: ['South Gate', 'Los Angeles', 'Burbank'],
  anaheim: ['Placentia', 'Burbank', 'Los Angeles'],
  gardena: ['Los Angeles', 'South Gate', 'Burbank'],
  compton: ['Los Angeles', 'South Gate', 'Burbank'],
  'san pedro': ['Los Angeles', 'Burbank'],
  burbank: ['Burbank', 'Pasadena', 'Los Angeles'],
}

export function providersInCity(city: string, limit = 5): WcwProvider[] {
  const needle = city.trim().toLowerCase()
  const direct = WCW_PROVIDERS.filter((p) => p.city.toLowerCase() === needle)
  if (direct.length >= limit) return direct.slice(0, limit)

  const fallbacks = CITY_FALLBACKS[needle] ?? ['Burbank', 'Los Angeles']
  const seen = new Set(direct.map((p) => p.name))
  const merged = [...direct]
  for (const cityName of fallbacks) {
    for (const provider of WCW_PROVIDERS) {
      if (provider.city.toLowerCase() !== cityName.toLowerCase()) continue
      if (seen.has(provider.name)) continue
      seen.add(provider.name)
      merged.push(provider)
      if (merged.length >= limit) return merged
    }
  }
  return merged.slice(0, limit)
}

export function findCaseManager(name: string): WcwCaseManager | undefined {
  return WCW_CASE_MANAGERS.find((c) => c.name === name)
}

export function findFacility(substring: string): WcwFacility | undefined {
  const needle = substring.toLowerCase()
  return WCW_FACILITIES.find((f) => f.name.toLowerCase().includes(needle))
}

export function pickFacility(...candidates: string[]): WcwFacility {
  for (const c of candidates) {
    const hit = findFacility(c)
    if (hit) return hit
  }
  return WCW_FACILITIES[0]
}

export function requireCaseManager(name: string): WcwCaseManager {
  return findCaseManager(name) ?? WCW_CASE_MANAGERS[0]
}

import providerRoster from '../../../../../company_providers.json'

export interface ProviderOption {
  id: string
  name: string
  npi?: string
  city?: string
  phone?: string
  email?: string
}

type ProviderSource = {
  source_row: number
  name: string
  npi: string | null
  city: string | null
  phone_number: string | null
  email: string | null
}

export const PROVIDER_OPTIONS: ProviderOption[] = (
  providerRoster.providers as ProviderSource[]
).map((provider) => ({
  id: String(provider.source_row),
  name: provider.name,
  npi: provider.npi ?? undefined,
  city: provider.city ?? undefined,
  phone: provider.phone_number ?? undefined,
  email: provider.email ?? undefined,
}))

const SUGGESTED_PROVIDER_NAMES: Record<string, string> = {
  'helen-park': 'Charles Cho',
  'irene-cho': 'Daniel Rowady',
  'patricia-johnson': 'Aaron Currie',
  'thomas-reed': 'Charles Cho',
  'maria-alvarez': 'Daniel Rowady',
  'nancy-liu': 'Aaron Currie',
  'james-carter': 'Daniel Rowady',
  'linda-nguyen': 'Aaron Currie',
  'david-ruiz': 'Aaron Currie',
}

interface ProviderPatientLocation {
  city: string
  state: string
  postalCode: string
}

const PATIENT_LOCATIONS: Record<string, ProviderPatientLocation> = {
  'helen-park': { city: 'Los Angeles', state: 'CA', postalCode: '90012' },
  'irene-cho': { city: 'Pasadena', state: 'CA', postalCode: '91101' },
  'betty-hayes': { city: 'Needles', state: 'CA', postalCode: '92363' },
  'patricia-johnson': { city: 'Burbank', state: 'CA', postalCode: '91501' },
  'thomas-reed': { city: 'Los Angeles', state: 'CA', postalCode: '90027' },
  'maria-alvarez': { city: 'Pasadena', state: 'CA', postalCode: '91103' },
  'nancy-liu': { city: 'Burbank', state: 'CA', postalCode: '91505' },
  'james-carter': { city: 'Gardena', state: 'CA', postalCode: '90249' },
  'linda-nguyen': { city: 'Los Angeles', state: 'CA', postalCode: '90045' },
}

export function providerPatientLocation(patientId: string): string {
  return PATIENT_LOCATIONS[patientId]?.city ?? 'Location unavailable'
}

export function providerPatientLocationDisplay(patientId: string): string {
  const location = PATIENT_LOCATIONS[patientId]
  return location
    ? `${location.city}, ${location.state} ${location.postalCode}`
    : 'Location unavailable'
}

export function providersForPatientLocation(
  patientId: string,
): ProviderOption[] {
  const location = providerPatientLocation(patientId)
  return PROVIDER_OPTIONS.filter(
    (provider) =>
      provider.city?.trim().toLocaleLowerCase() ===
      location.trim().toLocaleLowerCase(),
  )
}

export function providerSuggestion(patientId: string): ProviderOption {
  const suggestedName = SUGGESTED_PROVIDER_NAMES[patientId]
  return (
    PROVIDER_OPTIONS.find((provider) => provider.name === suggestedName) ??
    PROVIDER_OPTIONS[0]
  )
}

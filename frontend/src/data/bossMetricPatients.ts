import type { BossMetricsScope } from './bossMetrics'

export interface BossMetricPatient {
  id: string
  name: string
  owner: string
  status: string
  dateOfBirth: string
  phone: string
  address: string
}

const DEMO_PATIENTS = [
  {
    name: 'Maria Alvarez',
    owner: 'Jennifer Kim',
    dateOfBirth: '02/14/1958',
    phone: '(555) 014-2381',
    address: '4821 Palm Grove Dr, Riverside, CA 92501',
  },
  {
    name: 'James Carter',
    owner: 'Megan Rivera',
    dateOfBirth: '09/03/1946',
    phone: '(555) 017-9204',
    address: '1708 Magnolia Ave, Long Beach, CA 90806',
  },
  {
    name: 'Linda Nguyen',
    owner: 'Sarah Thompson',
    dateOfBirth: '06/22/1951',
    phone: '(555) 011-6638',
    address: '921 Harbor View Ln, San Pedro, CA 90731',
  },
  {
    name: 'Robert Williams',
    owner: 'Jennifer Kim',
    dateOfBirth: '11/18/1962',
    phone: '(555) 013-4472',
    address: '605 Cypress St, Anaheim, CA 92805',
  },
  {
    name: 'Evelyn Brooks',
    owner: 'Daniel Foster',
    dateOfBirth: '01/07/1943',
    phone: '(555) 016-2201',
    address: '2814 E Willow St, Compton, CA 90221',
  },
  {
    name: 'Thomas Reed',
    owner: 'Megan Rivera',
    dateOfBirth: '04/29/1955',
    phone: '(555) 018-3047',
    address: '733 Lakewood Blvd, Downey, CA 90240',
  },
  {
    name: 'Patricia Johnson',
    owner: 'Sarah Thompson',
    dateOfBirth: '08/11/1948',
    phone: '(555) 015-7819',
    address: '449 W Rosecrans Ave, Gardena, CA 90248',
  },
  {
    name: 'Samuel Ortiz',
    owner: 'Daniel Foster',
    dateOfBirth: '12/09/1959',
    phone: '(555) 012-4865',
    address: '1187 Atlantic Ave, Carson, CA 90745',
  },
] as const

function hash(value: string): number {
  return [...value].reduce((total, character) => total + character.charCodeAt(0), 0)
}

export function buildBossMetricPatients(
  scope: BossMetricsScope,
  metricId: string,
  metricLabel: string,
): BossMetricPatient[] {
  const offset = hash(`${scope}-${metricId}`) % DEMO_PATIENTS.length

  return Array.from({ length: 8 }, (_, index) => {
    const patient = DEMO_PATIENTS[(offset + index) % DEMO_PATIENTS.length]
    return {
      id: `REF-${String(24018 + offset * 7 + index).padStart(5, '0')}`,
      name: patient.name,
      owner: patient.owner,
      status: metricLabel,
      dateOfBirth: patient.dateOfBirth,
      phone: patient.phone,
      address: patient.address,
    }
  })
}

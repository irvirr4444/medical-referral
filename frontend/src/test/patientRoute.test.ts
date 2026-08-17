import { describe, expect, it } from 'vitest'
import {
  givenFamilySlug,
  nameMatchKey,
  patientKeyFromPath,
  patientProfilePath,
  slugifyPatientKey,
} from '../features/automation/patientRoute'

describe('patientRoute', () => {
  it('reads /patient/:id and /:id', () => {
    expect(patientKeyFromPath('/patient/butler-alva')).toBe('butler-alva')
    expect(patientKeyFromPath('/alva-butler')).toBe('alva-butler')
    expect(patientKeyFromPath('/frank-owens')).toBe('frank-owens')
    expect(patientKeyFromPath('/intake')).toBeNull()
    expect(patientKeyFromPath('/')).toBeNull()
    expect(patientKeyFromPath('/referrals/file.pdf')).toBeNull()
    expect(patientKeyFromPath('/api/patient/alva-butler')).toBeNull()
  })

  it('slugifies last-first and given-family names', () => {
    expect(slugifyPatientKey('Butler, Alva')).toBe('butler-alva')
    expect(givenFamilySlug('Butler, Alva')).toBe('alva-butler')
    expect(givenFamilySlug('Alva Butler')).toBe('alva-butler')
    expect(nameMatchKey('butler-alva')).toBe('alva-butler')
    expect(nameMatchKey('alva-butler')).toBe('alva-butler')
    expect(patientProfilePath('Butler, Alva')).toBe('/alva-butler')
  })
})

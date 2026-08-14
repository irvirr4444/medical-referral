import { describe, expect, it } from 'vitest'
import { createInitialState } from '../state/demoReducer'
import {
  patientProfile,
  resolvePatientKey,
} from '../features/automation/patientProfile'

describe('patientProfile', () => {
  it('resolves a patient by id or name slug', () => {
    expect(resolvePatientKey('butler-alva')?.patientId).toBe('butler-alva')
    expect(resolvePatientKey('alva-butler')?.patientId).toBe('butler-alva')
    expect(resolvePatientKey('Butler, Alva')?.patientId).toBe('butler-alva')
    expect(resolvePatientKey('not-a-patient')).toBeNull()
  })

  it('builds the intake skim for Butler', () => {
    const profile = patientProfile('butler-alva', createInitialState())
    expect(profile?.patientName).toMatch(/Butler, Alva/i)
    expect(profile?.currentStageId).toBe('intake')
    expect(profile?.blocker).toBeTruthy()
    expect(profile?.providerLabel).toBe('Not selected')
    expect(profile?.mondayOps.visit).toBe('—')
    expect(profile?.extractedSections.some((section) => section.id === 'required-fields')).toBe(
      true,
    )
    expect(profile?.timeline.length).toBeGreaterThan(0)
  })

  it('fills scheduling columns once the journey has reached that stage', () => {
    const profile = patientProfile('maria-alvarez', createInitialState())
    expect(profile?.currentStageId).toBe('scheduling')
    expect(profile?.mondayOps.referralSent).not.toBe('—')
    expect(profile?.extractedSections.length).toBe(0)
  })
})

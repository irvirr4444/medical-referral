import { describe, expect, it } from 'vitest'
import { createInitialState, demoReducer } from '../state/demoReducer'
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
    expect(profile?.mondayOps.appointment).toBe('—')
    expect(profile?.extractedSections.length).toBe(0)
  })

  it('writes the live appointment onto the profile after scheduling', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'SELECT_SCHEDULING_SLOT',
      patientId: 'maria-alvarez',
      slotId: 'maria-today-1530',
    })
    state = demoReducer(state, {
      type: 'COMPLETE_PATIENT_SCHEDULE',
      patientId: 'maria-alvarez',
      scheduledAt: 'August 14, 2026 at 3:40 PM',
    })
    const profile = patientProfile('maria-alvarez', state)
    expect(profile?.mondayOps.appointment).toBe('August 14, 2026')
    expect(profile?.mondayOps.scheduled).toBe('Scheduled')
    expect(profile?.mondayOps.scheduledComplete).toBe('Yes')
  })
})

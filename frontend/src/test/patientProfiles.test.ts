import { describe, expect, it } from 'vitest'
import {
  BUTLER_PROFILE_ID,
  getPatientProfile,
  mapCanonicalReferralToProfile,
} from '../data/patientProfiles'
import butlerCanonicalReferral from '../features/automation/fixtures/butlerCanonicalReferral.json'
import type { CanonicalReferral } from '../features/automation/canonicalReferral'

describe('patientProfiles', () => {
  it('maps Butler Alva canonical referral into a read-only profile view model', () => {
    const profile = mapCanonicalReferralToProfile(
      BUTLER_PROFILE_ID,
      butlerCanonicalReferral as unknown as CanonicalReferral,
    )

    expect(profile.profileId).toBe(BUTLER_PROFILE_ID)
    expect(profile.referralId).toBe('ref_demo_butler_alva_001')
    expect(profile.identity.displayName).toBe('Alva Butler')
    expect(profile.identity.legalName).toBe('BUTLER, ALVA')
    expect(profile.identity.dateOfBirth).toBe('10/04/1940')
    expect(profile.identity.phone).toBe('(260) 438-4646')
    expect(profile.identity.address).toContain('APOLLO BEACH')
    expect(profile.identity.sourcePatientId).toBe('6227')
    expect(profile.identity.mrn).toBeNull()

    expect(profile.referralSource.providerName).toBe('YVETTE GUZMAN, APRN DNP')
    expect(profile.referralSource.fileName).toBe('BUTLER, ALVA demo.pdf')
    expect(profile.referralSource.documentType).toBe('EHR patient chart')

    expect(profile.clinicalSummary).toMatch(/cardiopulmonary/i)
    expect(profile.diagnoses[0]).toMatchObject({
      code: 'I25.10',
      isPrimary: true,
    })
    expect(profile.insurances).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          payerName: 'MEDICARE PART B',
          insuranceType: 'Primary',
        }),
        expect.objectContaining({
          payerName: 'FLORIDA BLUE',
          insuranceType: 'Secondary',
        }),
      ]),
    )
    expect(profile.requestedServices).toEqual([])
    expect(profile.warnings.length).toBeGreaterThan(0)
    expect(profile.fieldQuality).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: 'home_health_or_hospice',
          status: 'missing',
        }),
      ]),
    )
    expect(profile.provenance.identity.source).toBe('canonical_referral')
    expect(profile.unavailableSections.careTeam.available).toBe(false)
    expect(profile.unavailableSections.appointment.available).toBe(false)
    expect(profile.unavailableSections.recentActivity.available).toBe(false)
  })

  it('includes Butler workflow stage, step, and platform presence', () => {
    const profile = getPatientProfile(BUTLER_PROFILE_ID)
    expect(profile?.workflow).toMatchObject({
      currentStageId: 'intake',
      currentStepId: 'interpret-reply',
      currentStepName: 'Interpret the reviewer reply',
      monday: { present: false },
      drk: { present: false },
    })
    expect(profile?.workflow?.stages[0]).toMatchObject({
      stageId: 'intake',
      status: 'current',
      currentStepNumber: 12,
    })
    expect(profile?.workflow?.stages[1]).toMatchObject({
      stageId: 'handoff',
      status: 'upcoming',
    })
  })

  it('returns the registered Butler profile by id', () => {
    const profile = getPatientProfile(BUTLER_PROFILE_ID)
    expect(profile?.identity.displayName).toBe('Alva Butler')
    expect(getPatientProfile('missing-profile')).toBeNull()
  })
})

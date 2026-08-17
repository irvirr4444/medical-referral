import { describe, expect, it } from 'vitest'
import { detailForPatientStep } from '../features/automation/ops'
import { overlayIntakeDetail } from '../features/automation/overlayIntakeDetail'
import { repeatableItemCount } from '../features/automation/intakeRecords'

describe('overlayIntakeDetail', () => {
  it('treats an edited required field as present without reopening original gaps', () => {
    const detail = detailForPatientStep(
      'intake',
      'gonzalez-eric',
      'extract-and-verify',
    )
    expect(detail.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 5,
        missingLabels: ['Home health or hospice agency'],
        unclearLabels: ['Patient address'],
        thresholdMet: false,
      }),
    )

    const afterAgency = overlayIntakeDetail(detail, {
      home_health_or_hospice: 'VNA of Southern California',
    })
    expect(afterAgency.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 6,
        missingLabels: [],
        unclearLabels: ['Patient address'],
        thresholdMet: false,
      }),
    )

    const afterAddress = overlayIntakeDetail(detail, {
      home_health_or_hospice: 'VNA of Southern California',
      'patient.address': '153 E 110th St, Los Angeles 90061',
    })
    expect(afterAddress.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 7,
        missingLabels: [],
        unclearLabels: [],
        thresholdMet: true,
      }),
    )
    expect(afterAddress.example?.feedDecision?.identityLine).toMatch(/Gonzalez/i)
  })

  it('replaces saved list rows and can mark insurance or clinical present', () => {
    const detail = detailForPatientStep(
      'intake',
      'gonzalez-eric',
      'extract-and-verify',
    )
    const insurance = detail.example?.artifactSections?.find(
      (section) => section.id === 'insurance',
    )
    const diagnoses = detail.example?.artifactSections?.find(
      (section) => section.id === 'diagnoses',
    )
    expect(insurance?.repeatable).toBe(true)
    expect(repeatableItemCount(diagnoses!)).toBe(28)
    expect(repeatableItemCount(insurance!)).toBe(1)

    const withRows = overlayIntakeDetail(detail, {}, {
      insurance: [
        ...(insurance?.fields ?? []),
        {
          label: 'Type',
          value: 'Secondary',
          rowId: 'insurances.new-1',
          choice: 'insurance-type',
        },
        {
          label: 'Payer',
          value: 'Blue Shield PPO',
          rowId: 'insurances.new-1',
          presence: true,
        },
      ],
      diagnoses: [
        ...(diagnoses?.fields ?? []),
        {
          label: 'Code',
          value: 'I10',
          rowId: 'diagnoses.new-1',
          presence: true,
        },
        {
          label: 'Description',
          value: 'Essential hypertension',
          rowId: 'diagnoses.new-1',
          presence: true,
        },
      ],
    })
    const overlaidInsurance = withRows.example?.artifactSections?.find(
      (section) => section.id === 'insurance',
    )
    const overlaidDiagnoses = withRows.example?.artifactSections?.find(
      (section) => section.id === 'diagnoses',
    )
    expect(repeatableItemCount(overlaidInsurance!)).toBe(2)
    expect(
      overlaidInsurance?.fields.some(
        (field) => field.label === 'Payer' && field.value === 'Blue Shield PPO',
      ),
    ).toBe(true)
    expect(
      overlaidDiagnoses?.fields.some(
        (field) => field.label === 'Code' && field.value === 'I10',
      ),
    ).toBe(true)
    expect(withRows.example?.feedDecision?.completeCount).toBe(5)

    const missingInsurance = {
      ...detail,
      example: {
        ...detail.example!,
        feedDecision: {
          ...detail.example!.feedDecision!,
          completeCount: 4,
          missingLabels: [
            'Home health or hospice agency',
            'Insurance information',
          ],
        },
      },
    }
    const filledInsurance = overlayIntakeDetail(missingInsurance, {}, {
      insurance: [
        {
          label: 'Payer',
          value: 'LA CARE HLTH PLAN MEDICAID HMO',
          rowId: 'insurances.0',
          presence: true,
        },
      ],
    })
    expect(filledInsurance.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 5,
        missingLabels: ['Home health or hospice agency'],
      }),
    )

    const missingClinical = {
      ...detail,
      example: {
        ...detail.example!,
        feedDecision: {
          ...detail.example!.feedDecision!,
          completeCount: 4,
          missingLabels: [
            'Home health or hospice agency',
            'Wound or clinical information',
          ],
        },
      },
    }
    const filledClinical = overlayIntakeDetail(missingClinical, {}, {
      diagnoses: [
        {
          label: 'Code',
          value: 'L03.314',
          rowId: 'diagnoses.0',
          presence: true,
        },
      ],
    })
    expect(filledClinical.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 5,
        missingLabels: ['Home health or hospice agency'],
      }),
    )

    const filledAllergies = overlayIntakeDetail(missingClinical, {}, {
      allergies: [
        {
          label: 'No known allergies',
          value: 'Yes',
          rowId: 'allergies.nka',
          fixed: true,
          presence: true,
        },
      ],
    })
    expect(filledAllergies.example?.feedDecision).toEqual(
      expect.objectContaining({
        completeCount: 5,
        missingLabels: ['Home health or hospice agency'],
      }),
    )
  })
})

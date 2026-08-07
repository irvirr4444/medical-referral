import type { AuditEvent, ReferralRecord, RequiredField, WorkflowStage } from '../types'

function fields(name: string, dob: string, phone: string, address: string, agency: string, clinical: string, insurance: string): RequiredField[] {
  return [
    { key: 'patient_name', label: 'Patient name', value: name, status: 'complete', evidencePage: 1, evidenceQuote: name, confidence: 0.98 },
    { key: 'date_of_birth', label: 'Date of birth', value: dob, status: 'complete', evidencePage: 1, evidenceQuote: dob, confidence: 0.97 },
    { key: 'contact_number', label: 'Contact number', value: phone, status: 'complete', evidencePage: 1, evidenceQuote: phone, confidence: 0.95 },
    { key: 'patient_address', label: 'Patient address', value: address, status: 'complete', evidencePage: 1, evidenceQuote: address, confidence: 0.96 },
    { key: 'home_health', label: 'Home-health/hospice agency', value: agency, status: 'complete', evidencePage: 2, evidenceQuote: agency, confidence: 0.94 },
    { key: 'clinical', label: 'Wound/clinical information', value: clinical, status: 'complete', evidencePage: 3, evidenceQuote: clinical, confidence: 0.93 },
    { key: 'insurance', label: 'Insurance information', value: insurance, status: 'complete', evidencePage: 2, evidenceQuote: insurance, confidence: 0.95 },
  ]
}

function timeline(events: Array<Omit<AuditEvent, 'id'>>, prefix: string): AuditEvent[] {
  return events.map((event, index) => ({
    id: `${prefix}-${index}`,
    ...event,
  }))
}

function priorReferral(input: {
  id: string
  patientName: string
  receivedAt: string
  referralSource: string
  stage: WorkflowStage
  cityLine: string
  diagnosis: string
  mondayStatus?: ReferralRecord['mondayStatus']
  drkStatus?: ReferralRecord['drkStatus']
  confirmed?: boolean
}): ReferralRecord {
  const phone = '(562) 555-0100'
  const dob = 'January 1, 1950'
  return {
    id: input.id,
    patientName: input.patientName,
    receivedAt: input.receivedAt,
    sender: 'referrals@partner.example',
    subject: `Referral — ${input.patientName}`,
    referralSource: input.referralSource,
    pdfFilename: `${input.id}.pdf`,
    samplePdf: '',
    pageCount: 12,
    dateOfBirth: dob,
    phone,
    address: input.cityLine,
    homeHealthOrHospice: input.referralSource,
    diagnosis: input.diagnosis,
    insurance: 'Medicare',
    requestedService: 'Wound evaluation',
    referringProvider: 'Partner clinical team',
    medications: [],
    allergies: [],
    clinicalSummary: input.diagnosis,
    requiredFields: fields(
      input.patientName,
      dob,
      phone,
      input.cityLine,
      input.referralSource,
      input.diagnosis,
      'Medicare',
    ),
    completenessScore: '7/7',
    duplicateStatus: 'clear',
    outcome: 'ready',
    minutesReturned: 28,
    demoPurpose: 'Earlier inbox batch — already in flight',
    mondayPreview: {
      itemName: input.patientName,
      board: 'Master Sheet',
      group: 'In intake',
      columns: [
        { label: 'Patient', value: input.patientName },
        { label: 'Referring facility', value: input.referralSource },
        { label: 'Diagnosis', value: input.diagnosis },
      ],
      updateComment: 'Prepared earlier today.',
      agencyRelation: input.referralSource,
      blockers: [],
      itemId: input.stage === 'monday_ready' || input.stage === 'drk_ready' ? `MS-${input.id}` : undefined,
    },
    drkDraft: {
      demographics: [
        { label: 'Name', value: input.patientName },
        { label: 'Date of birth', value: dob },
      ],
      contact: [{ label: 'Phone', value: phone }],
      address: [{ label: 'Address', value: input.cityLine }],
      emergencyContact: [{ label: 'Emergency contact', value: 'On file' }],
      admission: [{ label: 'Referral reason', value: input.diagnosis }],
      insurance: [{ label: 'Payer', value: 'Medicare' }],
      diagnoses: [input.diagnosis],
      requestedService: 'Wound evaluation',
      unresolvedLookups: [],
      duplicateCheck: 'Clear',
    },
    impactReceipt: {
      pagesAnalyzed: 12,
      valuesExtracted: 20,
      requiredFieldsVerified: 7,
      duplicateSearches: 1,
      destinationRecordsPrepared: 2,
      manualActionsAvoided: 8,
      minutesReturned: 28,
    },
    stage: input.stage,
    confirmed: input.confirmed ?? (input.stage !== 'reviewed' && input.stage !== 'extracted'),
    followUpPrepared: false,
    mondayStatus: input.mondayStatus ?? (input.stage === 'monday_ready' || input.stage === 'drk_ready' ? 'created' : input.stage === 'confirmed' ? 'ready' : 'ready'),
    drkStatus: input.drkStatus ?? (input.stage === 'drk_ready' ? 'face_sheet_ready' : 'draft_ready'),
    timeline: timeline(
      [
        {
          timestamp: input.receivedAt,
          label: 'Referral email received',
          result: 'Processed earlier today',
          actor: 'Outlook inbox',
          humanRequired: false,
        },
      ],
      input.id,
    ),
    processed: true,
    inboxBatch: false,
  }
}

/** Mid-morning referrals already past intake — keep the spine from looking empty. */
export function createPriorBatchReferrals(): ReferralRecord[] {
  return [
    priorReferral({
      id: 'prior-helen-park',
      patientName: 'Helen Park',
      receivedAt: '6:50 AM',
      referralSource: 'Anaheim Healthcare Center',
      stage: 'drk_ready',
      cityLine: 'Anaheim, CA',
      diagnosis: 'Venous ulcer left calf',
      mondayStatus: 'created',
      drkStatus: 'face_sheet_ready',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-samuel-ortiz',
      patientName: 'Samuel Ortiz',
      receivedAt: '7:05 AM',
      referralSource: 'Burbank Retirement Villa West',
      stage: 'drk_ready',
      cityLine: 'Burbank, CA',
      diagnosis: 'Diabetic ulcer right toe',
      mondayStatus: 'created',
      drkStatus: 'assisted_entry',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-irene-cho',
      patientName: 'Irene Cho',
      receivedAt: '7:12 AM',
      referralSource: 'Belmont Village Senior Living - Burbank',
      stage: 'monday_ready',
      cityLine: 'Burbank, CA',
      diagnosis: 'Stage 2 sacral pressure injury',
      mondayStatus: 'created',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-marcus-feldman',
      patientName: 'Marcus Feldman',
      receivedAt: '7:20 AM',
      referralSource: 'Anaheim Crown Plaza',
      stage: 'monday_ready',
      cityLine: 'Anaheim, CA',
      diagnosis: 'Post-op wound dehiscence',
      mondayStatus: 'created',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-nancy-liu',
      patientName: 'Nancy Liu',
      receivedAt: '7:28 AM',
      referralSource: 'South Gate Home Health',
      stage: 'confirmed',
      cityLine: 'South Gate, CA',
      diagnosis: 'Arterial ulcer left foot',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-david-ruiz',
      patientName: 'David Ruiz',
      receivedAt: '7:35 AM',
      referralSource: 'Pasadena Wound Partners',
      stage: 'confirmed',
      cityLine: 'Pasadena, CA',
      diagnosis: 'Pressure injury right heel',
      confirmed: true,
    }),
    priorReferral({
      id: 'prior-anita-gomez',
      patientName: 'Anita Gomez',
      receivedAt: '7:48 AM',
      referralSource: 'Rancho Cucamonga SNF',
      stage: 'reviewed',
      cityLine: 'Rancho Cucamonga, CA',
      diagnosis: 'Venous stasis ulcer bilateral',
      confirmed: false,
      mondayStatus: 'ready',
    }),
    priorReferral({
      id: 'prior-frank-owens',
      patientName: 'Frank Owens',
      receivedAt: '7:55 AM',
      referralSource: 'Los Angeles Home Health',
      stage: 'reviewed',
      cityLine: 'Los Angeles, CA',
      diagnosis: 'Diabetic ulcer midfoot',
      confirmed: false,
      mondayStatus: 'ready',
    }),
    priorReferral({
      id: 'prior-susan-park',
      patientName: 'Susan Park',
      receivedAt: '8:02 AM',
      referralSource: 'Placentia Care Center',
      stage: 'reviewed',
      cityLine: 'Placentia, CA',
      diagnosis: 'Surgical wound left thigh',
      confirmed: false,
      mondayStatus: 'ready',
    }),
    priorReferral({
      id: 'prior-george-chen',
      patientName: 'George Chen',
      receivedAt: '8:10 AM',
      referralSource: 'Menifee Skilled Nursing',
      stage: 'extracted',
      cityLine: 'Menifee, CA',
      diagnosis: 'Unstageable pressure injury',
      confirmed: false,
      mondayStatus: 'not_ready',
      drkStatus: 'draft_ready',
    }),
    priorReferral({
      id: 'prior-betty-hayes',
      patientName: 'Betty Hayes',
      receivedAt: '8:16 AM',
      referralSource: 'Burbank Congregate Living Center',
      stage: 'extracted',
      cityLine: 'Burbank, CA',
      diagnosis: 'Chronic wound right shin',
      confirmed: false,
      mondayStatus: 'not_ready',
      drkStatus: 'draft_ready',
    }),
  ]
}

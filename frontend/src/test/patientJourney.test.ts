import { describe, expect, it } from 'vitest'
import {
  buildJourneyRoster,
  buildPatientJourney,
  DEFAULT_JOURNEY_PATIENT_ID,
  JOURNEY_PATIENTS,
  JOURNEY_REFERRAL_ID,
  MARIA_JOURNEY_STEPS,
  referralForJourneyPatient,
  scenarioContainingCase,
  seedJourneyProgress,
} from '../data/patientJourney'
import { createInitialReferrals } from '../data/referrals'
import { createInitialWorkflowScenarios } from '../data/workflowScenarios'
import { createInitialState, demoReducer } from '../state/demoReducer'

describe('patient journey catalog', () => {
  it('builds a realistic census distributed across every workflow stage', () => {
    const scenarios = seedJourneyProgress(createInitialWorkflowScenarios())
    const roster = buildJourneyRoster(scenarios)
    expect(roster).toHaveLength(24)

    expect(roster.slice(0, 7).map((item) => item.patient.scenarioLabel)).toEqual([
      'Acknowledgement prepared',
      'Monday.com / DRK operation outcomes',
      'Physician referral ready',
      'Provider selected but not contacted',
      'New source document received',
      'Not eligible for handoff',
      'Private review draft prepared',
    ])

    expect(new Set(roster.map(({ journey }) => journey.current?.stage))).toEqual(
      new Set([
        'intake',
        'handoff',
        'assignment',
        'provider',
        'scheduling',
        'end-of-day',
        'weekly',
      ]),
    )

    for (const { patient, journey } of roster) {
      expect(journey.steps).toHaveLength(7)
      expect(journey.completedCount).toBe(patient.stuckAtIndex)
      expect(journey.current?.stage).toBe(patient.steps[patient.stuckAtIndex]?.stage)
      expect(journey.complete).toBe(false)
      for (const step of journey.steps) {
        expect(step.caseItem).not.toBeNull()
        expect(step.status).not.toBe('missing')
      }
    }

    expect(referralForJourneyPatient(createInitialReferrals())?.id).toBe(JOURNEY_REFERRAL_ID)
  })

  it('assigns every journey step to exactly one roster patient', () => {
    const caseIds = JOURNEY_PATIENTS.flatMap((patient) =>
      patient.steps.map((step) => step.caseId),
    )
    expect(new Set(caseIds).size).toBe(caseIds.length)
  })

  it('uses at least 22 distinct live queue paths for the current census', () => {
    const scenarios = seedJourneyProgress(createInitialWorkflowScenarios())
    const titles = new Set(
      buildJourneyRoster(scenarios).map(({ journey }) =>
        scenarioContainingCase(scenarios, journey.current!.caseId)?.title,
      ),
    )
    expect(titles.size).toBeGreaterThanOrEqual(22)
  })

  it('builds Maria’s 7 steps linked to real case IDs', () => {
    const scenarios = seedJourneyProgress(createInitialWorkflowScenarios())
    const journey = buildPatientJourney(scenarios, DEFAULT_JOURNEY_PATIENT_ID)
    expect(journey.steps).toHaveLength(7)
    expect(journey.patientName).toBe('Maria Alvarez')
    expect(journey.current?.caseId).toBe('ho-ack-1')
    for (const step of MARIA_JOURNEY_STEPS) {
      const found = scenarios.some((scenario) =>
        scenario.cases.some(
          (item) => item.id === step.caseId && item.patientName === 'Maria Alvarez',
        ),
      )
      expect(found).toBe(true)
    }
  })
})

describe('patient journey actions', () => {
  it('advancing the remaining steps completes Maria’s path and returns minutes', () => {
    let state = createInitialState()
    const seeded = state.scenarioMinutesReturned
    const initialJourney = buildPatientJourney(
      state.workflowScenarios,
      DEFAULT_JOURNEY_PATIENT_ID,
    )
    const expectedPath = MARIA_JOURNEY_STEPS.reduce((sum, step) => {
      const caseItem = state.workflowScenarios
        .flatMap((scenario) => scenario.cases)
        .find((item) => item.id === step.caseId)!
      return sum + caseItem.minutesReturned
    }, 0)
    const expectedRemaining = initialJourney.steps
      .filter((step) => !step.done)
      .reduce((sum, step) => sum + step.minutesReturned, 0)

    for (let i = 0; i < initialJourney.totalSteps - initialJourney.completedCount; i += 1) {
      state = demoReducer(state, { type: 'ADVANCE_JOURNEY' })
    }

    const journey = buildPatientJourney(state.workflowScenarios, DEFAULT_JOURNEY_PATIENT_ID)
    expect(journey.complete).toBe(true)
    expect(journey.completedCount).toBe(7)
    expect(journey.minutesOnPath).toBe(expectedPath)
    expect(state.scenarioMinutesReturned).toBe(seeded + expectedRemaining)
    expect(state.activePage).toBe('weekly')
    expect(state.journeyFocusCaseId).toBe('wk-seen-2')
  })

  it('SELECT_JOURNEY_PATIENT jumps to that patient’s intake case', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'SELECT_JOURNEY_PATIENT', patientId: 'thomas-reed' })
    expect(state.selectedJourneyPatientId).toBe('thomas-reed')
    expect(state.activePage).toBe('intake')
    expect(state.journeyFocusCaseId).toBe('in-ready-2')

    state = demoReducer(state, { type: 'SELECT_JOURNEY_PATIENT', patientId: 'linda-nguyen' })
    expect(state.activePage).toBe('handoff')
    expect(state.journeyFocusCaseId).toBe('ho-inelig-1')
  })

  it('FOCUS_JOURNEY_STEP navigates activePage without opening the PDF workspace', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'FOCUS_JOURNEY_STEP', caseId: 'ho-one-1' })
    expect(state.activePage).toBe('assignment')
    expect(state.journeyFocusCaseId).toBe('ho-one-1')
    expect(state.scenarioFilter).toBe('all')
    expect(state.selectedReferralId).toBeNull()

    state = demoReducer(state, { type: 'FOCUS_JOURNEY_STEP', caseId: 'in-ready-1' })
    expect(state.activePage).toBe('intake')
    expect(state.selectedReferralId).toBeNull()
  })

  it('SET_ACTIVE_PAGE clears any open referral workspace', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'SELECT_REFERRAL', id: JOURNEY_REFERRAL_ID })
    expect(state.selectedReferralId).toBe(JOURNEY_REFERRAL_ID)
    state = demoReducer(state, { type: 'SET_ACTIVE_PAGE', page: 'intake' })
    expect(state.activePage).toBe('intake')
    expect(state.selectedReferralId).toBeNull()
  })

  it('RESTART_JOURNEY returns the selected patient to their seeded stage', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'SELECT_JOURNEY_PATIENT', patientId: 'james-carter' })
    for (let i = 0; i < 7; i += 1) {
      state = demoReducer(state, { type: 'ADVANCE_JOURNEY' })
    }
    expect(
      buildPatientJourney(state.workflowScenarios, 'james-carter').complete,
    ).toBe(true)

    state = demoReducer(state, { type: 'RESTART_JOURNEY' })
    const journey = buildPatientJourney(state.workflowScenarios, 'james-carter')
    expect(journey.complete).toBe(false)
    expect(journey.current?.caseId).toBe('ho-dest-2')
    expect(state.activePage).toBe('handoff')
    expect(state.journeyFocusCaseId).toBe('ho-dest-2')
    expect(journey.completedCount).toBe(1)
  })

  it('resolving a journey case in the live queue jumps to the next stage tab', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'SELECT_JOURNEY_PATIENT', patientId: 'maria-alvarez' })
    expect(state.activePage).toBe('handoff')

    state = demoReducer(state, { type: 'RESOLVE_SCENARIO_CASE', id: 'ho-ack-1' })
    expect(state.activePage).toBe('assignment')
    expect(state.journeyFocusCaseId).toBe('ho-one-1')

    state = demoReducer(state, { type: 'RESOLVE_SCENARIO_CASE', id: 'ho-one-1' })
    expect(state.activePage).toBe('provider')
    expect(state.journeyFocusCaseId).toBe('sc-one-3')
  })
})

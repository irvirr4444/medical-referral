import { describe, expect, it } from 'vitest'
import { WORKFLOW_MODAL_TABS } from '../data/constants'
import { FLOW_OPS, isFlowOpsPage } from '../data/flowOps'
import {
  canonicalOpsPageId,
  COMBINED_ASSIGNMENT_STEP_IDS,
  fixtureStepId,
  isHandoffOperationStep,
  opsSourceStage,
  VISIBLE_STAGE_IDS,
} from '../features/automation/combinedAssignment'
import { ACTION_DEFS } from '../features/automation/confirmationTimers'
import { unreadCountForStage } from '../features/automation/unreadSteps'
import {
  detailForPatientStep,
  feedForStep,
  opsFixtureForStage,
  stepsForCombinedAssignment,
  stepsForPatient,
} from '../features/automation/ops'
import { HANDOFF_OPS_FIXTURE } from '../features/automation/ops/fixtures/handoff'
import { ASSIGNMENT_OPS_FIXTURE } from '../features/automation/ops/fixtures/assignment'
import {
  PATIENT_STEP_BREAKDOWNS,
  STAGE_STEP_IDS,
} from '../features/automation/ops/fixtures/patientSteps'
import {
  AUTOMATION_STAGES,
  automationStage,
  HANDOFF_STAGE,
} from '../features/automation/stages'
import { createInitialState, demoReducer } from '../state/demoReducer'

describe('combined Assignment & handoff', () => {
  it('exposes a six-stage visible workflow with no separate Handoff tab', () => {
    expect(VISIBLE_STAGE_IDS).toEqual([
      'intake',
      'assignment',
      'provider',
      'scheduling',
      'end-of-day',
      'weekly',
    ])
    expect(AUTOMATION_STAGES).toHaveLength(6)
    expect(AUTOMATION_STAGES.map((stage) => stage.id)).not.toContain('handoff')
    expect(WORKFLOW_MODAL_TABS.map((tab) => tab.id)).toEqual([
      'overview',
      'intake',
      'assignment',
      'provider',
      'scheduling',
      'end-of-day',
      'weekly',
    ])
    expect(WORKFLOW_MODAL_TABS.some((tab) => tab.id === 'assignment')).toBe(true)
    expect(
      WORKFLOW_MODAL_TABS.some(
        (tab) => /Handoff/i.test(tab.label) && !/Assignment/i.test(tab.label),
      ),
    ).toBe(false)
  })

  it('lists the four combined actions in order', () => {
    expect([...COMBINED_ASSIGNMENT_STEP_IDS]).toEqual([
      'assign-owner',
      'notify-referral-source',
      'create-monday-record',
      'create-update-drk',
    ])
    expect(automationStage('assignment').microsteps.map((step) => step.id)).toEqual([
      'assign-owner',
      'notify-referral-source',
      'create-monday-record',
      'create-update-drk',
    ])
    expect(automationStage('assignment').microsteps.map((step) => step.name)).toEqual([
      'Assign Case Manager',
      'Notify Case Manager',
      'Create Monday.com Record',
      'Prepare DRK Chart',
    ])
    expect(automationStage('assignment').purpose).toMatch(/case manager/i)
    expect(automationStage('assignment').trigger).toMatch(/Stage 1 is complete/i)
    expect(automationStage('assignment').successDefinition).toMatch(
      /DRK form is ready for final human review/i,
    )
    expect(automationStage('assignment').microsteps.at(-1)?.name).toBe(
      'Prepare DRK Chart',
    )
    expect(automationStage('assignment').microsteps.at(-1)?.description).toMatch(
      /does not press Create/i,
    )
  })

  it('resolves legacy handoff lookups without rewriting fixtures', () => {
    expect(isFlowOpsPage('handoff')).toBe(true)
    expect(canonicalOpsPageId('handoff')).toBe('assignment')
    expect(canonicalOpsPageId('assignment')).toBe('assignment')
    expect(automationStage('handoff')).toBe(HANDOFF_STAGE)
    expect(automationStage('handoff').id).toBe('handoff')
    expect(opsFixtureForStage('handoff')).toBe(HANDOFF_OPS_FIXTURE)
    expect(opsFixtureForStage('assignment')).toBe(ASSIGNMENT_OPS_FIXTURE)
    expect(STAGE_STEP_IDS.handoff).toEqual([
      'notify-referral-source',
      'create-monday-record',
      'create-update-drk',
    ])
    expect(STAGE_STEP_IDS.assignment).toEqual([
      'determine-owner',
      'assign-owner',
    ])
    expect(isHandoffOperationStep('notify-referral-source')).toBe(true)
    expect(isHandoffOperationStep('assign-owner')).toBe(false)
    expect(opsSourceStage('assignment', 'notify-referral-source')).toBe('handoff')
    expect(opsSourceStage('assignment', 'create-monday-record')).toBe('handoff')
    expect(opsSourceStage('assignment', 'assign-owner')).toBe('assignment')
    expect(opsSourceStage('assignment', 'determine-owner')).toBe('assignment')
    expect(fixtureStepId('assignment', 'assign-owner')).toBe('determine-owner')
    expect(fixtureStepId('assignment', 'notify-referral-source')).toBe(
      'notify-referral-source',
    )
  })

  it('renders existing Handoff fixture artifacts under the combined stage', () => {
    const notifyFromHandoff = detailForPatientStep(
      'handoff',
      'sardina-frank',
      'notify-referral-source',
    )
    const notifyFromCombined = detailForPatientStep(
      'assignment',
      'sardina-frank',
      'notify-referral-source',
    )
    expect(notifyFromHandoff.progress).toEqual(notifyFromCombined.progress)
    expect(notifyFromCombined.microstep?.id).toBe('notify-referral-source')
    expect(notifyFromCombined.microstep?.name).toBe('Notify Case Manager')
    expect(notifyFromCombined.microstep?.description).toBe(
      HANDOFF_STAGE.microsteps[0].description,
    )
    expect(notifyFromCombined.microstep?.example).toEqual(
      HANDOFF_STAGE.microsteps[0].example,
    )
    expect(notifyFromCombined.progress?.summary).toMatch(
      /Referral source notified and case manager CCd/i,
    )

    const fromHandoff = detailForPatientStep(
      'handoff',
      'sardina-frank',
      'create-update-drk',
    )
    const fromCombined = detailForPatientStep(
      'assignment',
      'sardina-frank',
      'create-update-drk',
    )
    expect(fromHandoff.progress).toEqual(fromCombined.progress)
    expect(fromCombined.example?.artifactSections?.length).toBeGreaterThan(0)
    expect(fromCombined.microstep?.name).toBe('Prepare DRK Chart')
    expect(PATIENT_STEP_BREAKDOWNS.handoff['sardina-frank']?.[2]?.summary).toMatch(
      /DRK chart created from approved intake data/i,
    )
    expect(HANDOFF_OPS_FIXTURE.events.some((event) => event.patientId === 'sardina-frank')).toBe(
      true,
    )
    expect(stepsForPatient('handoff', 'sardina-frank').map((row) => row.stepId)).toEqual(
      STAGE_STEP_IDS.handoff,
    )
    expect(
      stepsForCombinedAssignment('sardina-frank').map((row) => row.stepId),
    ).toEqual([
      'notify-referral-source',
      'create-monday-record',
      'create-update-drk',
    ])
    expect(
      feedForStep('assignment', 'notify-referral-source')
        .flatMap((day) => day.rows)
        .some((row) => row.patientId === 'sardina-frank'),
    ).toBe(true)
    expect(
      feedForStep('assignment', 'assign-owner')
        .flatMap((day) => day.rows)
        .some((row) => row.patientId === 'marcus-feldman'),
    ).toBe(true)
    expect(
      stepsForCombinedAssignment('marcus-feldman').map((row) => row.stepId),
    ).toContain('assign-owner')
    expect(
      stepsForCombinedAssignment('marcus-feldman').find(
        (row) => row.stepId === 'assign-owner',
      )?.summary,
    ).toMatch(/AI suggests Cole Winfield · Gardena territory/i)
  })

  it('keeps the case-manager confirmation gate on Assign Case Manager', () => {
    expect(ACTION_DEFS['confirm-assignment']).toEqual(
      expect.objectContaining({
        stageId: 'assignment',
        stepId: 'assign-owner',
        label: 'Confirm case manager',
      }),
    )
    expect(automationStage('assignment').microsteps[0].id).toBe('assign-owner')
    expect(automationStage('assignment').microsteps[0].example.validation).toMatch(
      /not auto-assigned/i,
    )

    let state = createInitialState()
    state = demoReducer(state, {
      type: 'CONFIRM_ASSIGNMENT_HANDOFF',
      patientId: 'marcus-feldman',
      patientName: 'Marcus Feldman',
      occurredAt: 'August 18, 2026 at 10:00 AM',
    })
    expect(state.latestAssignmentHandoff?.patientId).toBe('marcus-feldman')
    expect(state.handoffNotifyUnread).toBe(true)
    expect(unreadCountForStage(state, 'handoff')).toBe(
      unreadCountForStage(state, 'assignment'),
    )
    expect(unreadCountForStage(state, 'assignment')).toBeGreaterThan(0)
    expect(state.actionTimers['marcus-feldman:confirm-assignment']?.status).toBe(
      'resolved',
    )
  })

  it('renumbers later visible stages 3 through 6 without renaming internal IDs', () => {
    expect(FLOW_OPS.provider.title).toBe('3. Provider selection')
    expect(FLOW_OPS.scheduling.title).toBe('4. Scheduling')
    expect(FLOW_OPS['end-of-day'].title).toBe('5. End-of-day check')
    expect(FLOW_OPS.weekly.title).toBe('6. Weekly visit cycle')
    expect(automationStage('provider').id).toBe('provider')
    expect(automationStage('scheduling').id).toBe('scheduling')
    expect(automationStage('end-of-day').id).toBe('end-of-day')
    expect(automationStage('weekly').id).toBe('weekly')
    expect(WORKFLOW_MODAL_TABS.find((tab) => tab.id === 'provider')?.label).toBe(
      '3. Provider selection',
    )
    expect(WORKFLOW_MODAL_TABS.find((tab) => tab.id === 'weekly')?.label).toBe(
      '6. Weekly visit cycle',
    )
  })

  it('does not replace existing demo fixture patients or values', () => {
    expect(ASSIGNMENT_OPS_FIXTURE.events[0]).toEqual(
      expect.objectContaining({
        patientId: 'marcus-feldman',
        patientName: 'Marcus Feldman',
        summary: 'Intake approved · ready to assign case manager',
      }),
    )
    expect(HANDOFF_OPS_FIXTURE.stageId).toBe('handoff')
    expect(HANDOFF_OPS_FIXTURE.events[0]?.eventType).toBe('plans-loaded')
    expect(PATIENT_STEP_BREAKDOWNS.assignment['marcus-feldman']?.[0]).toEqual(
      expect.objectContaining({
        stepId: 'determine-owner',
        status: 'waiting',
        summary: 'AI suggests Cole Winfield · Gardena territory',
      }),
    )
    expect(Object.keys(PATIENT_STEP_BREAKDOWNS.handoff)).toEqual(
      expect.arrayContaining(['sardina-frank', 'gonzalez-eric']),
    )
    expect(Object.keys(PATIENT_STEP_BREAKDOWNS.handoff)).not.toContain(
      'butler-alva',
    )
  })
})

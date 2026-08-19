import { describe, expect, it } from 'vitest'
import { mergeWorkflowFeed } from '../features/automation/liveWorkflow/feed'
import type {
  LiveAssignment,
  LiveHandoff,
} from '../features/automation/liveWorkflow/types'

const assignment: LiveAssignment = {
  work_item_id: 'work-1',
  case_id: 'case-1',
  patient_label: 'Synthetic Patient',
  status: 'waiting',
  owner_role: 'case_manager',
  recommended_assignee: null,
  recommendation_reason: 'Territory rules unavailable',
  assigned_to: null,
  assigned_case_manager: null,
  payload: {},
  updated_at: '2026-08-13T14:30:00Z',
}

describe('live workflow feed', () => {
  it('shows a durable assignment without inventing a recommendation', () => {
    const days = mergeWorkflowFeed({
      demoDays: [],
      assignments: [assignment],
      handoffs: [],
      stageId: 'assignment',
      selectedStepId: 'assign-owner',
      patientQuery: '',
      statuses: ['waiting'],
    })

    expect(days[0].rows[0]).toEqual(
      expect.objectContaining({
        patientId: 'case-1',
        patientName: 'Synthetic Patient',
        summary: 'Case Manager needs to be confirmed',
        status: 'waiting',
      }),
    )
  })

  it('projects each ready handoff operation into its matching step', () => {
    const handoff: LiveHandoff = {
      case_id: 'case-1',
      patient_label: 'Synthetic Patient',
      status: 'awaiting_handoff',
      assigned_case_manager: {
        name: 'Case Manager',
        email: 'manager@example.test',
      },
      operations: [
        {
          operation_id: 'operation-1',
          operation_type: 'create-monday-record',
          status: 'ready',
          updated_at: '2026-08-13T14:31:00Z',
          request_payload: {},
        },
      ],
    }
    const days = mergeWorkflowFeed({
      demoDays: [],
      assignments: [],
      handoffs: [handoff],
      stageId: 'assignment',
      selectedStepId: 'create-monday-record',
      patientQuery: '',
      statuses: ['waiting'],
    })

    expect(days[0].rows[0]).toEqual(
      expect.objectContaining({
        summary: 'Monday.com record ready to create',
        status: 'waiting',
      }),
    )
  })

  it('keeps completed assignments visible on assign-owner and accepts the legacy handoff page id', () => {
    const completed: LiveAssignment = {
      ...assignment,
      status: 'completed',
      assigned_case_manager: {
        name: 'Cole Ramirez',
        email: 'cole@example.test',
      },
    }
    const waitingDays = mergeWorkflowFeed({
      demoDays: [],
      assignments: [completed],
      handoffs: [],
      stageId: 'assignment',
      selectedStepId: 'assign-owner',
      patientQuery: '',
      statuses: ['done'],
    })
    expect(waitingDays[0].rows[0]).toEqual(
      expect.objectContaining({
        status: 'done',
        summary: 'Cole Ramirez confirmed as Case Manager',
      }),
    )

    const handoff: LiveHandoff = {
      case_id: 'case-1',
      patient_label: 'Synthetic Patient',
      status: 'awaiting_handoff',
      assigned_case_manager: {
        name: 'Case Manager',
        email: 'manager@example.test',
      },
      operations: [
        {
          operation_id: 'operation-1',
          operation_type: 'notify-assigned-case-manager',
          status: 'ready',
          updated_at: '2026-08-13T14:31:00Z',
          request_payload: {},
        },
      ],
    }
    const legacyDays = mergeWorkflowFeed({
      demoDays: [],
      assignments: [],
      handoffs: [handoff],
      stageId: 'handoff',
      selectedStepId: 'notify-referral-source',
      patientQuery: '',
      statuses: ['waiting'],
    })
    expect(legacyDays[0].rows[0]).toEqual(
      expect.objectContaining({
        summary: 'Notify assigned case manager',
        status: 'waiting',
      }),
    )
  })
})

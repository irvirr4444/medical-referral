import type { FlowOpsPageId } from '../../../data/flowOps'
import type { StageOpsRecipe } from './types'

export const STAGE_OPS_RECIPES: Record<FlowOpsPageId, StageOpsRecipe> = {
  intake: {
    stageId: 'intake',
    sections: [
      { id: 'emails-arrived', label: 'Emails arrived', openByDefault: false },
      { id: 'extracted', label: 'Extractions', openByDefault: false },
      { id: 'needs-information', label: 'Needs information', openByDefault: true, isException: true },
      { id: 'duplicate-risk', label: 'Duplicate risk', openByDefault: true, isException: true },
      { id: 'awaiting-approval', label: 'Awaiting approval', openByDefault: true },
      { id: 'approved-rejected', label: 'Approved / rejected', openByDefault: false },
      { id: 'destination-gated', label: 'Destination authorized / blocked', openByDefault: true, isException: true },
    ],
  },
  handoff: {
    stageId: 'handoff',
    sections: [
      { id: 'plans-loaded', label: 'Approved plans loaded', openByDefault: false },
      { id: 'monday-created', label: 'Monday items created', openByDefault: false },
      { id: 'agency-unresolved', label: 'Agency unresolved', openByDefault: true, isException: true },
      { id: 'drk-prepared', label: 'DRK prepared / entered', openByDefault: true },
      { id: 'destinations-linked', label: 'Destinations linked', openByDefault: false },
      { id: 'handoff-verified', label: 'Handoff verified / partial failure', openByDefault: true, isException: true },
    ],
  },
  assignment: {
    stageId: 'assignment',
    sections: [
      { id: 'ready-assignment', label: 'Ready for assignment', openByDefault: true },
      { id: 'territory-matched', label: 'Territory matched', openByDefault: false },
      { id: 'needs-owner-confirm', label: 'Needs owner confirmation', openByDefault: true, isException: true },
      { id: 'assignment-confirmed', label: 'Assignment confirmed', openByDefault: false },
      { id: 'assignment-written', label: 'Assignment written', openByDefault: false },
    ],
  },
  provider: {
    stageId: 'provider',
    sections: [
      { id: 'needs-provider', label: 'Needs provider', openByDefault: true },
      { id: 'shortlist-ready', label: 'Provider shortlist ready', openByDefault: false },
      { id: 'needs-provider-confirm', label: 'Needs confirmation', openByDefault: true, isException: true },
      { id: 'provider-confirmed', label: 'Provider confirmed', openByDefault: false },
      { id: 'provider-written', label: 'Provider written', openByDefault: false },
    ],
  },
  scheduling: {
    stageId: 'scheduling',
    sections: [
      { id: 'ready-schedule', label: 'Ready to schedule', openByDefault: true },
      { id: 'windows-proposed', label: 'Windows proposed', openByDefault: false },
      { id: 'awaiting-response', label: 'Awaiting response', openByDefault: true },
      { id: 'appointment-confirmed', label: 'Appointment confirmed', openByDefault: false },
      { id: 'scheduling-exception', label: 'Scheduling exception', openByDefault: true, isException: true },
      { id: 'appointment-written', label: 'Appointment written', openByDefault: false },
    ],
  },
  'end-of-day': {
    stageId: 'end-of-day',
    sections: [
      { id: 'due-reviewed', label: 'Due patients reviewed', openByDefault: false },
      { id: 'scheduled-consistent', label: 'Scheduled & consistent', openByDefault: false },
      { id: 'inconsistencies', label: 'Scheduling inconsistencies', openByDefault: true, isException: true },
      { id: 'exceptions-opened', label: 'Exceptions opened', openByDefault: true, isException: true },
      { id: 'management-notified', label: 'Management notified', openByDefault: false },
    ],
  },
  weekly: {
    stageId: 'weekly',
    sections: [
      { id: 'patients-checked', label: 'Active patients checked', openByDefault: false },
      { id: 'visit-seen', label: 'Seen / visit recorded', openByDefault: false },
      { id: 'not-seen', label: 'Not seen incremented', openByDefault: true },
      { id: 'on-hold', label: 'On hold / hospitalization', openByDefault: true, isException: true },
      { id: 'review-required', label: 'Review required', openByDefault: true, isException: true },
      { id: 'weekly-exceptions', label: 'Exceptions opened', openByDefault: true, isException: true },
    ],
  },
}

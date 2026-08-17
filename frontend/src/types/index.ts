export type WorkflowStage =
  | 'received'
  | 'extracted'
  | 'reviewed'
  | 'confirmed'
  | 'monday_ready'
  | 'drk_ready'

export type FieldStatus = 'complete' | 'explicitly_none' | 'missing' | 'unclear'

export type DuplicateStatus = 'clear' | 'probable_duplicate' | 'resolved_different'

export type ReferralOutcome =
  | 'ready'
  | 'needs_information'
  | 'needs_clarification'
  | 'blocked_duplicate'

export type QueueFilter =
  | 'all'
  | 'ready'
  | 'needs_information'
  | 'possible_duplicate'
  | 'confirmed'

export type AutomationStep =
  | 'idle'
  | 'connecting'
  | 'discovering'
  | 'validating'
  | 'deduping_attachments'
  | 'reading'
  | 'verifying'
  | 'evaluating'
  | 'duplicate_search'
  | 'monday_prep'
  | 'drk_prep'
  | 'review_summaries'
  | 'complete'

export type MondayWriteStatus = 'not_ready' | 'ready' | 'creating' | 'created'
export type DrkStatus = 'not_ready' | 'draft_ready' | 'assisted_entry' | 'face_sheet_ready'

export interface RequiredField {
  key: string
  label: string
  value: string
  status: FieldStatus
  evidencePage: number
  evidenceQuote: string
  confidence: number
}

export interface AuditEvent {
  id: string
  timestamp: string
  label: string
  result: string
  actor: string
  humanRequired: boolean
}

export interface DuplicateCandidate {
  name: string
  dateOfBirth: string
  phone: string
  address: string
  mondayItemId: string
  matchNotes: string[]
}

export interface MondayPreview {
  itemName: string
  board: string
  group: string
  columns: Array<{ label: string; value: string }>
  updateComment: string
  agencyRelation: string
  blockers: string[]
  itemId?: string
  demoUrl?: string
}

export interface DrkDraft {
  demographics: Array<{ label: string; value: string }>
  contact: Array<{ label: string; value: string }>
  address: Array<{ label: string; value: string }>
  emergencyContact: Array<{ label: string; value: string }>
  admission: Array<{ label: string; value: string }>
  insurance: Array<{ label: string; value: string }>
  diagnoses: string[]
  requestedService: string
  unresolvedLookups: string[]
  duplicateCheck: string
}

export interface ImpactReceipt {
  pagesAnalyzed: number
  valuesExtracted: number
  requiredFieldsVerified: number
  duplicateSearches: number
  destinationRecordsPrepared: number
  manualActionsAvoided: number
  minutesReturned: number
}

export interface ReferralRecord {
  id: string
  patientName: string
  receivedAt: string
  sender: string
  subject: string
  referralSource: string
  pdfFilename: string
  /** Allowlisted samples/ file name served via /referrals/ */
  samplePdf: string
  pageCount: number
  dateOfBirth: string
  phone: string
  address: string
  homeHealthOrHospice: string
  diagnosis: string
  insurance: string
  requestedService: string
  referringProvider: string
  medications: string[]
  allergies: string[]
  clinicalSummary: string
  requiredFields: RequiredField[]
  completenessScore: string
  duplicateStatus: DuplicateStatus
  outcome: ReferralOutcome
  minutesReturned: number
  demoPurpose: string
  nextAction?: string
  duplicateCandidate?: DuplicateCandidate
  mondayPreview: MondayPreview
  drkDraft: DrkDraft
  impactReceipt: ImpactReceipt
  stage: WorkflowStage
  confirmed: boolean
  followUpPrepared: boolean
  followUpMessage?: string
  followUpOwner?: string
  mondayStatus: MondayWriteStatus
  drkStatus: DrkStatus
  timeline: AuditEvent[]
  processed: boolean
  /** True for the waiting inbox batch that Process inbox advances. */
  inboxBatch?: boolean
}

export interface ActivityEvent {
  id: string
  time: string
  text: string
  stage?: import('../data/flowOps').FlowOpsPageId | 'overview'
}

export interface BatchMetrics {
  emailsReceived: number
  pdfsProcessed: number
  pagesAnalyzed: number
  valuesExtracted: number
  requiredFieldsEvaluated: number
  duplicateSearches: number
  mondayPreviewsGenerated: number
  drkDraftsGenerated: number
  destinationReady: number
  incompleteOrUnclear: number
  probableDuplicatesBlocked: number
  readyForConfirmation: number
  manualActionsAvoided: number
  timeReturnedMinutes: number
}

export interface ImpactAssumptions {
  referralsPerDay: number
  manualMinutes: number
  assistedMinutes: number
  workingDaysPerYear: number
  annualProductiveHours: number
}

export interface ImpactProjection {
  minutesReturnedPerReferral: number
  hoursPerDay: number
  hoursPerWeek: number
  hoursPerYear: number
  addedReferralCapacity: number
  fteEquivalent: number
  reductionPercent: number
}

export type ProviderAvailabilityOutcome =
  | 'waiting'
  | 'confirmed'
  | 'timeout'
  | 'placement_completed'

export type ProviderTerritoryResolution = 'assigned' | 'discharged'

export type SchedulingHandoffRoute = 'provider_confirmed' | 'manual_placement'

export type ConfirmationActionId =
  | 'confirm-intake-review'
  | 'confirm-partner-contacted'
  | 'confirm-assignment'
  | 'confirm-provider'
  | 'use-fallback-provider'
  | 'provider-availability'
  | 'manual-placement'
  | 'schedule-patient'
  | 'eod-follow-up-cm'
  | 'eod-escalate'
  | 'weekly-mark-not-seen'
  | 'weekly-escalate-dc'
  | 'weekly-confirm-rescheduled'
  | 'weekly-qa-discharge'
  | 'weekly-remove-dc'
  | 'weekly-move-holds'

export type ActionTimerStatus = 'pending' | 'warning' | 'overdue' | 'resolved'

export interface ActionTimer {
  id: string
  patientId: string
  patientName: string
  stageId: import('../data/flowOps').FlowOpsPageId
  stepId: string
  actionId: ConfirmationActionId
  eligibleAt: number
  deadlineAt: number
  status: ActionTimerStatus
  resolvedAt?: number
}

export interface ProviderAvailabilityRequest {
  requestedAt: string
  deadlineAt: string
  outcome: ProviderAvailabilityOutcome
  resolvedAt?: string
}

export interface SchedulingHandoffProvider {
  id: string
  name: string
  npi?: string
  city?: string
  phone?: string
  email?: string
}

export interface SchedulingHandoff {
  patientId: string
  patientName: string
  provider: SchedulingHandoffProvider
  route: SchedulingHandoffRoute
  requestedAt: string
  deadlineAt: string
  readyAt: string
  samplePdf: string
}

export type SchedulingSlotStatus = 'open' | 'unavailable'
export type SchedulingAppointmentStatus = 'waiting' | 'scheduled' | 'blocked'
export type SchedulingBlockerReason =
  | 'patient_declined'
  | 'patient_unavailable'
  | 'slots_exhausted'

export interface SchedulingSlot {
  id: string
  dateLabel: string
  timeLabel: string
  appointmentDate: string
  appointmentTime: string
  status: SchedulingSlotStatus
  unavailableReason?: string
}

export interface PatientSchedulingRecord {
  patientId: string
  patientName: string
  provider: SchedulingHandoffProvider
  route: SchedulingHandoffRoute
  syncedAt: string
  slots: SchedulingSlot[]
  selectedSlotId: string | null
  status: SchedulingAppointmentStatus
  appointmentDate?: string
  appointmentTime?: string
  scheduledAt?: string
  blockerReason?: SchedulingBlockerReason
  referralSent: boolean
}

export interface DemoState {
  referrals: ReferralRecord[]
  automationStep: AutomationStep
  automationRunning: boolean
  automationComplete: boolean
  selectedReferralId: string | null
  queueFilter: QueueFilter
  spineFilter: WorkflowStage | 'all'
  batchMetrics: BatchMetrics
  impactAssumptions: ImpactAssumptions
  completionMessage: string | null
  howCalculatedOpen: boolean
  activePage: string
  lastInboxSyncLabel: string
  activityFeed: ActivityEvent[]
  lifecycleStageId: import('../data/lifecycle').LifecycleStageId
  lifecycleCases: import('../data/lifecycle').LifecycleCase[]
  lifecycleRunning: boolean
  lifecycleMessage: string | null
  lifecycleMinutesReturned: number
  workflowScenarios: import('../data/scenarioTypes').WorkflowScenario[]
  scenarioFilter: import('../data/scenarioTypes').ScenarioBucket | 'all'
  scenarioMinutesReturned: number
  /** Case highlighted by the patient journey spine. */
  journeyFocusCaseId: string | null
  /** Active patient on the journey spine roster. */
  selectedJourneyPatientId: string
  /** Worklist scoped to one patient across stage tabs. */
  opsScopedPatient: { patientId: string; patientName: string } | null
  /** Selected microstep per stage — keeps nav overdue counts in sync with the open step. */
  opsSelectedStepByStage: Partial<Record<string, string>>
  providerSelectedIds: Record<string, string>
  providerConfirmed: Record<string, boolean>
  providerTerritoryResolutions: Record<string, ProviderTerritoryResolution>
  providerAvailability: Record<string, ProviderAvailabilityRequest>
  latestProviderAvailabilityPatientId: string | null
  schedulingHandoffs: SchedulingHandoff[]
  patientSchedules: Record<string, PatientSchedulingRecord>
  providerRecordsUnread: boolean
  providerRecordsMessageUnread: boolean
  schedulingHandoffUnread: boolean
  schedulingHandoffMessageUnread: boolean
  latestAssignmentHandoff: {
    patientId: string
    patientName: string
    occurredAt: string
  } | null
  assignmentNotifyUnread: boolean
  handoffNavUnread: boolean
  handoffNotifyUnread: boolean
  handoffMondayUnread: boolean
  handoffDrkUnread: boolean
  providerNavUnread: boolean
  providerSelectUnread: boolean
  providerAvailabilityUnread: boolean
  eodFollowUpUnread: boolean
  eodEscalationUnread: boolean
  latestEodFollowUpPatientId: string | null
  latestEodEscalationPatientId: string | null
  intakeFieldEdits: Record<string, Record<string, string>>
  intakeSectionRows: Record<
    string,
    Record<
      string,
      Array<{
        label: string
        value: string
        fieldPath?: string
        rowId?: string
        meta?: string
      }>
    >
  >
  intakeVerified: Record<string, boolean>
  latestIntakeReview: {
    patientId: string
    patientName: string
    occurredAt: string
  } | null
  intakeMondayUnread: boolean
  intakeDrkUnread: boolean
  intakePartnerUnread: boolean
  latestPartnerContact: {
    patientId: string
    patientName: string
    occurredAt: string
  } | null
  assignmentOwnerUnread: boolean
  actionTimers: Record<string, ActionTimer>
}

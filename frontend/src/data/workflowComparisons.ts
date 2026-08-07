export interface WorkflowComparison {
  id: string
  title: string
  planned: boolean
  before: string[]
  after: string[]
  value: string
}

export const WORKFLOW_COMPARISONS: WorkflowComparison[] = [
  {
    id: 'intake',
    title: 'Referral intake',
    planned: false,
    before: [
      'Open the referral email.',
      'Download and validate the PDF.',
      'Read every page.',
      'Locate the patient name, DOB, phone, and address.',
      'Locate home-health/hospice, wound, clinical, and insurance information.',
      'Determine which required information is missing or unclear.',
      'Search Monday.com for an existing patient.',
      'Search DRK for an existing patient.',
      'Contact the referral partner.',
      'Re-enter information into Monday.com.',
      'Re-enter information into DRK.',
      'Track whether intake was completed and follow up again when needed.',
    ],
    after: [
      'Review extracted information.',
      'Review highlighted missing or uncertain fields.',
      'Resolve possible duplicate warnings.',
      'Confirm the referral.',
      'Monday.com and DRK records are prepared.',
    ],
    value:
      'Employees stop searching every document for routine information. Their attention is directed to referrals and fields that require judgment.',
  },
  {
    id: 'handoff',
    title: 'Handoff',
    planned: false,
    before: [
      'Prepare an acknowledgement email.',
      'Attach and forward the PDF.',
      'Send the referral to the case manager.',
      'Forward the referral to the face-sheet team.',
      'Enter information into the Monday.com Master Sheet.',
      'Fill the Sent By field.',
      'Track whether each handoff occurred.',
    ],
    after: [
      'An acknowledgement is prepared automatically.',
      'The Monday.com handoff is prepared.',
      'The DRK draft is prepared.',
      'Handoff destinations and events are recorded.',
      'Employees review exceptions and confirm.',
    ],
    value:
      'One confirmed referral creates a coordinated handoff instead of several disconnected manual tasks.',
  },
  {
    id: 'assignment',
    title: 'Assignment',
    planned: false,
    before: [
      "Determine the patient's geographic area.",
      'Search for the correct case manager.',
      'Compare territory coverage manually.',
      'Choose among one, none, or multiple matches.',
      'Notify the information-box manager when coverage is missing.',
      'Record the assignment by hand.',
    ],
    after: [
      'Patient location is read from the referral.',
      'Approved territory rules suggest the matching case manager.',
      'Zero-match and multi-match cases are flagged for human review.',
      'Employees confirm or override the suggestion.',
    ],
    value:
      'Territory matching becomes a confirmation step instead of a search exercise.',
  },
  {
    id: 'provider',
    title: 'Provider selection',
    planned: true,
    before: [
      "Review the patient's location.",
      "Search the case manager's provider list.",
      'Determine which provider covers the territory.',
      'Compare nearby providers when coverage is unclear.',
      'Escalate when no company provider covers the area.',
      'Track whether a selected provider has been contacted.',
    ],
    after: [
      'Matching providers are suggested from territory rules.',
      'Ambiguous and no-coverage cases are highlighted for review.',
      'Selected-but-not-contacted status stays human-controlled.',
      'Case managers confirm the provider before send.',
    ],
    value:
      'Automation shortlists providers. Case managers retain the final selection and send decision.',
  },
  {
    id: 'scheduling',
    title: 'Scheduling',
    planned: true,
    before: [
      'Open routing software.',
      "Inspect the provider's schedule.",
      'Contact the provider.',
      'Wait for a response.',
      'Track the one-hour response window.',
      'Decide where the patient fits if the provider does not respond.',
      'Update Monday.com and DRK.',
      'Continue checking until scheduling is complete.',
    ],
    after: [
      'Relevant routing windows are displayed.',
      'Provider-response deadlines are monitored.',
      'Unanswered referrals are highlighted.',
      'Confirmed scheduling information is prepared for Monday.com and DRK.',
      'Human staff select and confirm the final appointment.',
    ],
    value:
      'Automation monitors windows and deadlines. Case managers retain scheduling acceptance.',
  },
  {
    id: 'end-of-day',
    title: 'End-of-day scheduling check',
    planned: true,
    before: [
      'Open Monday.com and review every active referral.',
      'Check scheduled status, appointment date, and scheduling-complete status.',
      'Identify blank or overdue referrals.',
      'Contact case managers through Teams.',
      'Ask why each patient is not scheduled.',
      'Determine whether the issue is resolvable.',
      'Prepare management escalation emails.',
      'Maintain a separate tracking spreadsheet.',
      'Continue following up.',
    ],
    after: [
      'Active referrals are checked automatically.',
      'Unscheduled referrals are identified.',
      'The responsible case manager and known blocker are displayed.',
      'Existing Monday.com notifications are verified.',
      'Uncovered exceptions are prepared for escalation.',
      'Management reviews one organized exception list.',
    ],
    value: 'Management reviews exceptions instead of manually auditing every referral.',
  },
  {
    id: 'weekly',
    title: 'Weekly visit cycle',
    planned: true,
    before: [
      'Review the weekly schedule.',
      'Open DRK progress notes.',
      'Determine whether each patient was seen.',
      'Update visit status in Monday.com.',
      'Reschedule patients who were not seen.',
      'Count consecutive missed visits.',
      'Identify patients not seen for three weeks.',
      'Prepare noncompliance discharge-review requests.',
      'Monitor healed and expired statuses.',
      'Notify QA and management.',
      'Maintain hold lists.',
      'Remove held patients from active scheduling.',
      'Check whether held patients are ready to return.',
      'Return eligible patients to the weekly cycle.',
    ],
    after: [
      'Recorded visit statuses are monitored.',
      'Seen and not-seen outcomes are organized.',
      'Consecutive missed visits are counted.',
      'Three-week noncompliance creates a discharge-review request.',
      'Healed or expired statuses initiate the appropriate human review.',
      'Hold patients are removed from active scheduling.',
      'Return-ready patients re-enter the weekly cycle.',
      'Human staff retain all clinical and discharge decisions.',
    ],
    value:
      'The automation remembers deadlines, counts repeated events, and prepares follow-up work so employees do not have to maintain parallel tracking systems.',
  },
]

export const INTAKE_BEFORE_SHORT = [
  'Open email',
  'Download PDF',
  'Read every page',
  'Locate patient information',
  'Check required fields',
  'Search for duplicates',
  'Re-enter information into Monday.com',
  'Re-enter information into DRK',
  'Follow up on missing details',
  'Track completion',
]

export const INTAKE_AFTER_SHORT = [
  'Review extracted information',
  'Resolve exceptions',
  'Confirm',
  'Monday.com and DRK records are prepared',
]

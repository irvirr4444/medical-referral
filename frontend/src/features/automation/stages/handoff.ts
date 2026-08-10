import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const HANDOFF_STAGE: AutomationStageDefinition = {
  id: 'handoff',
  title: '2. Handoff',
  shortTitle: 'Handoff',
  purpose:
    'Acknowledge the referral source, send the referral to the assigned case manager and face-sheet team, and record the handoff in Monday.com and DRK.',
  trigger:
    'The guarded intake approval gate authorizes downstream preparation.',
  successDefinition:
    'Monday and DRK actions are prepared or applied once, linked, verified, and audited.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'load-approved-plan',
      name: 'Load the approved intake plan',
      description:
        'Read the immutable approved referral version and its authorization record.',
      system: 'Workflow database',
      next: 'Map Monday fields',
      input: 'Approved referral run and execution token',
      output: 'Locked destination plan',
      validation:
        'The plan version must match the version reviewed by the human approver.',
    }),
    step({
      id: 'map-monday-fields',
      name: 'Map the Monday.com fields',
      description:
        'Translate canonical referral values into explicit Master Sheet column values.',
      system: 'Monday mapper',
      next: 'Resolve agency relation',
      input: 'Canonical referral JSON',
      output:
        'Patient name, DOB, phone, receipt date, agency details, and structured update text',
      validation: 'Only configured WCW column IDs may be written.',
    }),
    step({
      id: 'resolve-agency',
      name: 'Resolve the referring agency',
      description:
        'Find one exact Accounts-board agency match before creating a relation.',
      system: 'Monday agency lookup',
      next: 'Create the Master Sheet item',
      input: 'Referring facility and agency phone',
      output: 'One exact agency relation candidate',
      validation:
        'Zero or multiple matches remain unresolved for human review.',
      exception: {
        input: 'Agency name with two possible Accounts matches',
        output: 'Agency relation withheld; two candidates reported',
        validation: 'The writer does not guess a relation.',
      },
    }),
    step({
      id: 'write-monday',
      name: 'Create the Monday.com item',
      description: 'Apply the approved payload with an idempotency key.',
      system: 'Monday writer',
      next: 'Prepare the DRK action',
      input: 'Approved Master Sheet payload',
      output: 'Created item ID and applied column receipt',
      validation:
        'A repeated request returns the existing result instead of creating another item.',
    }),
    step({
      id: 'prepare-drk',
      name: 'Prepare the DRK chart action',
      description:
        'Map demographics, contact, insurance, diagnosis, and referral details to DRK fields.',
      system: 'DRK mapper',
      next: 'Perform assisted DRK entry',
      input: 'Canonical referral and duplicate-clear result',
      output: 'DRK field/action draft with unresolved lookups',
      validation:
        'Create Patient remains blocked if identity or duplicate checks are unresolved.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'apply-drk',
      name: 'Perform assisted DRK entry',
      description:
        'Use the approved DRK action in the authenticated EMR session.',
      system: 'DRK browser automation',
      next: 'Link destination identifiers',
      input: 'Approved DRK action draft',
      output: 'Proposed chart identifiers and action receipt',
      validation:
        'Production selectors and final write behavior still require WCW validation.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'link-destinations',
      name: 'Link destination identifiers',
      description:
        'Store the Monday item, DRK chart, and internal referral relationship.',
      system: 'Workflow database',
      next: 'Reconcile destination state',
      input: 'Monday item ID and DRK chart result',
      output: 'One patient/referral link record',
      validation:
        'Identifiers are unique and tied to the approved referral version.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'reconcile-handoff',
      name: 'Verify and audit the handoff',
      description:
        'Read back destination state and record success, pending work, or a partial failure.',
      system: 'Reconciliation worker',
      next: 'Begin Assignment',
      input: 'Destination receipts and linked identifiers',
      output: 'Verified handoff event or targeted retry',
      validation:
        'Successful operations are never repeated when another destination fails.',
      implementationStatus: 'partial',
    }),
  ],
}

import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const HANDOFF_STAGE: AutomationStageDefinition = {
  id: 'handoff',
  title: '2. Handoff',
  shortTitle: 'Handoff',
  purpose:
    'Acknowledge the referral source, route the approved referral to the case manager and face-sheet team, and record it in Monday.com and DRK.',
  trigger:
    'The guarded intake approval gate authorizes downstream preparation.',
  successDefinition:
    'Monday and DRK actions are prepared or applied once, linked, verified, and audited.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'load-approved-plan',
      name: 'Load the confirmed referral',
      description:
        'Read the exact referral version and human approval that authorized the handoff.',
      system: 'Workflow database',
      next: 'Acknowledge the referral source',
      input: 'Approved referral run and execution token',
      output: 'Locked destination plan',
      validation:
        'The plan version must match the version reviewed by the human approver.',
    }),
    step({
      id: 'map-monday-fields',
      name: 'Acknowledge the referral source',
      description:
        'Send a receipt confirmation to the referral partner and copy the assigned case manager.',
      system: 'Outlook delivery',
      next: 'Route the referral internally',
      input: 'Referral source contact and approved summary',
      output: 'Acknowledgment email with delivery receipt',
      validation: 'The message references the correct patient and referral source.',
    }),
    step({
      id: 'resolve-agency',
      name: 'Route the referral internally',
      description:
        'Send the confirmed referral to the assigned case manager and face-sheet team.',
      system: 'Workflow routing',
      next: 'Create the Monday.com record',
      input: 'Approved referral, assignment context, and agency lookup',
      output: 'Internal routing receipt and resolved agency relation',
      validation:
        'Ambiguous agency or owner matches remain visible for human review.',
      exception: {
        input: 'Agency name with two possible Accounts matches',
        output: 'Agency relation withheld; two candidates reported',
        validation: 'The writer does not guess a relation.',
      },
    }),
    step({
      id: 'write-monday',
      name: 'Create the Monday.com record',
      description:
        'Map the approved referral into explicit Master Sheet columns and create the item once.',
      system: 'Monday writer',
      next: 'Prepare the DRK action',
      input: 'Approved Master Sheet payload',
      output: 'Created item ID and applied column receipt',
      validation:
        'A repeated request returns the existing result instead of creating another item.',
    }),
    step({
      id: 'prepare-drk',
      name: 'Prepare the DRK patient record',
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
      name: 'Create or update the DRK chart',
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
      name: 'Link the Monday.com and DRK records',
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
      name: 'Verify the completed handoff',
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

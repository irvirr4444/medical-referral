import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const INTAKE_STAGE: AutomationStageDefinition = {
  id: 'intake',
  title: '1. Referral intake',
  shortTitle: 'Referral intake',
  purpose:
    'Verify every inbound referral PDF, capture the required patient information, and route missing or uncertain data for human follow-up.',
  trigger:
    'A new Outlook message reaches the monitored inbox with at least one PDF attachment.',
  successDefinition:
    'The referral is fingerprinted, extracted, checked for missing fields and duplicates, and held behind human approval.',
  implementationStatus: 'working',
  microsteps: [
    step({
      id: 'discover-email',
      name: 'Discover the referral email',
      description:
        'Poll the monitored Outlook inbox and identify messages that may contain referrals.',
      system: 'Microsoft Graph / Outlook',
      next: 'Inspect attachments',
      input: 'Unread message: New wound care referral',
      output: 'Message and attachment metadata normalized for intake',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
    }),
    step({
      id: 'validate-pdf',
      name: 'Validate PDF attachments',
      description:
        'Accept only attachments whose name and binary signature identify a real PDF.',
      system: 'Outlook adapter',
      next: 'Fingerprint the attachment',
      input: 'synthetic-complete-referral.pdf, application/pdf',
      output: 'One accepted PDF attachment',
      validation:
        'Filename ends in .pdf and content starts with the PDF file signature.',
      exception: {
        input: 'synthetic-incomplete-referral.pdf, application/pdf',
        output: 'One accepted PDF attachment',
        validation:
          'The file is valid even though its clinical content is incomplete.',
      },
    }),
    step({
      id: 'fingerprint-attachment',
      name: 'Prevent duplicate processing',
      description:
        'Hash the attachment and check whether the same document already completed intake.',
      system: 'Pipeline state database',
      next: 'Read the PDF',
      input: 'Validated PDF bytes',
      output: 'SHA-256 fingerprint with status: not previously completed',
      validation:
        'A completed fingerprint is skipped; failed work may be retried safely.',
    }),
    step({
      id: 'extract-referral',
      name: 'Extract referral information',
      description:
        'Send the PDF through the canonical Anthropic Files API extractor.',
      system: 'Canonical PDF extractor',
      next: 'Verify evidence and required fields',
      input: 'Synthetic referral PDF',
      output:
        'Canonical referral JSON with patient, clinical, insurance, and source fields',
      validation:
        'The response must satisfy the referral schema before it is accepted.',
      duration: '2m 41s',
      exception: {
        input: 'Synthetic referral with no insurance section',
        output: 'Canonical referral JSON with insurance marked missing',
        validation:
          'Missing content remains null; the extractor does not invent a carrier.',
      },
    }),
    step({
      id: 'verify-required-fields',
      name: 'Evaluate the seven required fields',
      description:
        'Classify every required value as complete, explicitly absent, missing, or unclear.',
      system: 'Intake rules',
      next: 'Apply the minimum intake threshold',
      input: 'Canonical referral JSON and source evidence',
      output: '7 of 7 fields complete',
      validation:
        'Name, DOB, phone, address, agency, wound information, and insurance are evaluated separately.',
      exception: {
        input: 'Canonical JSON with insurance null',
        output: '6 of 7 complete; insurance missing',
        validation:
          'Missing insurance is surfaced as a gap rather than treated as complete.',
      },
    }),
    step({
      id: 'apply-threshold',
      name: 'Apply the minimum threshold',
      description:
        'Check whether name, DOB, phone, and address are present before downstream preparation.',
      system: 'Intake planner',
      next: 'Search for existing patients or prepare follow-up',
      input: 'Four minimum identity/contact fields',
      output: 'Threshold met; duplicate checks allowed',
      validation: 'A missing minimum field blocks destination writes.',
      exception: {
        input: 'Name and DOB present; phone and address missing',
        output: 'Threshold not met; downstream writes blocked',
        validation: 'The plan records the exact missing threshold fields.',
      },
    }),
    step({
      id: 'search-monday',
      name: 'Search Monday.com for duplicates',
      description:
        'Search existing Master Sheet items using normalized patient identity.',
      system: 'Monday.com reader',
      next: 'Search DRK for chart matches',
      input: 'Patient name and date of birth',
      output: 'No matching Monday.com candidate found',
      validation:
        'Name-only matches never authorize patient creation or blocking.',
      exception: {
        input: 'Incomplete identity',
        output: 'Monday duplicate search skipped',
        validation:
          'Search is marked indeterminate when identity is insufficient.',
      },
    }),
    step({
      id: 'search-drk',
      name: 'Search DRK for an existing chart',
      description:
        'Check available DRK patient information before preparing a new chart action.',
      system: 'DRK reader',
      next: 'Classify the combined duplicate result',
      input: 'Patient name and DOB',
      output: 'No exact DRK chart match found',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'classify-duplicate',
      name: 'Classify duplicate risk',
      description:
        'Combine Monday and DRK candidates into a clear, probable, or exact result.',
      system: 'Duplicate policy',
      next: 'Build the review summary',
      input: 'Monday: no candidates; DRK: no exact match',
      output: 'Distinct patient; creation remains eligible after approval',
      validation: 'Probable and exact matches are blocked for human review.',
      exception: {
        input: 'Identity incomplete; both searches indeterminate',
        output: 'Duplicate status unresolved',
        validation:
          'No destination action can pass while duplicate status is unresolved.',
      },
    }),
    step({
      id: 'build-review-email',
      name: 'Build the human-review email',
      description:
        'Create a concise summary separating extracted data, Monday fields, DRK fields, and warnings.',
      system: 'Review summary builder',
      next: 'Send the review request',
      input: 'Canonical referral, evidence, gaps, and duplicate result',
      output: 'Review email with approval instructions and referral identifier',
      validation:
        'The message states what is missing and never claims a write already occurred.',
      exception: {
        input:
          'Referral with missing insurance and unresolved duplicate status',
        output: 'Review email highlights both blockers',
        validation: 'The reviewer sees every blocker before responding.',
      },
    }),
    step({
      id: 'send-review-email',
      name: 'Send the review request',
      description: 'Send the generated summary to the configured WCW reviewer.',
      system: 'Microsoft Graph / Outlook',
      next: 'Wait for a reply',
      input: 'Review email addressed to the configured reviewer',
      output: 'Microsoft message ID stored with the referral run',
      validation:
        'The outbound message is linked to one referral and one review request.',
    }),
    step({
      id: 'interpret-reply',
      name: 'Interpret the reviewer reply',
      description:
        'Classify a natural-language response as approve, reject, correct, or unclear.',
      system: 'Approval intent classifier',
      next: 'Apply the approval gate',
      input: 'Reply: Everything looks good, you can proceed.',
      output: 'Intent: approve; referral identifier matched',
      validation:
        'Ambiguous replies remain pending and cannot trigger external writes.',
      exception: {
        input: 'Reply: I will check this later.',
        output: 'Intent: unclear; approval remains pending',
        validation:
          'No write permission is granted by a non-committal response.',
        status: 'waiting',
      },
    }),
    step({
      id: 'gate-destinations',
      name: 'Gate Monday and DRK actions',
      description:
        'Require threshold, duplicate, and human-approval checks before any destination action.',
      system: 'Guarded execution policy',
      next: 'Begin the Handoff stage',
      input: 'Threshold met; duplicate clear; approval recorded',
      output: 'Destination preparation authorized exactly once',
      validation: 'The gate is atomic and idempotent.',
      exception: {
        input: 'Threshold blocked and approval absent',
        output: 'Destination actions denied',
        validation:
          'The run remains available for correction and later review.',
      },
    }),
  ],
}

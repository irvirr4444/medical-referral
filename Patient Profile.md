# Patient Profile

## Goal

Give WCW leaders and staff one place to understand a patient's referral status, identify what is blocking progress, and determine the next action.

The profile should summarize the referral workflow. It should not attempt to replace the patient's complete clinical record in DRK.

## How the profile opens

Selecting a patient from any objective card opens the patient profile in a large modal or side drawer. Closing the profile returns the user to the same objective, reporting period, and search results.

## Profile header

Display the most important identifying and workflow information first:

- Patient name
- Date of birth
- Phone number
- Address
- Current referral status
- Current automation stage
- Primary next action

## Patient details

- Full legal name
- Date of birth
- Preferred phone number
- Home address
- Preferred language, when available
- Emergency contact, when relevant

## Referral progress

- Referral received date and time
- Referral source or partner
- Referral type
- Current workflow stage
- Current status
- Time spent in the current stage
- Missing information
- Active blocker or escalation
- Next required action
- Person responsible for the next action

## Care team and appointment

- Assigned case manager
- Selected provider
- Appointment status
- Appointment date and time
- Appointment location
- Scheduling confirmation status
- Latest visit outcome
- Next expected visit

## Relevant care summary

Only show clinical details needed to understand or coordinate the referral:

- Primary diagnosis or referral reason
- Wound location and type, when applicable
- Important mobility or transportation needs
- Relevant safety notes
- Treatment status
- Discharge or wound-healing status

Detailed clinical documentation remains in DRK.

## Recent activity

Show a chronological timeline of important workflow events:

- Referral received
- Information verified
- Missing information requested or received
- Referral acknowledged
- Case manager assigned
- Provider selected
- Appointment proposed and confirmed
- Visit completed or missed
- Patient placed on hold
- Escalation created or resolved
- Discharge review requested

Each event should include the date, time, source, and responsible person or automation.

## Communications

- Most recent patient communication
- Most recent referral-source communication
- Communication channel
- Date and time
- Delivery or response status
- Short summary

Full email and message content should open only when needed.

## Source records

Provide links to the authoritative records:

- Referral PDF
- Outlook conversation
- Monday.com item
- DRK patient chart
- Appointment record

## Actions

Actions should depend on the patient's current stage and the user's permissions:

- Call patient
- Send message
- Request missing information
- Assign or change case manager
- Select or change provider
- Schedule or reschedule appointment
- Resolve blocker
- Escalate to management
- Open Monday.com
- Open DRK

## MVP recommendation

The first version should include:

1. Profile header
2. Patient details
3. Referral progress
4. Care team and appointment
5. Recent activity timeline
6. Links to Monday.com, DRK, and the referral PDF

Communications, clinical summaries, and workflow actions can be added after the read-only profile is validated.

## Privacy and safety

- Display only information required for referral coordination.
- Apply role-based access to clinical and contact information.
- Record profile access and user actions in an audit log.
- Do not expose protected health information in URLs or browser notifications.
- Use the authoritative source system for edits whenever direct synchronization is unavailable.
